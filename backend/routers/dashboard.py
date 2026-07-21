"""
Dashboard Ejecutivo — KPIs consolidados Forecast DCIC
Endpoint único que reúne métricas clave para visión de directorio.
"""
from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from database import get_db
from logger import get_logger
from constants import ALERTA_UMBRAL_CLP

log = get_logger("forecast_dcic.dashboard")
router = APIRouter()


@router.get("")
async def dashboard_kpis(db: AsyncSession = Depends(get_db)):
    """
    KPIs ejecutivos consolidados:
    - Disponibilidad por canal (% SKUs VERDE/AMARILLO/ROJO)
    - MAPE promedio del modelo y distribución de calidad
    - Valor total de compras pendientes (ROJO) en CLP
    - Alertas críticas (compras > umbral ALERTA_UMBRAL_CLP)
    - Estado tipo de cambio
    - Resumen sync ERP más reciente
    """
    hoy = date.today()
    fecha_arribo = hoy + timedelta(days=90)
    mes_actual = hoy.month
    mes_arribo = fecha_arribo.month if fecha_arribo.year == 2026 else 13

    # ── 1. Disponibilidad por semáforo ────────────────────────────────────────
    semaforo_row = await db.execute(text("""
        WITH fc AS (
            SELECT
                f.sku,
                f.canal,
                COALESCE(SUM(f.cantidad) FILTER (
                    WHERE f.mes >= :mes_actual AND f.mes <= :mes_arribo
                ), 0) AS fc_periodo,
                COALESCE(SUM(f.cantidad) FILTER (
                    WHERE f.mes > :mes_arribo
                ), 0) AS fc_post_arribo
            FROM forecast_2027 f
            JOIN productos p ON p.sku = f.sku
            WHERE f.anio = 2027 AND p.activo = TRUE AND p.es_pack = FALSE
            GROUP BY f.sku, f.canal
        ),
        stock_actual AS (
            SELECT s.sku, s.canal, s.cantidad AS stock
            FROM stock s
            JOIN productos p ON p.sku = s.sku
            WHERE p.activo = TRUE AND p.es_pack = FALSE
        ),
        semaforo AS (
            SELECT
                fc.sku,
                fc.canal,
                COALESCE(sa.stock, 0) AS stock,
                fc.fc_periodo,
                fc.fc_post_arribo,
                CASE
                    WHEN fc.fc_post_arribo = 0 THEN 'VERDE'
                    WHEN COALESCE(sa.stock, 0) - fc.fc_periodo >= fc.fc_post_arribo THEN 'VERDE'
                    WHEN (COALESCE(sa.stock, 0) - fc.fc_periodo)::float / NULLIF(fc.fc_post_arribo, 0) >= 0.5 THEN 'AMARILLO'
                    ELSE 'ROJO'
                END AS color
            FROM fc
            LEFT JOIN stock_actual sa ON sa.sku = fc.sku AND sa.canal = fc.canal
        )
        SELECT
            color,
            COUNT(*) AS cantidad
        FROM semaforo
        GROUP BY color
        ORDER BY color
    """), {"mes_actual": mes_actual, "mes_arribo": mes_arribo})

    semaforo_data = {r["color"]: r["cantidad"] for r in semaforo_row.mappings().all()}
    total_semaforo = sum(semaforo_data.values()) or 1
    disponibilidad = {
        "verde":    {"cantidad": semaforo_data.get("VERDE", 0),
                     "pct": round(semaforo_data.get("VERDE", 0) / total_semaforo * 100, 1)},
        "amarillo": {"cantidad": semaforo_data.get("AMARILLO", 0),
                     "pct": round(semaforo_data.get("AMARILLO", 0) / total_semaforo * 100, 1)},
        "rojo":     {"cantidad": semaforo_data.get("ROJO", 0),
                     "pct": round(semaforo_data.get("ROJO", 0) / total_semaforo * 100, 1)},
        "total_skus_canal": total_semaforo,
    }

    # ── 2. MAPE del modelo ─────────────────────────────────────────────────────
    mape_row = await db.execute(text("""
        SELECT
            ROUND(AVG(mape)::numeric, 1)   AS mape_promedio,
            ROUND(MIN(mape)::numeric, 1)   AS mape_min,
            ROUND(MAX(mape)::numeric, 1)   AS mape_max,
            ROUND(AVG(bias_pct)::numeric, 1) AS bias_promedio,
            COUNT(*) AS skus_con_metrica,
            COUNT(*) FILTER (WHERE mape < 20) AS mape_bueno,
            COUNT(*) FILTER (WHERE mape BETWEEN 20 AND 40) AS mape_regular,
            COUNT(*) FILTER (WHERE mape > 40) AS mape_alto
        FROM forecast_metricas
        WHERE modelo = 'holt_winters'
    """))
    mape_data = mape_row.mappings().first() or {}
    modelo_kpis = {
        "mape_promedio":    float(mape_data.get("mape_promedio") or 0),
        "mape_min":         float(mape_data.get("mape_min") or 0),
        "mape_max":         float(mape_data.get("mape_max") or 0),
        "bias_promedio":    float(mape_data.get("bias_promedio") or 0),
        "skus_con_metrica": int(mape_data.get("skus_con_metrica") or 0),
        "calidad": {
            "bueno":   int(mape_data.get("mape_bueno") or 0),    # MAPE < 20%
            "regular": int(mape_data.get("mape_regular") or 0),  # MAPE 20-40%
            "alto":    int(mape_data.get("mape_alto") or 0),     # MAPE > 40%
        },
    }

    # ── 3. Valor compras pendientes (ROJO) ────────────────────────────────────
    compras_row = await db.execute(text("""
        WITH fc_post AS (
            SELECT
                f.sku,
                SUM(f.cantidad) AS fc_post_arribo
            FROM forecast_2027 f
            JOIN productos p ON p.sku = f.sku
            WHERE f.anio = 2027 AND f.mes > :mes_arribo
              AND p.activo = TRUE AND p.es_pack = FALSE
            GROUP BY f.sku
        ),
        stock_total AS (
            SELECT sku, SUM(cantidad) AS stock_total
            FROM stock
            GROUP BY sku
        ),
        fc_periodo AS (
            SELECT
                f.sku,
                SUM(f.cantidad) AS fc_periodo
            FROM forecast_2027 f
            WHERE f.anio = 2027 AND f.mes BETWEEN :mes_actual AND :mes_arribo
            GROUP BY f.sku
        ),
        rojo AS (
            SELECT
                fp.sku,
                fp.fc_post_arribo,
                COALESCE(st.stock_total, 0) - COALESCE(fper.fc_periodo, 0) AS stock_disponible,
                p.precio_costo_neto,
                GREATEST(
                    fp.fc_post_arribo - GREATEST(
                        COALESCE(st.stock_total, 0) - COALESCE(fper.fc_periodo, 0), 0
                    ), 0
                ) AS unidades_faltantes
            FROM fc_post fp
            JOIN productos p ON p.sku = fp.sku
            LEFT JOIN stock_total st ON st.sku = fp.sku
            LEFT JOIN fc_periodo fper ON fper.sku = fp.sku
            WHERE COALESCE(st.stock_total, 0) - COALESCE(fper.fc_periodo, 0) <
                  fp.fc_post_arribo * 0.5
        )
        SELECT
            COUNT(*) AS skus_rojo,
            ROUND(SUM(unidades_faltantes * COALESCE(precio_costo_neto, 0))::numeric, 0)
                AS valor_compras_pendientes_clp,
            ROUND(SUM(unidades_faltantes * COALESCE(precio_costo_neto, 0))::numeric / NULLIF(
                (SELECT usd_clp FROM tipo_cambio ORDER BY fecha DESC LIMIT 1), 0
            ), 0) AS valor_compras_pendientes_usd
        FROM rojo
    """), {"mes_actual": mes_actual, "mes_arribo": mes_arribo})

    compras_data = compras_row.mappings().first() or {}
    compras_kpis = {
        "skus_rojo":                     int(compras_data.get("skus_rojo") or 0),
        "valor_compras_pendientes_clp":  float(compras_data.get("valor_compras_pendientes_clp") or 0),
        "valor_compras_pendientes_usd":  float(compras_data.get("valor_compras_pendientes_usd") or 0),
    }

    # ── 4. Alertas críticas (ROJO con importe > umbral) ───────────────────────
    alertas_row = await db.execute(text("""
        WITH faltantes AS (
            SELECT
                p.sku, p.nombre,
                GREATEST(
                    SUM(f.cantidad) FILTER (WHERE f.mes > :mes_arribo) -
                    GREATEST(
                        (SELECT COALESCE(SUM(cantidad),0) FROM stock WHERE sku = p.sku)
                        - COALESCE(SUM(f.cantidad) FILTER (WHERE f.mes BETWEEN :mes_actual AND :mes_arribo), 0)
                    , 0)
                , 0) AS unidades_faltantes,
                p.precio_costo_neto
            FROM forecast_2027 f
            JOIN productos p ON p.sku = f.sku
            WHERE f.anio = 2027 AND p.activo = TRUE AND p.es_pack = FALSE
            GROUP BY p.sku, p.nombre, p.precio_costo_neto
        )
        SELECT COUNT(*) AS total_alertas,
               ROUND(AVG(unidades_faltantes * COALESCE(precio_costo_neto,0))::numeric, 0) AS importe_promedio_clp
        FROM faltantes
        WHERE unidades_faltantes * COALESCE(precio_costo_neto, 0) >= :umbral
    """), {"mes_actual": mes_actual, "mes_arribo": mes_arribo, "umbral": ALERTA_UMBRAL_CLP})

    alertas_data = alertas_row.mappings().first() or {}
    alertas_kpis = {
        "umbral_clp":      ALERTA_UMBRAL_CLP,
        "total_alertas":   int(alertas_data.get("total_alertas") or 0),
        "importe_promedio_clp": float(alertas_data.get("importe_promedio_clp") or 0),
    }

    # ── 5. Estado tipo de cambio ───────────────────────────────────────────────
    tc_row = await db.execute(
        text("SELECT fecha, usd_clp, fuente FROM tipo_cambio ORDER BY fecha DESC LIMIT 1")
    )
    tc = tc_row.mappings().first()
    if tc:
        dias_atraso = (hoy - tc["fecha"]).days
        tc_kpi = {
            "fecha":       tc["fecha"].isoformat(),
            "usd_clp":     float(tc["usd_clp"]),
            "fuente":      tc["fuente"],
            "dias_atraso": dias_atraso,
            "estado":      "ok" if dias_atraso <= 3 else "desactualizado",
        }
    else:
        tc_kpi = {"fecha": None, "usd_clp": None, "fuente": None, "dias_atraso": None, "estado": "sin_dato"}

    # ── 6. Último sync ERP ─────────────────────────────────────────────────────
    sync_row = await db.execute(text("""
        SELECT fecha_sync, insertados, actualizados, errores_fk, errores_otros, estado
        FROM sync_log
        ORDER BY id DESC LIMIT 1
    """))
    sync = sync_row.mappings().first()
    sync_kpi = dict(sync) if sync else {"estado": "sin_registro"}
    if sync_kpi.get("fecha_sync"):
        sync_kpi["fecha_sync"] = sync_kpi["fecha_sync"].isoformat()

    return {
        "generado_en":   hoy.isoformat(),
        "disponibilidad": disponibilidad,
        "modelo":         modelo_kpis,
        "compras":        compras_kpis,
        "alertas":        alertas_kpis,
        "tipo_cambio":    tc_kpi,
        "ultimo_sync":    sync_kpi,
    }
