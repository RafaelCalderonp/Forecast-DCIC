"""
Forecast 2027 por SKU x Canal x Mes
Estructura: SKU Total → desglose por canal
"""
import asyncio, sys, os
from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List
from pydantic import BaseModel, Field
from database import get_db
from auth import require_rol, get_current_user
from constants import IVA_FACTOR_FLOAT, PHI_CAP, MACRO_SENS

router = APIRouter()

CANALES_ORDEN = [
    'Falabella', 'Mercado Libre', 'Walmart', 'Paris',
    'Vincenzi', 'Ripley', 'GlowUp', 'Petwoow', 'Kfit',
    'Venta Directa', 'Segunda Seleccion', 'Miglu', 'Bfresh',
    'Homeclaf', 'Dafiti',
]

MESES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']


@router.get("")
async def get_forecast_2027(
    canal:        Optional[str] = Query(None),
    marca_id:     Optional[int] = Query(None),
    categoria_id: Optional[int] = Query(None),
    temporada_id: Optional[int] = Query(None),
    limit:        int = Query(500, ge=1, le=2000),
    offset:       int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Retorna pivot SKU × Canal × 12 meses con paginación."""
    params: dict = {}
    where_parts = []
    if marca_id:
        where_parts.append("p.marca_id = :marca_id")
        params["marca_id"] = marca_id
    if categoria_id:
        where_parts.append("p.categoria_id = :categoria_id")
        params["categoria_id"] = categoria_id
    if temporada_id:
        where_parts.append("p.temporada_id = :temporada_id")
        params["temporada_id"] = temporada_id
    if canal:
        where_parts.append("f.canal = :canal")
        params["canal"] = canal
    where_sql = ("AND " + " AND ".join(where_parts)) if where_parts else ""

    sql = f"""
    WITH precio_real AS (
        SELECT v.sku,
               SUM(v.precio_total_bruto) / NULLIF(SUM(v.cantidad - COALESCE(v.unidades_devueltas,0)), 0) AS precio
        FROM ventas v
        WHERE v.estado_orden = 'Regular'
          AND v.fecha >= '2025-01-01'
          AND v.cantidad > COALESCE(v.unidades_devueltas, 0)
        GROUP BY v.sku
    )
    SELECT
        f.sku,
        p.descripcion,
        m.nombre  AS marca,
        c.nombre  AS categoria,
        s.nombre  AS subcategoria,
        p.tipo_producto,
        t.nombre  AS temporada,
        p.grupo_pareto AS pareto,
        f.canal,
        f.mes,
        f.cantidad,
        f.ajuste_manual,
        COALESCE(NULLIF(pr.precio,0), NULLIF(p.precio_venta_bruto,0), 0) AS precio_lp,
        COALESCE(p.costo_unitario_neto, 0)                     AS costo
    FROM forecast_2027 f
    JOIN productos p    ON p.sku = f.sku
    LEFT JOIN precio_real pr   ON pr.sku = f.sku
    LEFT JOIN marcas m         ON m.id = p.marca_id
    LEFT JOIN categorias c     ON c.id = p.categoria_id
    LEFT JOIN subcategorias s  ON s.id = p.subcategoria_id
    LEFT JOIN temporadas t     ON t.id = p.temporada_id
    WHERE p.activo = TRUE AND p.es_pack = FALSE
      AND f.cantidad > 0
      {where_sql}
    ORDER BY p.descripcion, f.sku, f.canal, f.mes
    """
    result = await db.execute(text(sql), params)
    rows = result.mappings().all()

    # Construir estructura: {sku: {info, canales: {canal: {mes: qty}}}}
    skus: dict = {}
    for r in rows:
        sku = r["sku"]
        ch  = r["canal"]
        mes = r["mes"]
        qty = int(r["cantidad"])

        if sku not in skus:
            skus[sku] = {
                "sku":           sku,
                "descripcion":   r["descripcion"],
                "marca":         r["marca"],
                "categoria":     r["categoria"],
                "subcategoria":  r["subcategoria"],
                "tipo_producto": r["tipo_producto"],
                "temporada":     r["temporada"],
                "pareto":        r["pareto"],
                "precio_lp":     float(r["precio_lp"] or 0),
                "costo":         float(r["costo"] or 0),
                "canales":       {},
            }
        if ch not in skus[sku]["canales"]:
            skus[sku]["canales"][ch] = [0]*12
        skus[sku]["canales"][ch][mes-1] = qty

    # Serializar con totales
    filas = []
    for sku_data in skus.values():
        total_meses = [0]*12
        canales_out = []

        # Ordenar canales según CANALES_ORDEN, luego alfabético
        canales_sorted = sorted(
            sku_data["canales"].items(),
            key=lambda kv: (CANALES_ORDEN.index(kv[0]) if kv[0] in CANALES_ORDEN else 99, kv[0])
        )

        for ch, meses in canales_sorted:
            for i in range(12):
                total_meses[i] += meses[i]
            canales_out.append({"canal": ch, "meses": meses, "total": sum(meses)})

        precio_lp = sku_data["precio_lp"]
        costo     = sku_data["costo"]
        total_uds = sum(total_meses)

        filas.append({
            **{k: sku_data[k] for k in ["sku","descripcion","marca","categoria","subcategoria","tipo_producto","temporada","pareto"]},
            "precio_lp":    precio_lp,
            "costo":        costo,
            "meses_total":  total_meses,
            "total_uds":    total_uds,
            "venta_neta":   round(total_uds * precio_lp / IVA_FACTOR_FLOAT, 0) if precio_lp else 0,
            "margen_total": round(total_uds * (precio_lp/IVA_FACTOR_FLOAT - costo), 0) if precio_lp and costo else 0,
            "canales":      canales_out,
        })

    # Totales globales (sobre el universo completo, antes de paginar)
    tot_meses = [0]*12
    for f in filas:
        for i in range(12):
            tot_meses[i] += f["meses_total"][i]

    total_skus = len(filas)
    filas_paginadas = filas[offset: offset + limit]

    return {
        "canales_disponibles": CANALES_ORDEN,
        "meses_nombres": MESES,
        "total_skus": total_skus,
        "total_uds": sum(f["total_uds"] for f in filas),
        "totales_mes": tot_meses,
        "pagina": {"offset": offset, "limit": limit, "total": total_skus},
        "filas": filas_paginadas,
    }


class UpsertItem(BaseModel):
    sku:    str
    canal:  str
    mes:    int
    cantidad: int


class RecalcularRequest(BaseModel):
    crecimiento_pct: Optional[float] = None   # None = modelo estadístico; número = tasa fija

@router.post("/recalcular", dependencies=[Depends(require_rol("admin", "editor"))])
async def recalcular_forecast(req: RecalcularRequest):
    """Recalcula el forecast 2027. Si crecimiento_pct es None usa el modelo estadístico."""
    script = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'crear_forecast_2027.py'))
    if not os.path.exists(script):
        raise HTTPException(500, "crear_forecast_2027.py no encontrado")
    cmd = [sys.executable, script]
    if req.crecimiento_pct is not None:
        cmd += ['--crecimiento', str(req.crecimiento_pct)]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=os.path.dirname(script),
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise HTTPException(504, "Timeout al recalcular forecast")
        salida = (stdout or b"").decode("utf-8", errors="replace")
        return {"ok": proc.returncode == 0, "salida": salida[-3000:],
                "modo": "fijo" if req.crecimiento_pct is not None else "estadistico",
                "crecimiento_pct": req.crecimiento_pct}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/holt-winters", dependencies=[Depends(require_rol("admin", "editor"))])
async def ejecutar_holt_winters(solo_metricas: bool = False):
    """
    Ejecuta el modelo Holt-Winters aditivo (recomendación panel expertos jun-2026).
    - solo_metricas=false: genera forecast_hw_2027 + calcula MAPE/Bias
    - solo_metricas=true:  solo calcula métricas sin tocar el forecast
    """
    script = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'modelo_holt_winters.py'))
    if not os.path.exists(script):
        raise HTTPException(500, "modelo_holt_winters.py no encontrado")
    cmd = [sys.executable, script]
    if solo_metricas:
        cmd.append('--solo-metricas')
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=os.path.dirname(script),
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
        except asyncio.TimeoutError:
            proc.kill(); await proc.communicate()
            raise HTTPException(504, "Timeout ejecutando holt-winters")
        salida = (stdout or b"").decode("utf-8", errors="replace")
        return {
            "ok": proc.returncode == 0,
            "salida": salida[-3000:],
            "modo": "solo_metricas" if solo_metricas else "forecast_completo",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {e}")


@router.post("/calcular-intervalos", dependencies=[Depends(require_rol("admin", "editor"))])
async def calcular_intervalos():
    """Genera intervalos de confianza 80% y 95% para forecast 2026 y 2027."""
    script = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'calcular_intervalos.py'))
    if not os.path.exists(script):
        raise HTTPException(500, "calcular_intervalos.py no encontrado")
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=os.path.dirname(script),
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=180)
        except asyncio.TimeoutError:
            proc.kill(); await proc.communicate()
            raise HTTPException(504, "Timeout calculando intervalos")
        salida = (stdout or b"").decode("utf-8", errors="replace")
        return {"ok": proc.returncode == 0, "salida": salida[-3000:]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {e}")


@router.get("/intervalos/{sku}")
async def get_intervalos_sku(
    sku: str,
    anio: int = Query(2026),
    modelo: str = Query("ancla_si_macro"),
    db: AsyncSession = Depends(get_db),
):
    """Retorna los intervalos de confianza para un SKU/año/modelo específico."""
    rows = await db.execute(
        text("""
            SELECT mes, cantidad, lower_80, upper_80, lower_95, upper_95, mape_usado
            FROM forecast_intervalos
            WHERE sku = :sku AND anio = :anio AND modelo = :modelo
            ORDER BY mes
        """),
        {"sku": sku, "anio": anio, "modelo": modelo},
    )
    filas = [dict(r) for r in rows.mappings().all()]
    if not filas:
        raise HTTPException(404, f"No hay intervalos para {sku} / {anio} / {modelo}")
    return {"sku": sku, "anio": anio, "modelo": modelo, "meses": filas}


@router.post("/calcular-metricas", dependencies=[Depends(require_rol("admin", "editor"))])
async def calcular_metricas():
    """Calcula MAPE y Bias para ANCLA-SI-MACRO (2026 H1) y Holt-Winters (backtest 2025)."""
    script = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'calcular_metricas.py'))
    if not os.path.exists(script):
        raise HTTPException(500, "calcular_metricas.py no encontrado")
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=os.path.dirname(script),
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            proc.kill(); await proc.communicate()
            raise HTTPException(504, "Timeout calculando métricas")
        salida = (stdout or b"").decode("utf-8", errors="replace")
        return {"ok": proc.returncode == 0, "salida": salida[-3000:]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {e}")


@router.get("/metricas")
async def obtener_metricas(
    modelo: Optional[str] = Query(None, description="holt_winters | ancla_si_macro"),
    db: AsyncSession = Depends(get_db),
):
    """Retorna MAPE y Bias por SKU calculados en el último backtesting."""
    params: dict = {}
    where = ""
    if modelo:
        where = "WHERE modelo = :modelo"
        params["modelo"] = modelo
    rows = await db.execute(
        text("SELECT sku, modelo, mape, bias_pct, n_meses, updated_at FROM forecast_metricas"
             + (" WHERE modelo = :modelo" if modelo else "")
             + " ORDER BY mape DESC NULLS LAST"),
        params,
    )
    filas = [dict(r) for r in rows.mappings().all()]
    if not filas:
        return {"total": 0, "filas": []}

    mapas = [float(r["mape"]) for r in filas if r["mape"] is not None]
    bias  = [float(r["bias_pct"]) for r in filas if r["bias_pct"] is not None]
    return {
        "total": len(filas),
        "resumen": {
            "mape_promedio": round(sum(mapas) / len(mapas), 1) if mapas else None,
            "bias_promedio": round(sum(bias)  / len(bias),  1) if bias  else None,
        },
        "filas": filas,
    }


@router.post("/snapshot", dependencies=[Depends(require_rol("admin", "editor"))])
async def crear_snapshot(
    nombre: str = Body(...),
    descripcion: str = Body(""),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Guarda una copia inmutable del forecast 2027 actual como snapshot histórico."""
    # Leer tipo de cambio actual
    tc = await db.execute(text("SELECT usd_clp FROM tipo_cambio ORDER BY fecha DESC LIMIT 1"))
    tc_row = tc.mappings().first()
    usd_clp = float(tc_row["usd_clp"]) if tc_row else None

    # Leer forecast actual
    filas = await db.execute(text(
        "SELECT sku, canal, mes, cantidad FROM forecast_2027 ORDER BY sku, canal, mes"
    ))
    rows = filas.mappings().all()
    if not rows:
        raise HTTPException(400, "No hay datos en forecast_2027 para guardar")

    total_skus = len(set(r["sku"] for r in rows))
    total_uds  = sum(r["cantidad"] for r in rows)

    snap = await db.execute(text("""
        INSERT INTO forecast_snapshots (nombre, descripcion, usd_clp, total_skus, total_uds, creado_por)
        VALUES (:n, :d, :tc, :skus, :uds, :usr)
        RETURNING id
    """), {"n": nombre, "d": descripcion, "tc": usd_clp,
           "skus": total_skus, "uds": total_uds, "usr": current_user.email})
    snap_id = snap.scalar()

    for r in rows:
        await db.execute(text("""
            INSERT INTO forecast_snapshot_filas (snapshot_id, sku, canal, mes, cantidad)
            VALUES (:sid, :sku, :canal, :mes, :qty)
        """), {"sid": snap_id, "sku": r["sku"], "canal": r["canal"],
               "mes": r["mes"], "qty": r["cantidad"]})
    await db.commit()
    return {"ok": True, "snapshot_id": snap_id, "total_skus": total_skus, "total_uds": total_uds}


@router.get("/snapshots")
async def listar_snapshots(db: AsyncSession = Depends(get_db)):
    """Lista todos los snapshots guardados."""
    rows = await db.execute(text(
        "SELECT id, nombre, descripcion, crecimiento, usd_clp, total_skus, total_uds, creado_por, creado_en "
        "FROM forecast_snapshots ORDER BY creado_en DESC"
    ))
    return [dict(r) for r in rows.mappings().all()]


@router.delete("/snapshot/{snap_id}", dependencies=[Depends(require_rol("admin"))])
async def eliminar_snapshot(snap_id: int, db: AsyncSession = Depends(get_db)):
    await db.execute(text("DELETE FROM forecast_snapshots WHERE id=:id"), {"id": snap_id})
    await db.commit()
    return {"ok": True}


@router.post("/bulk-upsert", dependencies=[Depends(require_rol("editor"))])
async def bulk_upsert(items: List[UpsertItem], db: AsyncSession = Depends(get_db)):
    for item in items:
        await db.execute(text("""
            INSERT INTO forecast_2027 (sku, canal, mes, cantidad, ajuste_manual, updated_at)
            VALUES (:sku, :canal, :mes, :cantidad, TRUE, NOW())
            ON CONFLICT (sku, canal, mes) DO UPDATE
              SET cantidad = EXCLUDED.cantidad,
                  ajuste_manual = TRUE,
                  updated_at = NOW()
        """), {"sku": item.sku, "canal": item.canal, "mes": item.mes, "cantidad": item.cantidad})
    await db.commit()
    return {"ok": True, "updated": len(items)}


# ── HW Params endpoint ────────────────────────────────────────────────────────

class HWParamsIn(BaseModel):
    alpha: Optional[float] = Field(None, ge=0.0, le=1.0, description="Nivel (0-1, None=auto)")
    beta:  Optional[float] = Field(None, ge=0.0, le=1.0, description="Tendencia (0-1, None=auto)")
    gamma: Optional[float] = Field(None, ge=0.0, le=1.0, description="Estacionalidad (0-1, None=auto)")
    phi_cap:    Optional[float] = Field(None, ge=0.0, le=0.20, description="Cap phi +/- (0-0.20, default 0.03)")
    macro_sens: Optional[float] = Field(None, ge=0.0, le=0.05, description="Sensibilidad macro por 10 CLP (default 0.003)")


import importlib
import constants as _constants_mod

@router.get("/hw-params")
async def get_hw_params():
    """Retorna los parámetros actuales del modelo Holt-Winters y cap phi."""
    return {
        "alpha":      os.getenv("HW_ALPHA"),
        "beta":       os.getenv("HW_BETA"),
        "gamma":      os.getenv("HW_GAMMA"),
        "phi_cap":    os.getenv("PHI_CAP", str(PHI_CAP)),
        "macro_sens": os.getenv("MACRO_SENS", str(MACRO_SENS)),
        "nota": "None = optimización automática statsmodels. Modifica variables de entorno y reinicia el servidor para aplicar.",
    }


@router.put("/hw-params", dependencies=[Depends(require_rol("admin"))])
async def set_hw_params(params: HWParamsIn):
    """
    Actualiza los parámetros HW y cap phi en el archivo .env del backend.
    Requiere reinicio del servidor para aplicar.
    """
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")

    # Leer .env actual o crear vacío
    env_lines: list[str] = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            env_lines = f.readlines()

    def set_env_key(lines: list[str], key: str, value: Optional[float]) -> list[str]:
        val_str = str(value) if value is not None else "0"
        new_line = f"{key}={val_str}\n"
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = new_line
                return lines
        lines.append(new_line)
        return lines

    updates: dict = {}
    if params.alpha is not None:
        env_lines = set_env_key(env_lines, "HW_ALPHA", params.alpha)
        updates["HW_ALPHA"] = params.alpha
    if params.beta is not None:
        env_lines = set_env_key(env_lines, "HW_BETA", params.beta)
        updates["HW_BETA"] = params.beta
    if params.gamma is not None:
        env_lines = set_env_key(env_lines, "HW_GAMMA", params.gamma)
        updates["HW_GAMMA"] = params.gamma
    if params.phi_cap is not None:
        env_lines = set_env_key(env_lines, "PHI_CAP", params.phi_cap)
        updates["PHI_CAP"] = params.phi_cap
    if params.macro_sens is not None:
        env_lines = set_env_key(env_lines, "MACRO_SENS", params.macro_sens)
        updates["MACRO_SENS"] = params.macro_sens

    if not updates:
        raise HTTPException(400, "No se proporcionaron parámetros a actualizar")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(env_lines)

    return {
        "ok": True,
        "actualizados": updates,
        "advertencia": "Reinicia el servidor para aplicar los cambios.",
    }
