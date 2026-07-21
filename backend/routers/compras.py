"""
Reporte de Compras 2026
Lead time: 90 dias => una orden colocada hoy llega aprox. en 3 meses.
Semaforo:
  VERDE   = stock cubre forecast post-arribo
  AMARILLO = cubre >= 50%
  ROJO    = cubre < 50% (o cero stock vs demanda)
"""

from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from database import get_db
from auth import require_rol
from logger import get_logger
from constants import IVA_FACTOR_FLOAT, ALERTA_UMBRAL_CLP

log = get_logger("forecast_dcic.compras")
router = APIRouter()

LEAD_TIME = 90
ANIO_FC   = 2026


@router.get("")
async def reporte_compras(
    marca_id:      Optional[int]  = Query(None),
    categoria_id:  Optional[int]  = Query(None),
    temporada_id:  Optional[int]  = Query(None),
    pareto:        Optional[str]  = Query(None),
    solo_faltante: bool           = Query(False),
    limit:         int            = Query(500, ge=1, le=2000),
    offset:        int            = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    # Fechas calculadas en cada request, no al importar el módulo
    hoy          = date.today()
    fecha_arribo = hoy + timedelta(days=LEAD_TIME)
    mes_actual   = hoy.month
    mes_arribo   = fecha_arribo.month if fecha_arribo.year == ANIO_FC else 13

    # Filtros con parámetros enlazados — sin interpolación directa de strings
    params: dict = {"anio_fc": ANIO_FC, "mes_actual": mes_actual, "mes_arribo": mes_arribo, "iva": IVA_FACTOR_FLOAT}
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
    if pareto:
        where_parts.append("p.grupo_pareto = :pareto")
        params["pareto"] = pareto.upper()[:1]
    where_clause = ("AND " + " AND ".join(where_parts)) if where_parts else ""

    sql = f"""
    WITH stock_disp AS (
        -- Stock total = Stock Jun inicial + TODAS las llegadas confirmadas (ya ordenadas)
        SELECT
            s.sku,
            COALESCE(s.stock_jun,0)
            + COALESCE(s.llegada_jun,0) + COALESCE(s.llegada_jul,0)
            + COALESCE(s.llegada_ago,0) + COALESCE(s.llegada_sep,0)
            + COALESCE(s.llegada_oct,0) + COALESCE(s.llegada_nov,0)
            + COALESCE(s.llegada_dic,0)                      AS total,
            COALESCE(s.stock_jun,0)     AS stock_jun,
            COALESCE(s.llegada_jun,0)   AS leg_jun,
            COALESCE(s.llegada_jul,0)   AS leg_jul,
            COALESCE(s.llegada_ago,0)   AS leg_ago,
            COALESCE(s.llegada_sep,0)   AS leg_sep,
            COALESCE(s.llegada_oct,0)   AS leg_oct,
            COALESCE(s.llegada_nov,0)   AS leg_nov,
            COALESCE(s.llegada_dic,0)   AS leg_dic
        FROM stock s
    ),
    fc AS (
        -- Forecast de TODOS los SKUs (incluyendo packs, para poder explotar su demanda)
        SELECT sku,
            SUM(CASE WHEN mes=6  THEN cantidad ELSE 0 END) m06,
            SUM(CASE WHEN mes=7  THEN cantidad ELSE 0 END) m07,
            SUM(CASE WHEN mes=8  THEN cantidad ELSE 0 END) m08,
            SUM(CASE WHEN mes=9  THEN cantidad ELSE 0 END) m09,
            SUM(CASE WHEN mes=10 THEN cantidad ELSE 0 END) m10,
            SUM(CASE WHEN mes=11 THEN cantidad ELSE 0 END) m11,
            SUM(CASE WHEN mes=12 THEN cantidad ELSE 0 END) m12,
            SUM(CASE WHEN mes >= :mes_actual THEN cantidad ELSE 0 END) fc_restante,
            SUM(CASE WHEN mes >= :mes_actual AND mes < :mes_arribo THEN cantidad ELSE 0 END) fc_pre,
            SUM(CASE WHEN mes >= :mes_arribo THEN cantidad ELSE 0 END) fc_post
        FROM forecast
        WHERE anio = :anio_fc
        GROUP BY sku
    ),
    pack_extra AS (
        -- Demanda adicional sobre cada componente generada por los packs que lo contienen
        SELECT pc.producto_sku AS sku,
            SUM(COALESCE(fp.m06,0) * pc.cantidad) extra_m06,
            SUM(COALESCE(fp.m07,0) * pc.cantidad) extra_m07,
            SUM(COALESCE(fp.m08,0) * pc.cantidad) extra_m08,
            SUM(COALESCE(fp.m09,0) * pc.cantidad) extra_m09,
            SUM(COALESCE(fp.m10,0) * pc.cantidad) extra_m10,
            SUM(COALESCE(fp.m11,0) * pc.cantidad) extra_m11,
            SUM(COALESCE(fp.m12,0) * pc.cantidad) extra_m12,
            SUM(COALESCE(fp.fc_pre,0)  * pc.cantidad) extra_pre,
            SUM(COALESCE(fp.fc_post,0) * pc.cantidad) extra_post
        FROM pack_componentes pc
        JOIN fc fp ON fp.sku = pc.pack_sku
        GROUP BY pc.producto_sku
    )
    SELECT
        p.sku,
        m.nombre  AS marca,
        c.nombre  AS categoria,
        s.nombre  AS subcategoria,
        p.tipo_producto,
        t.nombre  AS temporada,
        p.descripcion,
        p.grupo_pareto                      AS pareto,
        p.comentario,
        CASE WHEN p.precio_venta_neto > 0 THEN p.precio_venta_neto
             ELSE ROUND(p.precio_venta_bruto / :iva, 2) END AS precio_neto,
        p.costo_unitario_neto,
        COALESCE(sd.total,0)   AS stock_disponible,
        COALESCE(sd.stock_jun,0) AS stock_jun,
        COALESCE(sd.leg_jun,0) AS leg_jun,
        COALESCE(sd.leg_jul,0) AS leg_jul,
        COALESCE(sd.leg_ago,0) AS leg_ago,
        COALESCE(sd.leg_sep,0) AS leg_sep,
        COALESCE(sd.leg_oct,0) AS leg_oct,
        COALESCE(sd.leg_nov,0) AS leg_nov,
        COALESCE(sd.leg_dic,0) AS leg_dic,
        -- Forecast propio + demanda generada por packs
        COALESCE(fc.m06,0) + COALESCE(pe.extra_m06,0) m06,
        COALESCE(fc.m07,0) + COALESCE(pe.extra_m07,0) m07,
        COALESCE(fc.m08,0) + COALESCE(pe.extra_m08,0) m08,
        COALESCE(fc.m09,0) + COALESCE(pe.extra_m09,0) m09,
        COALESCE(fc.m10,0) + COALESCE(pe.extra_m10,0) m10,
        COALESCE(fc.m11,0) + COALESCE(pe.extra_m11,0) m11,
        COALESCE(fc.m12,0) + COALESCE(pe.extra_m12,0) m12,
        COALESCE(fc.fc_restante,0) fc_restante,
        COALESCE(fc.fc_pre,0)  + COALESCE(pe.extra_pre,0)  AS fc_pre,
        COALESCE(fc.fc_post,0) + COALESCE(pe.extra_post,0) AS fc_post,
        -- demanda de packs (para mostrar en UI)
        COALESCE(pe.extra_pre,0)  AS extra_pre,
        COALESCE(pe.extra_post,0) AS extra_post,
        -- stock que sobra despues de cubrir periodo pre-arribo (con demanda total)
        GREATEST(0, COALESCE(sd.total,0)
            - (COALESCE(fc.fc_pre,0) + COALESCE(pe.extra_pre,0))) AS stock_post_pre,
        -- unidades a comprar = faltante en periodo post-arribo (con demanda total)
        GREATEST(0, (COALESCE(fc.fc_post,0) + COALESCE(pe.extra_post,0))
                    - GREATEST(0, COALESCE(sd.total,0)
                        - (COALESCE(fc.fc_pre,0) + COALESCE(pe.extra_pre,0)))) AS a_comprar,
        CASE
            WHEN (COALESCE(fc.fc_post,0) + COALESCE(pe.extra_post,0)) = 0 THEN 0
            WHEN GREATEST(0, COALESCE(sd.total,0)
                    - (COALESCE(fc.fc_pre,0) + COALESCE(pe.extra_pre,0)))
                 >= (COALESCE(fc.fc_post,0) + COALESCE(pe.extra_post,0)) THEN 0
            WHEN GREATEST(0, COALESCE(sd.total,0)
                    - (COALESCE(fc.fc_pre,0) + COALESCE(pe.extra_pre,0)))
                 >= (COALESCE(fc.fc_post,0) + COALESCE(pe.extra_post,0)) * 0.5 THEN 1
            ELSE 2
        END AS semaforo
    FROM productos p
    LEFT JOIN marcas       m  ON m.id = p.marca_id
    LEFT JOIN categorias   c  ON c.id = p.categoria_id
    LEFT JOIN subcategorias s ON s.id = p.subcategoria_id
    LEFT JOIN temporadas   t  ON t.id = p.temporada_id
    LEFT JOIN stock_disp sd ON sd.sku = p.sku
    LEFT JOIN fc            ON fc.sku = p.sku
    LEFT JOIN pack_extra pe ON pe.sku = p.sku
    WHERE p.activo = TRUE AND p.es_pack = FALSE {where_clause}
    ORDER BY semaforo DESC, a_comprar DESC
    """

    # Tipo de cambio más reciente para conversión a USD
    tc_row = await db.execute(
        text("SELECT usd_clp FROM tipo_cambio ORDER BY fecha DESC LIMIT 1")
    )
    tc = tc_row.scalar_one_or_none()
    usd_clp = float(tc) if tc else None

    result = await db.execute(text(sql), params)
    rows = result.mappings().all()

    filas = []
    for r in rows:
        comentario = r["comentario"]
        a_comprar = 0 if comentario == "Descontinuar" else int(r["a_comprar"])
        semaforo  = 0 if comentario == "Descontinuar" else int(r["semaforo"])
        if solo_faltante and a_comprar == 0:
            continue
        costo   = float(r["costo_unitario_neto"] or 0)
        precio  = float(r["precio_neto"] or 0)
        fc_post = int(r["fc_post"])
        filas.append({
            "sku":            r["sku"],
            "marca":          r["marca"],
            "categoria":      r["categoria"],
            "subcategoria":   r["subcategoria"],
            "tipo_producto":  r["tipo_producto"],
            "temporada":      r["temporada"],
            "descripcion":    r["descripcion"],
            "pareto":         r["pareto"],
            "precio_neto":    precio,
            "costo_unitario": costo,
            "stock_jun":       int(r["stock_jun"]),
            "stock_disponible": int(r["stock_disponible"]),
            "llegadas": {
                "Jun": int(r["leg_jun"]), "Jul": int(r["leg_jul"]), "Ago": int(r["leg_ago"]),
                "Sep": int(r["leg_sep"]), "Oct": int(r["leg_oct"]), "Nov": int(r["leg_nov"]),
                "Dic": int(r["leg_dic"]),
            },
            "fc_restante":    int(r["fc_restante"]),
            "fc_pre":         int(r["fc_pre"]),
            "fc_post":        fc_post,
            "extra_pre":      int(r["extra_pre"]),
            "extra_post":     int(r["extra_post"]),
            "a_comprar":      a_comprar,
            "meses": {
                "Jun": int(r["m06"]), "Jul": int(r["m07"]), "Ago": int(r["m08"]),
                "Sep": int(r["m09"]), "Oct": int(r["m10"]), "Nov": int(r["m11"]),
                "Dic": int(r["m12"]),
            },
            "comentario":      comentario,
            "semaforo":        semaforo,
            "importe_compra":  costo * a_comprar if comentario != "Descontinuar" else 0,
            "venta_neta_fc":   precio * fc_post / IVA_FACTOR_FLOAT if fc_post else 0,
            "costo_usd":       round(costo / usd_clp, 2) if usd_clp and costo else None,
            "importe_usd":     round(costo * a_comprar / usd_clp, 0) if usd_clp and costo and a_comprar else None,
        })

    total_importe = sum(f["importe_compra"] for f in filas)
    total_importe_usd = round(total_importe / usd_clp, 0) if usd_clp else None
    total_productos = len(filas)
    filas_paginadas = filas[offset: offset + limit]
    return {
        "meta": {
            "fecha_calculo":   hoy.isoformat(),
            "lead_time_dias":  LEAD_TIME,
            "fecha_arribo":    fecha_arribo.isoformat(),
            "mes_arribo":      mes_arribo,
            "mes_actual":      mes_actual,
            "total_productos": total_productos,
            "total_faltante":  sum(f["a_comprar"] for f in filas),
            "total_importe":     total_importe,
            "total_importe_usd": total_importe_usd,
            "usd_clp":           usd_clp,
            "rojos":           sum(1 for f in filas if f["semaforo"] == 2),
            "amarillos":       sum(1 for f in filas if f["semaforo"] == 1),
            "verdes":          sum(1 for f in filas if f["semaforo"] == 0),
            "pagina":          {"offset": offset, "limit": limit, "total": total_productos},
        },
        "filas": filas_paginadas,
    }


@router.get("/alertas-rojo")
async def alertas_rojo(
    umbral: float = Query(None, description="Valor mínimo de importe_compra en CLP para incluir en alerta. Por defecto usa ALERTA_UMBRAL_CLP del entorno."),
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna SKUs en semáforo ROJO cuyo importe de compra supera el umbral configurado.
    Útil para notificaciones proactivas y alertas automáticas post-sync.
    El umbral es configurable vía query param o variable de entorno ALERTA_UMBRAL_CLP (default: 500.000 CLP).
    """
    umbral_efectivo = umbral if umbral is not None else ALERTA_UMBRAL_CLP
    hoy          = date.today()
    fecha_arribo = hoy + timedelta(days=LEAD_TIME)
    mes_actual   = hoy.month
    mes_arribo   = fecha_arribo.month if fecha_arribo.year == ANIO_FC else 13

    rows = await db.execute(text("""
        WITH fc AS (
            SELECT sku,
                SUM(CASE WHEN mes < :mes_actual THEN cantidad ELSE 0 END) AS fc_pre,
                SUM(CASE WHEN mes >= :mes_arribo AND anio = :anio_fc THEN cantidad ELSE 0 END) AS fc_post
            FROM forecast_2027
            WHERE anio = :anio_fc
            GROUP BY sku
        ),
        sd AS (
            SELECT sku,
                COALESCE(stock_base,0)+COALESCE(stock_jun,0)+COALESCE(stock_full_ml,0)+COALESCE(stock_full_fala,0)
                +COALESCE(bodega_transito,0)+COALESCE(por_arribar,0)+COALESCE(pi,0) AS total
            FROM stock
        )
        SELECT p.sku, p.descripcion, p.grupo_pareto AS pareto,
               p.costo_unitario_neto AS costo,
               COALESCE(sd.total,0) AS stock_total,
               COALESCE(fc.fc_pre,0) AS fc_pre,
               COALESCE(fc.fc_post,0) AS fc_post,
               GREATEST(0, COALESCE(fc.fc_post,0)
                    - GREATEST(0, COALESCE(sd.total,0) - COALESCE(fc.fc_pre,0))) AS a_comprar
        FROM productos p
        LEFT JOIN fc ON fc.sku = p.sku
        LEFT JOIN sd ON sd.sku = p.sku
        WHERE p.activo = TRUE AND p.es_pack = FALSE
          AND COALESCE(fc.fc_post,0) > 0
          AND GREATEST(0, COALESCE(sd.total,0) - COALESCE(fc.fc_pre,0))
                < COALESCE(fc.fc_post,0) * 0.5
        ORDER BY (GREATEST(0, COALESCE(fc.fc_post,0)
                    - GREATEST(0, COALESCE(sd.total,0) - COALESCE(fc.fc_pre,0)))
                  * COALESCE(p.costo_unitario_neto,0)) DESC
    """), {"anio_fc": ANIO_FC, "mes_actual": mes_actual, "mes_arribo": mes_arribo})

    alertas = []
    for r in rows.mappings().all():
        a_comprar    = int(r["a_comprar"])
        costo        = float(r["costo"] or 0)
        importe      = round(a_comprar * costo, 0)
        if importe >= umbral_efectivo:
            alertas.append({
                "sku":         r["sku"],
                "descripcion": r["descripcion"],
                "pareto":      r["pareto"],
                "a_comprar":   a_comprar,
                "costo":       costo,
                "importe_clp": importe,
            })

    log.info(f"alertas-rojo umbral={umbral_efectivo:,.0f} → {len(alertas)} SKUs")
    return {
        "umbral_clp":    umbral_efectivo,
        "fecha_calculo": hoy.isoformat(),
        "total_alertas": len(alertas),
        "alertas":       alertas,
    }


@router.post("/actualizar-costos", dependencies=[Depends(require_rol("admin"))])
async def actualizar_costos_desde_ventas(db: AsyncSession = Depends(get_db)):
    """
    Pobla productos.costo_unitario_neto con el promedio ponderado
    de costo_unitario_clp de las ventas sincronizadas.
    Solo admin puede ejecutarlo.
    """
    result = await db.execute(text("""
        UPDATE productos p
        SET costo_unitario_neto = v.costo_avg,
            updated_at = NOW()
        FROM (
            SELECT sku,
                   ROUND(SUM(costo_unitario_clp * cantidad) / NULLIF(SUM(cantidad), 0), 2) AS costo_avg
            FROM ventas
            WHERE costo_unitario_clp IS NOT NULL AND costo_unitario_clp > 0
              AND cantidad > 0
            GROUP BY sku
        ) v
        WHERE p.sku = v.sku AND v.costo_avg IS NOT NULL
    """))
    await db.commit()
    actualizados = result.rowcount

    # Cuantos siguen sin costo
    sin_costo = await db.execute(
        text("SELECT COUNT(*) FROM productos WHERE costo_unitario_neto IS NULL OR costo_unitario_neto = 0")
    )
    return {
        "actualizados": actualizados,
        "sin_costo": sin_costo.scalar(),
    }
