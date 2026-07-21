"""
Forecast 2027 — Modelo Holt-Winters Aditivo
=============================================
Panel de expertos DCIC — Jun-2026
Recomendación: ExponentialSmoothing(trend='add', seasonal='add', seasonal_periods=12)

Usa datos históricos 2023-2026 por SKU (ventas totales por mes, todos los canales).
Genera 12 meses de forecast 2027 y calcula métricas de validación (MAPE, Bias)
mediante backtesting dejando 2026 como holdout.

Uso:
  python modelo_holt_winters.py              # genera forecast 2027 + métricas
  python modelo_holt_winters.py --solo-metricas   # solo calcula métricas, no escribe forecast
"""
import asyncio
import asyncpg
import argparse
import os
from statistics import mean
from constants import HW_ALPHA, HW_BETA, HW_GAMMA

DB = dict(host='localhost', port=5432, user='postgres', password=os.getenv("PGPASSWORD", "postgres"), database='forecast_dcic')

# Mínimo de meses de historia para forecast 2027
MIN_MESES_HW = 18
# Mínimo para backtesting (más permisivo: train=12, holdout=12)
MIN_MESES_BACKTEST = 13

# Parámetros del modelo — configurables via variables de entorno:
#   HW_TREND=add|mul  HW_SEASONAL=add|mul  HW_PERIODS=12
HW_TREND    = os.getenv("HW_TREND",    'add')
HW_SEASONAL = os.getenv("HW_SEASONAL", 'add')
HW_PERIODS  = int(os.getenv("HW_PERIODS", '12'))


def ajustar_holt_winters(serie: list[float]) -> list[float] | None:
    """
    Ajusta ExponentialSmoothing aditivo y retorna forecast de 12 pasos.
    Retorna None si la serie es insuficiente o el modelo falla.
    """
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        import warnings
        import numpy as np

        if len(serie) < MIN_MESES_HW:
            return None
        if sum(serie) == 0:
            return None

        # Reemplazar ceros con un valor pequeño para evitar problemas numéricos
        serie_clean = [max(v, 0.01) for v in serie]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            modelo = ExponentialSmoothing(
                serie_clean,
                trend=HW_TREND,
                seasonal=HW_SEASONAL,
                seasonal_periods=HW_PERIODS,
                initialization_method='estimated',
            ).fit(
                optimized=True,
                smoothing_level=HW_ALPHA,
                smoothing_trend=HW_BETA,
                smoothing_seasonal=HW_GAMMA,
            )

        forecast = modelo.forecast(12)
        # Clamp a >= 0 (demanda no puede ser negativa)
        return [max(0.0, float(v)) for v in forecast]

    except Exception:
        return None


def calcular_mape(reales: list[float], predichos: list[float]) -> float | None:
    """MAPE excluyendo meses con demanda real = 0."""
    errores = []
    for r, p in zip(reales, predichos):
        if r > 0:
            errores.append(abs(r - p) / r)
    return mean(errores) * 100 if errores else None


def calcular_bias(reales: list[float], predichos: list[float]) -> float | None:
    """Bias = (predicho - real) / real en promedio. >0 sobreestima, <0 subestima."""
    errores = []
    for r, p in zip(reales, predichos):
        if r > 0:
            errores.append((p - r) / r)
    return mean(errores) * 100 if errores else None


async def main(solo_metricas: bool = False):
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing  # noqa
    except ImportError:
        print("ERROR: instala statsmodels:  pip install statsmodels")
        return

    conn = await asyncpg.connect(**DB)

    # ── Crear tablas si no existen ────────────────────────────────────────────

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS forecast_hw_2027 (
            sku        VARCHAR(50) NOT NULL REFERENCES productos(sku) ON DELETE CASCADE,
            mes        SMALLINT NOT NULL CHECK (mes BETWEEN 1 AND 12),
            cantidad   INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (sku, mes)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS forecast_metricas (
            sku          VARCHAR(50) NOT NULL,
            modelo       VARCHAR(50) NOT NULL,
            mape         NUMERIC(8,2),
            bias_pct     NUMERIC(8,2),
            n_meses      INTEGER,
            updated_at   TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (sku, modelo)
        )
    """)

    # ── Cargar ventas mensuales por SKU (todos los canales) ───────────────────
    # Usamos 2023, 2024, 2025, 2026 como historia completa

    rows = await conn.fetch("""
        SELECT v.sku,
               EXTRACT(YEAR  FROM v.fecha)::int AS anio,
               EXTRACT(MONTH FROM v.fecha)::int AS mes,
               SUM(v.cantidad - v.unidades_devueltas)::float AS qty
        FROM ventas v
        JOIN productos p ON p.sku = v.sku
        WHERE v.estado_orden = 'Regular'
          AND EXTRACT(YEAR FROM v.fecha) BETWEEN 2023 AND 2025
          AND p.activo = TRUE AND p.es_pack = FALSE
        GROUP BY v.sku,
                 EXTRACT(YEAR FROM v.fecha),
                 EXTRACT(MONTH FROM v.fecha)
        HAVING SUM(v.cantidad - v.unidades_devueltas) > 0
        ORDER BY v.sku, anio, mes
    """)

    # Organizar en dict: {sku: {(anio, mes): qty}}
    historico: dict[str, dict] = {}
    for r in rows:
        historico.setdefault(r['sku'], {})[(r['anio'], r['mes'])] = r['qty']

    # ── Para backtesting: cargar ventas reales 2026 ───────────────────────────
    rows_2026 = await conn.fetch("""
        SELECT v.sku,
               EXTRACT(MONTH FROM v.fecha)::int AS mes,
               SUM(v.cantidad - v.unidades_devueltas)::float AS qty
        FROM ventas v
        JOIN productos p ON p.sku = v.sku
        WHERE v.estado_orden = 'Regular'
          AND EXTRACT(YEAR FROM v.fecha) = 2026
          AND p.activo = TRUE AND p.es_pack = FALSE
        GROUP BY v.sku, EXTRACT(MONTH FROM v.fecha)
        HAVING SUM(v.cantidad - v.unidades_devueltas) > 0
    """)
    ventas_2026: dict[str, dict] = {}
    for r in rows_2026:
        ventas_2026.setdefault(r['sku'], {})[r['mes']] = r['qty']

    # ── Procesar cada SKU ─────────────────────────────────────────────────────

    insertados = 0
    skus_ok = 0
    skus_sin_datos = 0
    mapas_todos: list[float] = []
    bias_todos:  list[float] = []

    for sku, datos in historico.items():
        # Construir serie temporal mensual continua desde el primer mes disponible
        anios = sorted(set(a for a, m in datos))
        if not anios:
            continue

        # Serie desde ene del primer año hasta dic 2025
        anio_inicio = min(anios)
        serie: list[float] = []
        for anio in range(anio_inicio, 2026):
            for mes in range(1, 13):
                serie.append(datos.get((anio, mes), 0.0))

        if len(serie) < MIN_MESES_HW:
            skus_sin_datos += 1
            continue

        # ── Backtesting: entrenar con hasta dic-2024, predecir 2025 ──────────
        serie_train = serie[:-12] if len(serie) >= MIN_MESES_BACKTEST else None
        if serie_train and len(serie_train) >= MIN_MESES_BACKTEST - 12:
            fc_2025 = ajustar_holt_winters(serie_train)
            if fc_2025:
                reales_2025 = [datos.get((2025, m), 0.0) for m in range(1, 13)]
                mape = calcular_mape(reales_2025, fc_2025)
                bias = calcular_bias(reales_2025, fc_2025)
                if mape is not None:
                    mapas_todos.append(mape)
                    await conn.execute("""
                        INSERT INTO forecast_metricas (sku, modelo, mape, bias_pct, n_meses)
                        VALUES ($1, 'holt_winters', $2, $3, $4)
                        ON CONFLICT (sku, modelo) DO UPDATE
                          SET mape=$2, bias_pct=$3, n_meses=$4, updated_at=NOW()
                    """, sku, round(mape, 2), round(bias, 2) if bias else None, len(reales_2025))
                if bias is not None:
                    bias_todos.append(bias)

        if solo_metricas:
            skus_ok += 1
            continue

        # ── Forecast 2027: entrenar con toda la historia hasta dic-2025 ───────
        fc_2027 = ajustar_holt_winters(serie)
        if not fc_2027:
            skus_sin_datos += 1
            continue

        for mes_idx, qty_float in enumerate(fc_2027):
            mes = mes_idx + 1
            qty = max(0, round(qty_float))
            if qty > 0:
                await conn.execute("""
                    INSERT INTO forecast_hw_2027 (sku, mes, cantidad)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (sku, mes) DO UPDATE
                      SET cantidad=$3, updated_at=NOW()
                """, sku, mes, qty)
                insertados += 1

        skus_ok += 1

    await conn.close()

    # ── Resumen ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  FORECAST 2027 — Holt-Winters Aditivo")
    print(f"  trend='{HW_TREND}'  seasonal='{HW_SEASONAL}'  periods={HW_PERIODS}")
    print(f"{'='*60}")
    print(f"  SKUs procesados con HW:    {skus_ok:>6,}")
    print(f"  SKUs sin datos suficientes:{skus_sin_datos:>6,}")
    if not solo_metricas:
        print(f"  Filas insertadas (2027):   {insertados:>6,}")
    if mapas_todos:
        print(f"\n  Backtesting (2025 holdout):")
        print(f"    MAPE promedio:  {mean(mapas_todos):.1f}%")
        print(f"    Bias promedio:  {mean(bias_todos):.1f}%  (+ sobreestima, - subestima)")
        print(f"    SKUs con métrica: {len(mapas_todos)}")
    print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--solo-metricas', action='store_true',
                        help='Solo calcula MAPE/Bias sin escribir forecast_hw_2027')
    args = parser.parse_args()
    asyncio.run(main(solo_metricas=args.solo_metricas))
