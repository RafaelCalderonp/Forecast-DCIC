"""
ForecastService — orquesta el engine HW con la base de datos.
No contiene lógica de modelo; eso vive en forecast_engine.py.
"""

import pandas as pd
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, delete

from forecast.engine.forecast_engine import (
    preparar_serie_temporal,
    calibrar_holt_winters,
    aplicar_lift_factors,
    aplicar_restriccion_stock,
    calcular_metricas_precision,
    calcular_segmentacion_abc_xyz,
    generar_ordenes_compra_sugeridas,
)
from forecast.models.forecast_models import (
    ForecastResultado,
    SegmentacionAbcXyz,
    LiftFactor,
    OrdenCompraSugerida,
    AlertaForecast,
)


class ForecastService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # Carga de datos base
    # ─────────────────────────────────────────────────────────────────────────

    async def _cargar_ventas_df(self) -> pd.DataFrame:
        """Carga todas las ventas activas como DataFrame."""
        q = text("""
            SELECT sku, canal, fecha, cantidad, valor_unitario_bruto AS precio_neto
            FROM ventas
            WHERE activo = TRUE AND cantidad > 0
            ORDER BY fecha
        """)
        result = await self.db.execute(q)
        rows = result.fetchall()
        return pd.DataFrame(rows, columns=["sku", "canal", "fecha", "cantidad", "precio_neto"])

    async def _cargar_lift_factors(self) -> list:
        """Carga todos los lift factors vigentes como lista de dicts."""
        result = await self.db.execute(select(LiftFactor))
        return [
            {
                "canal": lf.canal,
                "sku_pattern": lf.sku_pattern,
                "fecha_inicio": lf.fecha_inicio,
                "fecha_fin": lf.fecha_fin,
                "multiplicador": float(lf.multiplicador),
            }
            for lf in result.scalars().all()
        ]

    async def _cargar_stock_df(self) -> pd.DataFrame:
        """Carga stock disponible por SKU."""
        q = text("SELECT sku, COALESCE(stock_base, 0) AS stock_base FROM stock")
        result = await self.db.execute(q)
        rows = result.fetchall()
        return pd.DataFrame(rows, columns=["sku", "stock_base"])

    async def _skus_activos(self) -> list:
        """Retorna lista de SKUs con ventas en los últimos 12 meses."""
        q = text("""
            SELECT DISTINCT v.sku, v.canal
            FROM ventas v
            JOIN productos p ON p.sku = v.sku
            WHERE p.activo = TRUE
              AND v.activo = TRUE
              AND v.fecha >= CURRENT_DATE - INTERVAL '12 months'
            ORDER BY v.sku, v.canal
        """)
        result = await self.db.execute(q)
        return result.fetchall()

    # ─────────────────────────────────────────────────────────────────────────
    # Cálculo individual SKU-Canal
    # ─────────────────────────────────────────────────────────────────────────

    async def calcular_sku_canal(
        self,
        sku: str,
        canal: str,
        horizonte_meses: int = 6,
        df_ventas: pd.DataFrame = None,
        lift_factors: list = None,
        df_stock: pd.DataFrame = None,
    ) -> dict:
        """
        Calcula el forecast completo (3 capas) para un SKU-Canal.
        Devuelve dict con periodos y valores de cada capa.
        """
        if df_ventas is None:
            df_ventas = await self._cargar_ventas_df()
        if lift_factors is None:
            lift_factors = await self._cargar_lift_factors()
        if df_stock is None:
            df_stock = await self._cargar_stock_df()

        try:
            serie = preparar_serie_temporal(df_ventas, sku, canal)
        except ValueError:
            return {"sku": sku, "canal": canal, "error": "serie_insuficiente"}

        resultado = calibrar_holt_winters(serie, horizonte_meses=horizonte_meses, sku=sku, canal=canal)

        # Stock disponible para Capa 3
        stock_row = df_stock[df_stock["sku"] == sku]
        stock_disponible = int(stock_row["stock_base"].iloc[0]) if not stock_row.empty else None

        filas = []
        for periodo_str, base in zip(resultado.periodos, resultado.forecast_base):
            mult, ajustado = aplicar_lift_factors(base, sku, canal, periodo_str, lift_factors)
            final, dci = aplicar_restriccion_stock(ajustado, stock_disponible)
            filas.append({
                "sku": sku,
                "canal": canal,
                "periodo": periodo_str,
                "forecast_base": base,
                "lift_aplicado": mult,
                "forecast_ajustado": ajustado,
                "stock_disponible": stock_disponible,
                "forecast_final": final,
                "dci": dci,
                "modelo_version": resultado.modelo_version,
                "parametros_hw": resultado.parametros_hw,
            })

        return {"sku": sku, "canal": canal, "filas": filas, "error": None}

    # ─────────────────────────────────────────────────────────────────────────
    # Persistencia en DB
    # ─────────────────────────────────────────────────────────────────────────

    async def guardar_forecast(self, filas: list) -> int:
        """
        Upsert de resultados de forecast en forecast_resultados.
        Elimina períodos existentes del mismo SKU-canal antes de insertar.
        Retorna cantidad de filas insertadas.
        """
        if not filas:
            return 0

        sku = filas[0]["sku"]
        canal = filas[0]["canal"]
        periodos = [f["periodo"] for f in filas]

        # Eliminar forecast anterior para estos períodos
        from datetime import date as date_type
        def _to_date(s):
            return date_type.fromisoformat(s) if isinstance(s, str) else s

        periodo_min = _to_date(min(periodos))
        periodo_max = _to_date(max(periodos))
        await self.db.execute(
            text("""
                DELETE FROM forecast_resultados
                WHERE sku = :sku AND canal = :canal
                  AND periodo BETWEEN :p_min AND :p_max
            """),
            {"sku": sku, "canal": canal, "p_min": periodo_min, "p_max": periodo_max},
        )

        for f in filas:
            fr = ForecastResultado(
                sku=f["sku"],
                canal=f["canal"],
                periodo=_to_date(f["periodo"]),
                forecast_base=f["forecast_base"],
                lift_aplicado=f["lift_aplicado"],
                forecast_ajustado=f["forecast_ajustado"],
                stock_disponible=f.get("stock_disponible"),
                forecast_final=f["forecast_final"],
                dci=min(f["dci"], 99999.99) if f.get("dci") is not None else None,
                modelo_version=f["modelo_version"],
                parametros_hw=f["parametros_hw"],
            )
            self.db.add(fr)

        await self.db.flush()
        return len(filas)

    # ─────────────────────────────────────────────────────────────────────────
    # Cálculo masivo
    # ─────────────────────────────────────────────────────────────────────────

    async def calcular_todos_los_skus(self, horizonte_meses: int = 6) -> tuple:
        """
        Calcula HW para todos los SKUs activos.
        Retorna (n_ok, n_errores).
        """
        skus_canales = await self._skus_activos()
        df_ventas = await self._cargar_ventas_df()
        lift_factors = await self._cargar_lift_factors()
        df_stock = await self._cargar_stock_df()

        n_ok = 0
        n_err = 0

        for sku, canal in skus_canales:
            try:
                resultado = await self.calcular_sku_canal(
                    sku, canal, horizonte_meses,
                    df_ventas=df_ventas,
                    lift_factors=lift_factors,
                    df_stock=df_stock,
                )
                if resultado.get("error"):
                    n_err += 1
                    continue
                await self.guardar_forecast(resultado["filas"])
                n_ok += 1
            except Exception:
                n_err += 1
                try:
                    await self.db.rollback()
                except Exception:
                    pass

        await self.db.commit()
        return n_ok, n_err

    # ─────────────────────────────────────────────────────────────────────────
    # Refresh vista materializada
    # ─────────────────────────────────────────────────────────────────────────

    async def refresh_vista(self) -> None:
        # CONCURRENTLY falla en vista vacía; intentar primero, fallback sin CONCURRENTLY
        try:
            await self.db.execute(
                text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_forecast_resumen")
            )
        except Exception:
            await self.db.rollback()
            await self.db.execute(
                text("REFRESH MATERIALIZED VIEW mv_forecast_resumen")
            )
        await self.db.commit()

    # ─────────────────────────────────────────────────────────────────────────
    # Segmentación ABC-XYZ
    # ─────────────────────────────────────────────────────────────────────────

    async def recalcular_segmentacion(
        self,
        periodo_inicio: str,
        periodo_fin: str,
    ) -> int:
        df_ventas = await self._cargar_ventas_df()
        df_seg = calcular_segmentacion_abc_xyz(df_ventas, periodo_inicio, periodo_fin)

        if df_seg.empty:
            return 0

        from datetime import date as date_type
        pi = date_type.fromisoformat(periodo_inicio) if isinstance(periodo_inicio, str) else periodo_inicio
        pf = date_type.fromisoformat(periodo_fin) if isinstance(periodo_fin, str) else periodo_fin

        # Eliminar segmentación del mismo período
        await self.db.execute(
            text("DELETE FROM segmentacion_abc_xyz WHERE periodo_inicio = :pi"),
            {"pi": pi},
        )

        for _, row in df_seg.iterrows():
            seg = SegmentacionAbcXyz(
                sku=row["sku"],
                canal=row["canal"],
                periodo_inicio=pi,
                periodo_fin=pf,
                clase_abc=row["clase_abc"],
                clase_xyz=row["clase_xyz"],
                coeficiente_variacion=row.get("coeficiente_variacion"),
                revenue_total=row.get("revenue_total"),
                unidades_total=row.get("unidades_total"),
                pct_revenue_acum=row.get("pct_revenue_acum"),
            )
            self.db.add(seg)

        await self.db.commit()
        return len(df_seg)
