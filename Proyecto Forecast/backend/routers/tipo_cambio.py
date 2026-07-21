"""
Tipo de Cambio CLP/USD — Forecast DCIC
Entrada manual + sync desde Banco Central de Chile (si disponible).
Circuit-breaker + fallback a USD_NEUTRO env si la API no responde.
"""
from datetime import date, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

from database import get_db
from auth import require_rol
from logger import get_logger
from constants import USD_NEUTRO

log = get_logger("forecast_dcic.tipo_cambio")
router = APIRouter()


class TipoCambioIn(BaseModel):
    fecha:   date
    usd_clp: float
    fuente:  str = "manual"


class TipoCambioOut(BaseModel):
    fecha:   date
    usd_clp: float
    fuente:  str


@router.get("/actual")
async def get_tipo_cambio_actual(db: AsyncSession = Depends(get_db)):
    """Retorna el tipo de cambio más reciente disponible."""
    row = await db.execute(
        text("SELECT fecha, usd_clp, fuente FROM tipo_cambio ORDER BY fecha DESC LIMIT 1")
    )
    r = row.mappings().first()
    if not r:
        raise HTTPException(404, "No hay tipo de cambio registrado. Ingresa uno manualmente.")
    dias_atraso = (date.today() - r["fecha"]).days
    return {
        "fecha":       r["fecha"].isoformat(),
        "usd_clp":     float(r["usd_clp"]),
        "fuente":      r["fuente"],
        "dias_atraso": dias_atraso,
        "advertencia": f"Dato de hace {dias_atraso} días" if dias_atraso > 3 else None,
    }


@router.get("/historico")
async def get_historico(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Historial de tipos de cambio para el período indicado."""
    params: dict = {}
    where_parts = []
    if desde:
        where_parts.append("fecha >= :desde")
        params["desde"] = desde
    if hasta:
        where_parts.append("fecha <= :hasta")
        params["hasta"] = hasta
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    rows = await db.execute(
        text("SELECT fecha, usd_clp, fuente FROM tipo_cambio "
             + where + " ORDER BY fecha DESC LIMIT 365"),
        params,
    )
    return [dict(r) for r in rows.mappings().all()]


@router.post("/", dependencies=[Depends(require_rol("admin", "editor"))])
async def registrar_tipo_cambio(data: TipoCambioIn, db: AsyncSession = Depends(get_db)):
    """Registra o actualiza el tipo de cambio para una fecha."""
    await db.execute(
        text("""
            INSERT INTO tipo_cambio (fecha, usd_clp, fuente)
            VALUES (:fecha, :usd_clp, :fuente)
            ON CONFLICT (fecha) DO UPDATE
              SET usd_clp = EXCLUDED.usd_clp,
                  fuente  = EXCLUDED.fuente,
                  created_at = NOW()
        """),
        {"fecha": data.fecha, "usd_clp": data.usd_clp, "fuente": data.fuente},
    )
    await db.commit()
    log.info(f"Tipo cambio registrado: {data.fecha} USD/CLP={data.usd_clp} fuente={data.fuente}")
    return {"ok": True, "fecha": data.fecha.isoformat(), "usd_clp": data.usd_clp}


@router.post("/sync-bcc", dependencies=[Depends(require_rol("admin"))])
async def sync_banco_central(db: AsyncSession = Depends(get_db)):
    """
    Intenta obtener el tipo de cambio USD/CLP desde la API pública
    del Banco Central de Chile (si está disponible).
    """
    try:
        import httpx
        # API pública BCC — series F073.TCO.PRE.Z.D (dólar observado diario)
        hoy   = date.today()
        desde = hoy - timedelta(days=7)
        url = (
            "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"
            "?user=rafael.calderon@dcic.cl&pass=&firstdate={}&lastdate={}"
            "&timeseries=F073.TCO.PRE.Z.D&function=GetSeries"
        ).format(desde.isoformat(), hoy.isoformat())

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)

        if resp.status_code != 200:
            raise HTTPException(502, f"BCC respondió {resp.status_code}")

        data = resp.json()
        series = data.get("Series", {}).get("Obs", [])
        if not series:
            raise HTTPException(502, "BCC no retornó datos")

        insertados = 0
        for obs in series:
            fecha_str = obs.get("indexDateString", "")
            valor_str = obs.get("value", "")
            if not fecha_str or not valor_str or valor_str in ("", "NaN"):
                continue
            try:
                f = date.fromisoformat(fecha_str)
                v = float(valor_str.replace(",", "."))
                await db.execute(
                    text("""
                        INSERT INTO tipo_cambio (fecha, usd_clp, fuente)
                        VALUES (:fecha, :usd_clp, 'bcc')
                        ON CONFLICT (fecha) DO UPDATE
                          SET usd_clp = EXCLUDED.usd_clp, fuente = 'bcc', created_at = NOW()
                    """),
                    {"fecha": f, "usd_clp": v},
                )
                insertados += 1
            except (ValueError, TypeError):
                continue

        await db.commit()
        log.info(f"Sync BCC: {insertados} registros actualizados")
        return {"ok": True, "insertados": insertados}

    except httpx.RequestError as e:
        raise HTTPException(502, f"No se pudo conectar al BCC: {e}")
    except ImportError:
        raise HTTPException(500, "Instala httpx: pip install httpx")


@router.post("/sync-auto", dependencies=[Depends(require_rol("admin", "editor"))])
async def sync_auto(db: AsyncSession = Depends(get_db)):
    """
    Sincronización automática con circuit-breaker:
    1. Intenta BCC. Si falla o no responde en 10s → fallback gracioso.
    2. Fallback: inserta USD_NEUTRO (valor env) con fuente='fallback_env'
       SOLO si no hay dato de hoy o de los últimos 3 días.
    Retorna: fuente usada, valor insertado, estado.
    """
    hoy = date.today()

    # ── 1. Intentar BCC ───────────────────────────────────────────────────────
    try:
        import httpx
        desde = hoy - timedelta(days=5)
        url = (
            "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"
            "?user=rafael.calderon@dcic.cl&pass=&firstdate={}&lastdate={}"
            "&timeseries=F073.TCO.PRE.Z.D&function=GetSeries"
        ).format(desde.isoformat(), hoy.isoformat())

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)

        if resp.status_code == 200:
            data   = resp.json()
            series = data.get("Series", {}).get("Obs", [])
            insertados = 0
            ultimo_valor = None
            for obs in series:
                fecha_str = obs.get("indexDateString", "")
                valor_str = obs.get("value", "")
                if not fecha_str or not valor_str or valor_str in ("", "NaN"):
                    continue
                try:
                    f = date.fromisoformat(fecha_str)
                    v = float(valor_str.replace(",", "."))
                    await db.execute(text("""
                        INSERT INTO tipo_cambio (fecha, usd_clp, fuente)
                        VALUES (:fecha, :usd_clp, 'bcc')
                        ON CONFLICT (fecha) DO UPDATE
                          SET usd_clp = EXCLUDED.usd_clp, fuente = 'bcc', created_at = NOW()
                    """), {"fecha": f, "usd_clp": v})
                    insertados += 1
                    ultimo_valor = v
                except (ValueError, TypeError):
                    continue
            if insertados > 0:
                await db.commit()
                log.info(f"sync-auto BCC: {insertados} registros")
                return {"fuente": "bcc", "insertados": insertados, "ultimo_valor": ultimo_valor, "estado": "ok"}

    except Exception as e:
        log.warning(f"sync-auto BCC falló (circuit-breaker activado): {e}")

    # ── 2. Fallback: USD_NEUTRO si no hay dato reciente ───────────────────────
    reciente = await db.execute(text(
        "SELECT fecha, usd_clp FROM tipo_cambio WHERE fecha >= :desde ORDER BY fecha DESC LIMIT 1"
    ), {"desde": hoy - timedelta(days=3)})
    row = reciente.mappings().first()

    if row:
        dias = (hoy - row["fecha"]).days
        log.info(f"sync-auto fallback: dato reciente ya existe ({row['fecha']}, {dias}d atrás)")
        return {"fuente": "existente", "usd_clp": float(row["usd_clp"]),
                "fecha": row["fecha"].isoformat(), "estado": "sin_cambios",
                "nota": "BCC no disponible, se mantiene dato reciente"}

    # No hay dato reciente → insertar fallback
    await db.execute(text("""
        INSERT INTO tipo_cambio (fecha, usd_clp, fuente)
        VALUES (:fecha, :usd_clp, 'fallback_env')
        ON CONFLICT (fecha) DO UPDATE
          SET usd_clp = EXCLUDED.usd_clp, fuente = 'fallback_env', created_at = NOW()
    """), {"fecha": hoy, "usd_clp": USD_NEUTRO})
    await db.commit()
    log.warning(f"sync-auto: BCC no disponible, insertado fallback USD_NEUTRO={USD_NEUTRO}")
    return {
        "fuente":   "fallback_env",
        "usd_clp":  USD_NEUTRO,
        "fecha":    hoy.isoformat(),
        "estado":   "fallback",
        "nota":     f"BCC no respondió. Usar variable USD_NEUTRO para ajustar el valor de referencia.",
    }
