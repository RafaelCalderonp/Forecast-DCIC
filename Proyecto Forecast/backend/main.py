# ============================================================
# FORECAST DCIC - Backend FastAPI
# ============================================================

import uuid
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy.exc import IntegrityError

import os
from logger import get_logger, set_correlation_id
from routers import productos, packs, forecast, ventas, stock, temporadas, marcas, categorias, ajuste_forecast, compras, forecast_2027, tipo_cambio, dashboard, lista_precios
from forecast.routers import forecast_dinamico
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    _SCHEDULER_OK = True
except ImportError:
    _SCHEDULER_OK = False
# migracion solo se activa con variable de entorno MIGRATION_MODE=1 (nunca en producción)
if os.getenv("MIGRATION_MODE") == "1":
    from routers import migracion as _migracion_mod
from routers import auth_router, api_keys_router

log = get_logger("forecast_dcic.main")


async def _job_recalibrar_mensual():
    """Job 1 — recalibra HW todos los SKUs el día 1 de cada mes."""
    from database import AsyncSessionLocal
    from forecast.services.forecast_service import ForecastService
    async with AsyncSessionLocal() as db:
        svc = ForecastService(db)
        n_ok, n_err = await svc.calcular_todos_los_skus(horizonte_meses=6)
        await svc.refresh_vista()
        log.info(f"[Scheduler] recalibración mensual: {n_ok} OK / {n_err} errores")


async def _job_alertas_quincenal():
    """Job 2 — genera alertas cada 15 días."""
    from database import AsyncSessionLocal
    from forecast.services.alert_service import AlertService
    async with AsyncSessionLocal() as db:
        svc = AlertService(db)
        res = await svc.ejecutar_todas()
        log.info(f"[Scheduler] alertas quincenales: {res}")


async def _job_monitor_t90():
    """Job 3 — monitoreo semanal protocolo T-90."""
    from database import AsyncSessionLocal
    from forecast.services.alert_service import AlertService
    async with AsyncSessionLocal() as db:
        svc = AlertService(db)
        n = await svc.generar_alertas_t90()
        if n > 0:
            log.info(f"[Scheduler] T-90 activado: {n} alertas creadas")


async def _job_sync_descontinuados():
    """Job 4 — respaldo diario: sincroniza activo/por_discontinuar según stock."""
    from database import AsyncSessionLocal
    from services.descontinuados_service import sincronizar_descontinuados
    async with AsyncSessionLocal() as db:
        cambios = await sincronizar_descontinuados(db)
        if cambios["desactivados"] or cambios["reactivados"]:
            log.info(
                f"[Scheduler] descontinuados: {len(cambios['desactivados'])} desactivados, "
                f"{len(cambios['reactivados'])} marcados por_discontinuar"
            )


async def _job_sync_stock_api():
    """Job 5 — sync horario de stock desde dcic-stock-loader (misma cadencia que la fuente)."""
    from database import AsyncSessionLocal
    from services.stock_api_service import sincronizar_stock_desde_api
    async with AsyncSessionLocal() as db:
        try:
            resultado = await sincronizar_stock_desde_api(db)
            log.info(f"[Scheduler] sync stock-loader: {resultado['actualizados']} SKUs actualizados")
        except Exception as e:
            log.warning(f"[Scheduler] sync stock-loader falló (no crítico): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if _SCHEDULER_OK:
        scheduler = AsyncIOScheduler()
        # Job 1: recalibración HW — día 1 de cada mes a las 03:00
        scheduler.add_job(_job_recalibrar_mensual, CronTrigger(day=1, hour=3, minute=0))
        # Job 2: alertas — días 1 y 15 de cada mes a las 04:00
        scheduler.add_job(_job_alertas_quincenal, CronTrigger(day="1,15", hour=4, minute=0))
        # Job 3: T-90 — cada lunes a las 08:00
        scheduler.add_job(_job_monitor_t90, CronTrigger(day_of_week="mon", hour=8, minute=0))
        # Job 4: sync descontinuados (respaldo) — todos los días a las 05:00
        scheduler.add_job(_job_sync_descontinuados, CronTrigger(hour=5, minute=0))
        # Job 5: sync stock desde dcic-stock-loader — cada hora
        scheduler.add_job(_job_sync_stock_api, CronTrigger(minute=15))
        scheduler.start()
        log.info("Scheduler APScheduler iniciado (5 jobs)")
    log.info("Forecast DCIC API iniciada")
    yield
    if scheduler:
        scheduler.shutdown()
    log.info("Forecast DCIC API detenida")


app = FastAPI(
    title="Forecast DCIC API",
    version="1.0.0",
    redirect_slashes=False,
    description="API de gestión de productos, forecast, ventas y stock DCIC",
    lifespan=lifespan,
)

# CORS para React frontend
# CORS_ORIGINS: lista separada por comas (ej: "https://forecast-dcic.pages.dev,https://forecast.dcic.cl")
_cors_env = os.getenv("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()] or [
    "http://localhost:3002",
    "http://127.0.0.1:3002",
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Middleware: request logging con latencia ─────────────────────────────────

@app.middleware("http")
async def request_logger(request: Request, call_next):
    # Usar X-Request-ID del cliente o generar uno nuevo
    cid = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
    set_correlation_id(cid)

    t0 = time.perf_counter()
    response = await call_next(request)
    ms = round((time.perf_counter() - t0) * 1000)

    response.headers["X-Request-ID"] = cid
    level = "warning" if response.status_code >= 400 else "info"
    getattr(log, level)(
        f"{request.method} {request.url.path} → {response.status_code} ({ms}ms)"
    )
    return response


# ── Manejo de excepciones estructurado ───────────────────────────────────────

@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    detalle = str(exc.orig) if exc.orig else str(exc)
    log.warning(f"IntegrityError {request.method} {request.url.path} — {detalle}")
    return JSONResponse(
        status_code=409,
        content={"error": "conflict", "detalle": detalle},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    from logger import get_correlation_id
    correlation_id = get_correlation_id() or str(uuid.uuid4())[:8]
    log.error(
        f"{request.method} {request.url.path} — {type(exc).__name__}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "correlation_id": correlation_id},
    )


@app.get("/health", tags=["Health"])
async def health():
    from sqlalchemy import text
    from database import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        log.error(f"Health check DB error: {exc}")
        db_ok = False
    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={"status": "ok" if db_ok else "degraded", "database": db_ok},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(temporadas.router,      prefix="/api/temporadas",      tags=["Temporadas"])
app.include_router(marcas.router,          prefix="/api/marcas",           tags=["Marcas"])
app.include_router(categorias.router,      prefix="/api/categorias",       tags=["Categorías"])
app.include_router(productos.router,       prefix="/api/productos",        tags=["Productos"])
app.include_router(packs.router,           prefix="/api/packs",            tags=["Packs"])
app.include_router(forecast.router,        prefix="/api/forecast",         tags=["Forecast"])
app.include_router(ventas.router,          prefix="/api/ventas",           tags=["Ventas"])
app.include_router(stock.router,           prefix="/api/stock",            tags=["Stock"])
app.include_router(ajuste_forecast.router, prefix="/api/ajuste-forecast",  tags=["Ajuste Forecast"])
app.include_router(compras.router,         prefix="/api/compras",          tags=["Compras"])
app.include_router(forecast_2027.router,   prefix="/api/forecast-2027",    tags=["Forecast 2027"])
app.include_router(auth_router.router,     prefix="/api/auth",             tags=["Auth"])
app.include_router(tipo_cambio.router,     prefix="/api/tipo-cambio",      tags=["Tipo de Cambio"])
app.include_router(dashboard.router,       prefix="/api/dashboard",         tags=["Dashboard"])
app.include_router(lista_precios.router,      prefix="/api/lista-precios",      tags=["Lista de Precios"])
app.include_router(api_keys_router.router,    prefix="/api/api-keys",            tags=["API Keys M2M"])
app.include_router(forecast_dinamico.router, prefix="/api/forecast-dinamico",  tags=["Forecast Dinámico"])
if os.getenv("MIGRATION_MODE") == "1":
    app.include_router(_migracion_mod.router, prefix="/api/migracion",     tags=["migracion"])


@app.get("/")
def root():
    return {"status": "ok", "proyecto": "Forecast DCIC", "version": "1.0.0"}
