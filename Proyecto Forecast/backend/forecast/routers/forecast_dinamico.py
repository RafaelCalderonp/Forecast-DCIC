"""
Router /api/forecast-dinamico/
Endpoints para el sistema de forecast dinámico 3 capas.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from pydantic import BaseModel
from typing import Optional
import csv
import io
from datetime import date

from database import get_db
from forecast.services.forecast_service import ForecastService
from forecast.services.alert_service import AlertService
from forecast.models.forecast_models import (
    LiftFactor, AlertaForecast, OrdenCompraSugerida, SegmentacionAbcXyz
)

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class LiftFactorCreate(BaseModel):
    nombre_evento: str
    canal: Optional[str] = None
    sku_pattern: Optional[str] = None
    fecha_inicio: date
    fecha_fin: date
    multiplicador: float = 1.0
    tipo: str = "manual"
    notas: Optional[str] = None


class LiftFactorUpdate(BaseModel):
    nombre_evento: Optional[str] = None
    canal: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    multiplicador: Optional[float] = None
    notas: Optional[str] = None


class AlertaResolver(BaseModel):
    notas: Optional[str] = None


class OrdenCompraUpdate(BaseModel):
    estado: str
    notas: Optional[str] = None


class OverrideCreate(BaseModel):
    sku: str
    canal: str
    periodo: date
    valor_override: float
    motivo: str


class OverrideUpdate(BaseModel):
    valor_override: Optional[float] = None
    motivo: Optional[str] = None
    aplicado: Optional[bool] = None


# ── Forecast: calcular y listar ───────────────────────────────────────────────

@router.post("/calcular")
async def calcular_forecast(
    background_tasks: BackgroundTasks,
    sku: Optional[str] = Query(None),
    canal: Optional[str] = Query(None),
    horizonte_meses: int = Query(6, ge=1, le=18),
    db: AsyncSession = Depends(get_db),
):
    """Dispara cálculo HW. Sin parámetros = todos los SKUs activos."""
    svc = ForecastService(db)

    if sku and canal:
        resultado = await svc.calcular_sku_canal(sku, canal, horizonte_meses)
        if resultado.get("error"):
            raise HTTPException(422, detail=resultado["error"])
        await svc.guardar_forecast(resultado["filas"])
        await db.commit()
        background_tasks.add_task(_refresh_vista, db)
        return {"ok": True, "skus_procesados": 1, "periodos": len(resultado["filas"])}

    # Cálculo masivo en background
    background_tasks.add_task(_calcular_todos_background, horizonte_meses)
    return {"ok": True, "mensaje": "Cálculo masivo iniciado en background"}


async def _calcular_todos_background(horizonte_meses: int):
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        svc = ForecastService(db)
        n_ok, n_err = await svc.calcular_todos_los_skus(horizonte_meses)
        await svc.refresh_vista()


async def _refresh_vista(db: AsyncSession):
    try:
        await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_forecast_resumen"))
        await db.commit()
    except Exception:
        try:
            await db.rollback()
            await db.execute(text("REFRESH MATERIALIZED VIEW mv_forecast_resumen"))
            await db.commit()
        except Exception:
            pass


@router.get("/resumen")
async def forecast_resumen(
    periodo: Optional[str] = Query(None, description="YYYY-MM-DD primer día del mes"),
    canal: Optional[str] = Query(None),
    clase_abc: Optional[str] = Query(None),
    estado_mape: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Lee mv_forecast_resumen con filtros opcionales."""
    from datetime import date as date_type
    conditions = ["1=1"]
    params: dict = {}

    if periodo:
        conditions.append("periodo = :periodo")
        params["periodo"] = date_type.fromisoformat(periodo) if isinstance(periodo, str) else periodo
    if canal:
        conditions.append("canal = :canal")
        params["canal"] = canal
    if clase_abc:
        conditions.append("clase_abc = :clase_abc")
        params["clase_abc"] = clase_abc
    if estado_mape:
        conditions.append("estado_mape = :estado_mape")
        params["estado_mape"] = estado_mape

    where = " AND ".join(conditions)
    offset = (page - 1) * per_page
    params.update({"limit": per_page, "offset": offset})

    q = text(f"""
        SELECT sku, canal, periodo, descripcion_producto, marca, categoria,
               clase_abc, clase_xyz,
               forecast_base, forecast_ajustado, forecast_final,
               ventas_reales, mape, bias, dci, lift_aplicado,
               es_override, estado_mape, alertas_activas
        FROM mv_forecast_resumen
        WHERE {where}
        ORDER BY clase_abc, sku, canal, periodo
        LIMIT :limit OFFSET :offset
    """)

    result = await db.execute(q, params)
    rows = result.mappings().fetchall()

    count_q = text(f"SELECT COUNT(*) FROM mv_forecast_resumen WHERE {where}")
    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    total = (await db.execute(count_q, count_params)).scalar()

    return {
        "data": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "pages": (total + per_page - 1) // per_page,
    }


@router.get("/sku/{sku}")
async def forecast_sku(
    sku: str,
    meses: int = Query(6, ge=1, le=18),
    db: AsyncSession = Depends(get_db),
):
    """Detalle de forecast de un SKU en todos sus canales."""
    q = text("""
        SELECT canal, periodo, forecast_base, forecast_ajustado,
               forecast_final, ventas_reales, mape, bias, dci,
               lift_aplicado, modelo_version, parametros_hw
        FROM forecast_resultados
        WHERE sku = :sku
          AND periodo >= date_trunc('month', CURRENT_DATE)
        ORDER BY canal, periodo
        LIMIT :lim
    """)
    result = await db.execute(q, {"sku": sku, "lim": meses * 10})
    rows = result.mappings().fetchall()

    by_canal: dict = {}
    for r in rows:
        c = r["canal"]
        if c not in by_canal:
            by_canal[c] = []
        by_canal[c].append(dict(r))

    return {"sku": sku, "canales": [{"canal": k, "forecast": v} for k, v in by_canal.items()]}


@router.post("/refresh-vista")
async def refresh_vista(db: AsyncSession = Depends(get_db)):
    svc = ForecastService(db)
    await svc.refresh_vista()
    return {"ok": True}


@router.get("/export/csv")
async def exportar_csv(
    periodo_inicio: str = Query(...),
    periodo_fin: str = Query(...),
    canal: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Descarga forecast como CSV para columnas O PROY. del informe."""
    from datetime import date as date_type
    _d = lambda s: date_type.fromisoformat(s) if isinstance(s, str) else s
    conditions = ["periodo BETWEEN :pi AND :pf"]
    params = {"pi": _d(periodo_inicio), "pf": _d(periodo_fin)}
    if canal:
        conditions.append("canal = :canal")
        params["canal"] = canal

    q = text(f"""
        SELECT sku, canal, periodo, forecast_final, forecast_base,
               lift_aplicado, ventas_reales, mape, clase_abc
        FROM mv_forecast_resumen
        WHERE {' AND '.join(conditions)}
        ORDER BY sku, canal, periodo
    """)
    result = await db.execute(q, params)
    rows = result.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["SKU", "Canal", "Periodo", "O_PROY", "Forecast_Base",
                     "Lift_Aplicado", "Ventas_Reales", "MAPE", "Clase_ABC"])
    for r in rows:
        writer.writerow([r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=forecast_{periodo_inicio}_{periodo_fin}.csv"},
    )


# ── Lift Factors ──────────────────────────────────────────────────────────────

@router.get("/lift-factors")
async def listar_lift_factors(
    vigente: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    q = select(LiftFactor).order_by(LiftFactor.fecha_inicio.desc())
    if vigente:
        hoy = date.today()
        q = q.where(LiftFactor.fecha_inicio <= hoy, LiftFactor.fecha_fin >= hoy)
    result = await db.execute(q)
    lifts = result.scalars().all()
    return [
        {
            "id": lf.id, "nombre_evento": lf.nombre_evento,
            "canal": lf.canal, "sku_pattern": lf.sku_pattern,
            "fecha_inicio": lf.fecha_inicio, "fecha_fin": lf.fecha_fin,
            "multiplicador": float(lf.multiplicador),
            "tipo": lf.tipo, "notas": lf.notas,
        }
        for lf in lifts
    ]


@router.post("/lift-factors", status_code=201)
async def crear_lift_factor(data: LiftFactorCreate, db: AsyncSession = Depends(get_db)):
    lf = LiftFactor(**data.model_dump())
    db.add(lf)
    await db.commit()
    await db.refresh(lf)
    return {"id": lf.id, "nombre_evento": lf.nombre_evento, "multiplicador": float(lf.multiplicador)}


@router.put("/lift-factors/{lf_id}")
async def actualizar_lift_factor(
    lf_id: int, data: LiftFactorUpdate, db: AsyncSession = Depends(get_db)
):
    lf = await db.get(LiftFactor, lf_id)
    if not lf:
        raise HTTPException(404, "Lift factor no encontrado")
    for campo, valor in data.model_dump(exclude_none=True).items():
        setattr(lf, campo, valor)
    await db.commit()
    return {"id": lf.id, "multiplicador": float(lf.multiplicador)}


@router.delete("/lift-factors/{lf_id}")
async def eliminar_lift_factor(lf_id: int, db: AsyncSession = Depends(get_db)):
    lf = await db.get(LiftFactor, lf_id)
    if not lf:
        raise HTTPException(404)
    await db.delete(lf)
    await db.commit()
    return {"ok": True}


# ── Alertas ───────────────────────────────────────────────────────────────────

@router.get("/alertas")
async def listar_alertas(
    tipo: Optional[str] = Query(None),
    severidad: Optional[str] = Query(None),
    sku: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    q = select(AlertaForecast).where(AlertaForecast.resuelta == False)
    if tipo:
        q = q.where(AlertaForecast.tipo_alerta == tipo)
    if severidad:
        q = q.where(AlertaForecast.severidad == severidad)
    if sku:
        q = q.where(AlertaForecast.sku == sku)
    q = q.order_by(AlertaForecast.severidad.desc(), AlertaForecast.creado_en.desc())
    q = q.offset((page - 1) * 50).limit(50)
    result = await db.execute(q)
    alertas = result.scalars().all()

    criticas = await db.execute(
        text("SELECT COUNT(*) FROM alertas_forecast WHERE resuelta = FALSE AND severidad = 'CRITICA'")
    )
    n_criticas = criticas.scalar()

    return {
        "data": [
            {
                "id": a.id, "tipo_alerta": a.tipo_alerta, "sku": a.sku,
                "canal": a.canal, "periodo": a.periodo,
                "valor_actual": float(a.valor_actual), "umbral": float(a.umbral),
                "severidad": a.severidad, "mensaje": a.mensaje, "creado_en": a.creado_en,
            }
            for a in alertas
        ],
        "total_criticas": n_criticas,
    }


@router.patch("/alertas/{alerta_id}/resolver")
async def resolver_alerta(
    alerta_id: int, data: AlertaResolver, db: AsyncSession = Depends(get_db)
):
    from datetime import datetime
    alerta = await db.get(AlertaForecast, alerta_id)
    if not alerta:
        raise HTTPException(404)
    alerta.resuelta = True
    alerta.resuelta_en = datetime.utcnow()
    await db.commit()
    return {"ok": True, "id": alerta_id}


# ── Segmentación ──────────────────────────────────────────────────────────────

@router.get("/segmentacion")
async def segmentacion_abc_xyz(
    canal: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Retorna la última segmentación como matriz 3×3."""
    q = select(SegmentacionAbcXyz).order_by(SegmentacionAbcXyz.calculado_en.desc())
    if canal:
        q = q.where(SegmentacionAbcXyz.canal == canal)
    result = await db.execute(q)
    rows = result.scalars().all()

    matriz: dict = {}
    for r in rows:
        clave = f"{r.clase_abc}{r.clase_xyz}"
        if clave not in matriz:
            matriz[clave] = []
        matriz[clave].append({"sku": r.sku, "canal": r.canal, "revenue": float(r.revenue_total or 0)})

    return {"matriz": matriz, "total_skus": len(rows)}


@router.post("/segmentacion/recalcular")
async def recalcular_segmentacion(
    periodo_inicio: str = Query(..., description="YYYY-MM-DD"),
    periodo_fin: str = Query(..., description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    svc = ForecastService(db)
    n = await svc.recalcular_segmentacion(periodo_inicio, periodo_fin)
    return {"ok": True, "skus_reclasificados": n}


# ── Órdenes de compra ─────────────────────────────────────────────────────────

@router.get("/ordenes-compra")
async def listar_ordenes_compra(
    estado: Optional[str] = Query(None),
    clase_abc: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(OrdenCompraSugerida).order_by(OrdenCompraSugerida.fecha_sugerida)
    if estado:
        q = q.where(OrdenCompraSugerida.estado == estado)
    if clase_abc:
        q = q.where(OrdenCompraSugerida.clase_abc == clase_abc)
    result = await db.execute(q)
    ocs = result.scalars().all()
    return [
        {
            "id": oc.id, "sku": oc.sku,
            "fecha_sugerida": oc.fecha_sugerida,
            "fecha_necesidad": oc.fecha_necesidad,
            "cantidad_sugerida": oc.cantidad_sugerida,
            "stock_actual": oc.stock_actual,
            "forecast_demanda": float(oc.forecast_demanda),
            "lead_time_dias": oc.lead_time_dias,
            "estado": oc.estado, "clase_abc": oc.clase_abc,
        }
        for oc in ocs
    ]


@router.patch("/ordenes-compra/{oc_id}")
async def actualizar_orden_compra(
    oc_id: int, data: OrdenCompraUpdate, db: AsyncSession = Depends(get_db)
):
    estados_validos = {"pendiente", "aprobada", "rechazada", "emitida"}
    if data.estado not in estados_validos:
        raise HTTPException(422, f"Estado debe ser uno de: {estados_validos}")
    oc = await db.get(OrdenCompraSugerida, oc_id)
    if not oc:
        raise HTTPException(404)
    oc.estado = data.estado
    if data.notas:
        oc.notas = data.notas
    await db.commit()
    return {"ok": True, "id": oc_id, "estado": oc.estado}


# ── Generación de alertas ─────────────────────────────────────────────────────

@router.get("/alertas-precio")
async def alertas_precio(db: AsyncSession = Depends(get_db)):
    """
    SKUs con alza/baja de precio relevante detectada (panel expertos ago-2026).
    Usado para marcar SKUs que requieren revisión manual antes de aprobar su OC.
    """
    from constants import PRECIO_ALZA_UMBRAL_REVISION, PRECIO_ALZA_UMBRAL_CONGELAR
    result = await db.execute(text("""
        SELECT a.sku, p.descripcion, a.precio_anterior, a.precio_nuevo,
               a.delta_pct, a.factor_ajuste, a.fecha_deteccion
        FROM ajuste_precio_2026 a
        LEFT JOIN productos p ON p.sku = a.sku
        WHERE a.activo = TRUE AND a.delta_pct > :umbral
        ORDER BY a.delta_pct DESC
    """), {"umbral": PRECIO_ALZA_UMBRAL_REVISION})
    rows = result.mappings().all()
    return [{
        "sku": r["sku"],
        "descripcion": r["descripcion"],
        "precio_anterior": float(r["precio_anterior"]),
        "precio_nuevo": float(r["precio_nuevo"]),
        "delta_pct": float(r["delta_pct"]),
        "factor_ajuste": float(r["factor_ajuste"]),
        "nivel": "CONGELAR" if float(r["delta_pct"]) > PRECIO_ALZA_UMBRAL_CONGELAR else "REVISION",
        "fecha_deteccion": r["fecha_deteccion"].isoformat(),
    } for r in rows]


@router.post("/alertas/generar")
async def generar_alertas(db: AsyncSession = Depends(get_db)):
    """Ejecuta todos los detectores de alertas y devuelve cuántas se crearon."""
    svc = AlertService(db)
    resultado = await svc.ejecutar_todas()
    return {"ok": True, **resultado}


@router.post("/alertas/generar/{tipo}")
async def generar_alerta_tipo(
    tipo: str,
    db: AsyncSession = Depends(get_db),
):
    """Ejecuta un detector específico: mape | dci | t90 | oos"""
    svc = AlertService(db)
    tipos_map = {
        "mape": svc.generar_alertas_mape,
        "dci":  svc.generar_alertas_dci,
        "t90":  svc.generar_alertas_t90,
        "oos":  svc.generar_alertas_oos,
    }
    if tipo not in tipos_map:
        raise HTTPException(422, f"Tipo debe ser uno de: {list(tipos_map)}")
    n = await tipos_map[tipo]()
    return {"ok": True, "tipo": tipo, "alertas_creadas": n}


# ── Generación de órdenes de compra ──────────────────────────────────────────

@router.post("/ordenes-compra/generar")
async def generar_ordenes_compra(
    horizonte_dias: int = Query(90, ge=30, le=180),
    db: AsyncSession = Depends(get_db),
):
    """
    Genera OC sugeridas para SKUs donde stock_actual < demanda proyectada + stock_seguridad.
    Usa forecast_resultados + segmentacion_abc_xyz + stock.
    """
    from datetime import date as dt, timedelta
    from forecast.engine.forecast_engine import generar_ordenes_compra_sugeridas
    import pandas as pd

    hoy = dt.today()
    horizonte_fin = hoy + timedelta(days=horizonte_dias)

    # Cargar forecast próximos N días
    q_fc = text("""
        SELECT fr.sku, fr.canal, fr.periodo, fr.forecast_final, s.clase_abc
        FROM forecast_resultados fr
        LEFT JOIN (
            SELECT sku, canal, clase_abc
            FROM segmentacion_abc_xyz
            WHERE periodo_inicio = (SELECT MAX(periodo_inicio) FROM segmentacion_abc_xyz)
        ) s ON s.sku = fr.sku AND s.canal = fr.canal
        WHERE fr.periodo BETWEEN :hoy AND :fin
          AND fr.forecast_final > 0
    """)
    res_fc = await db.execute(q_fc, {"hoy": hoy, "fin": horizonte_fin})
    df_forecast = pd.DataFrame(res_fc.fetchall(), columns=["sku", "canal", "periodo", "forecast_final", "clase_abc"])

    if df_forecast.empty:
        return {"ok": True, "ordenes_generadas": 0, "msg": "Sin forecast en el horizonte"}

    # Stock actual
    q_st = text("SELECT sku, COALESCE(stock_base, 0) AS stock_base FROM stock")
    res_st = await db.execute(q_st)
    df_stock = pd.DataFrame(res_st.fetchall(), columns=["sku", "stock_base"])

    # Lead times por SKU clase A=21d, B=30d, C=45d
    lead_por_abc = {"A": 21, "B": 30, "C": 45}
    lead_time_por_sku = {}
    for _, row in df_forecast.drop_duplicates("sku").iterrows():
        lead_time_por_sku[row["sku"]] = lead_por_abc.get(row.get("clase_abc", "C") or "C", 30)

    df_ocs = generar_ordenes_compra_sugeridas(
        df_forecast, df_stock, lead_time_por_sku, hoy=hoy
    )

    if df_ocs.empty:
        return {"ok": True, "ordenes_generadas": 0, "msg": "Stock suficiente para el horizonte"}

    # Limpiar OCs pendientes anteriores antes de insertar
    await db.execute(text("DELETE FROM ordenes_compra_sugeridas WHERE estado = 'pendiente'"))

    # Circuit-breaker por alza de precio (panel expertos ago-2026, recomendación Larraín):
    # SKUs con alza > umbral requieren revisión manual antes de aprobar la OC.
    from constants import PRECIO_ALZA_UMBRAL_REVISION, PRECIO_ALZA_UMBRAL_CONGELAR
    q_precio = text("""
        SELECT sku, delta_pct FROM ajuste_precio_2026
        WHERE activo = TRUE AND delta_pct > :umbral
    """)
    res_precio = await db.execute(q_precio, {"umbral": PRECIO_ALZA_UMBRAL_REVISION})
    alzas_por_sku = {r[0]: float(r[1]) for r in res_precio.fetchall()}

    from datetime import date as date_type
    _d = lambda s: date_type.fromisoformat(str(s)[:10]) if isinstance(s, str) else (s if isinstance(s, date_type) else date_type.fromisoformat(str(s)[:10]))

    n_revision = 0
    for _, row in df_ocs.iterrows():
        def _safe_int(v, default=0): return int(v) if pd.notna(v) else default
        def _safe_float(v, default=0.0): return float(v) if pd.notna(v) else default

        sku = row["sku"]
        delta_pct = alzas_por_sku.get(sku)
        estado = "pendiente"
        notas = None
        if delta_pct is not None:
            n_revision += 1
            if delta_pct > PRECIO_ALZA_UMBRAL_CONGELAR:
                estado = "revision_requerida"
                notas = f"⚠ Alza de precio +{delta_pct:.1f}% — congelar compra hasta validar demanda real post-alza."
            else:
                estado = "revision_requerida"
                notas = f"⚠ Alza de precio +{delta_pct:.1f}% — revisar antes de aprobar (umbral {PRECIO_ALZA_UMBRAL_REVISION}%)."

        oc = OrdenCompraSugerida(
            sku=sku,
            fecha_sugerida=_d(row["fecha_sugerida"]),
            fecha_necesidad=_d(row["fecha_necesidad"]),
            cantidad_sugerida=_safe_int(row["cantidad_sugerida"]),
            stock_actual=_safe_int(row["stock_actual"]),
            forecast_demanda=_safe_float(row["forecast_demanda"]),
            lead_time_dias=_safe_int(row["lead_time_dias"], 30),
            stock_seguridad=_safe_int(row["stock_seguridad"]),
            estado=estado,
            notas=notas,
            clase_abc=row.get("clase_abc") if pd.notna(row.get("clase_abc")) else None,
        )
        db.add(oc)

    await db.commit()
    return {"ok": True, "ordenes_generadas": len(df_ocs), "requieren_revision_por_precio": n_revision}


# ── Overrides manuales ────────────────────────────────────────────────────────

@router.get("/overrides")
async def listar_overrides(
    sku: Optional[str] = Query(None),
    canal: Optional[str] = Query(None),
    aplicado: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    from forecast.models.forecast_models import OverrideForecast
    q = select(OverrideForecast).order_by(OverrideForecast.creado_en.desc())
    if sku:
        q = q.where(OverrideForecast.sku == sku)
    if canal:
        q = q.where(OverrideForecast.canal == canal)
    if aplicado is not None:
        q = q.where(OverrideForecast.aplicado == aplicado)
    result = await db.execute(q)
    ovs = result.scalars().all()
    return [
        {
            "id": o.id, "sku": o.sku, "canal": o.canal,
            "periodo": o.periodo, "valor_original": float(o.valor_original),
            "valor_override": float(o.valor_override),
            "motivo": o.motivo, "aplicado": o.aplicado,
            "creado_en": o.creado_en,
        }
        for o in ovs
    ]


@router.post("/overrides", status_code=201)
async def crear_override(data: OverrideCreate, db: AsyncSession = Depends(get_db)):
    from forecast.models.forecast_models import OverrideForecast

    # Obtener valor original del forecast actual
    q = text("""
        SELECT forecast_final FROM forecast_resultados
        WHERE sku = :sku AND canal = :canal AND periodo = :periodo
        LIMIT 1
    """)
    res = await db.execute(q, {"sku": data.sku, "canal": data.canal, "periodo": data.periodo})
    row = res.fetchone()
    valor_original = float(row[0]) if row else 0.0

    # Verificar si ya existe override para este período
    from sqlalchemy import text as t2
    existe = await db.execute(
        t2("SELECT id FROM overrides_forecast WHERE sku=:sku AND canal=:canal AND periodo=:p"),
        {"sku": data.sku, "canal": data.canal, "p": data.periodo}
    )
    if existe.fetchone():
        raise HTTPException(409, "Ya existe un override para este SKU/canal/período")

    ov = OverrideForecast(
        sku=data.sku,
        canal=data.canal,
        periodo=data.periodo,
        valor_original=valor_original,
        valor_override=data.valor_override,
        motivo=data.motivo,
        aplicado=False,
    )
    db.add(ov)

    # Aplicar inmediatamente al forecast_resultados
    await db.execute(
        text("""
            UPDATE forecast_resultados
            SET forecast_final = :val, es_override = TRUE
            WHERE sku = :sku AND canal = :canal AND periodo = :periodo
        """),
        {"val": data.valor_override, "sku": data.sku, "canal": data.canal, "periodo": data.periodo}
    )
    await db.flush()
    # Marcar como aplicado
    ov.aplicado = True
    await db.commit()
    await db.refresh(ov)
    return {"id": ov.id, "ok": True, "valor_original": valor_original, "valor_override": data.valor_override}


@router.delete("/overrides/{ov_id}")
async def eliminar_override(ov_id: int, db: AsyncSession = Depends(get_db)):
    from forecast.models.forecast_models import OverrideForecast
    ov = await db.get(OverrideForecast, ov_id)
    if not ov:
        raise HTTPException(404)
    # Restaurar valor original
    await db.execute(
        text("""
            UPDATE forecast_resultados
            SET forecast_final = :val, es_override = FALSE
            WHERE sku = :sku AND canal = :canal AND periodo = :periodo
        """),
        {"val": ov.valor_original, "sku": ov.sku, "canal": ov.canal, "periodo": ov.periodo}
    )
    await db.delete(ov)
    await db.commit()
    return {"ok": True, "restaurado": float(ov.valor_original)}
