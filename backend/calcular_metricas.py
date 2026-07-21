"""
Métricas MAPE y Bias — Forecast DCIC
======================================
Compara predicciones vs ventas reales para dos modelos:

1. ancla_si_macro: forecast tabla 2026 vs ventas reales 2026 (H1: Ene-Jun)
2. holt_winters:   backtesting HW prediciendo 2025 vs ventas reales 2025

Guarda resultados en forecast_metricas.
Uso:
  python calcular_metricas.py
"""
import asyncio
import asyncpg
import os
from statistics import mean

DB = dict(host='localhost', port=5432, user='postgres', password=os.getenv("PGPASSWORD", "postgres"), database='forecast_dcic')

MIN_SERIE = 1  # mínimo de meses con demanda real > 0 para calcular MAPE


def mape(reales: list[float], predichos: list[float]) -> float | None:
    errores = [abs(r - p) / r for r, p in zip(reales, predichos) if r > 0]
    return round(mean(errores) * 100, 2) if errores else None


def bias(reales: list[float], predichos: list[float]) -> float | None:
    errores = [(p - r) / r for r, p in zip(reales, predichos) if r > 0]
    return round(mean(errores) * 100, 2) if errores else None


async def main():
    conn = await asyncpg.connect(**DB)

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

    # ── 1. ANCLA-SI-MACRO: forecast 2026 vs ventas reales 2026 H1 ────────────
    print("Calculando MAPE modelo ANCLA-SI-MACRO (forecast 2026 vs real 2026 H1)...")

    fc_rows = await conn.fetch("""
        SELECT f.sku, f.mes, f.cantidad AS fc
        FROM forecast f
        JOIN productos p ON p.sku = f.sku
        WHERE f.anio = 2026
          AND f.mes BETWEEN 1 AND 6
          AND p.activo = TRUE AND p.es_pack = FALSE
        ORDER BY f.sku, f.mes
    """)

    ventas_rows = await conn.fetch("""
        SELECT v.sku,
               EXTRACT(MONTH FROM v.fecha)::int AS mes,
               SUM(v.cantidad - v.unidades_devueltas)::float AS qty
        FROM ventas v
        JOIN productos p ON p.sku = v.sku
        WHERE v.estado_orden = 'Regular'
          AND EXTRACT(YEAR FROM v.fecha) = 2026
          AND EXTRACT(MONTH FROM v.fecha) BETWEEN 1 AND 6
          AND p.activo = TRUE AND p.es_pack = FALSE
        GROUP BY v.sku, EXTRACT(MONTH FROM v.fecha)
    """)

    # Organizar
    fc_map: dict[str, dict] = {}
    for r in fc_rows:
        fc_map.setdefault(r['sku'], {})[r['mes']] = float(r['fc'])

    real_map: dict[str, dict] = {}
    for r in ventas_rows:
        real_map.setdefault(r['sku'], {})[r['mes']] = r['qty']

    skus_ancla = set(fc_map) & set(real_map)
    mapas_ancla: list[float] = []
    bias_ancla:  list[float] = []
    insertados_ancla = 0

    for sku in skus_ancla:
        meses = list(range(1, 7))
        reales   = [real_map[sku].get(m, 0.0) for m in meses]
        predichos = [fc_map[sku].get(m, 0.0) for m in meses]

        m_val = mape(reales, predichos)
        b_val = bias(reales, predichos)
        n = sum(1 for r in reales if r > 0)

        if m_val is None or n < MIN_SERIE:
            continue

        await conn.execute("""
            INSERT INTO forecast_metricas (sku, modelo, mape, bias_pct, n_meses)
            VALUES ($1, 'ancla_si_macro', $2, $3, $4)
            ON CONFLICT (sku, modelo) DO UPDATE
              SET mape=$2, bias_pct=$3, n_meses=$4, updated_at=NOW()
        """, sku, m_val, b_val, n)
        mapas_ancla.append(m_val)
        if b_val is not None:
            bias_ancla.append(b_val)
        insertados_ancla += 1

    # ── 2. Holt-Winters: backtesting 2025 ────────────────────────────────────
    print("Calculando MAPE modelo Holt-Winters (backtesting 2025)...")

    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        import warnings

        hist_rows = await conn.fetch("""
            SELECT v.sku,
                   EXTRACT(YEAR  FROM v.fecha)::int AS anio,
                   EXTRACT(MONTH FROM v.fecha)::int AS mes,
                   SUM(v.cantidad - v.unidades_devueltas)::float AS qty
            FROM ventas v
            JOIN productos p ON p.sku = v.sku
            WHERE v.estado_orden = 'Regular'
              AND EXTRACT(YEAR FROM v.fecha) BETWEEN 2023 AND 2025
              AND p.activo = TRUE AND p.es_pack = FALSE
            GROUP BY v.sku, EXTRACT(YEAR FROM v.fecha), EXTRACT(MONTH FROM v.fecha)
            HAVING SUM(v.cantidad - v.unidades_devueltas) > 0
        """)

        hist: dict[str, dict] = {}
        for r in hist_rows:
            hist.setdefault(r['sku'], {}).setdefault(r['anio'], {})[r['mes']] = r['qty']

        mapas_hw: list[float] = []
        bias_hw:  list[float] = []
        insertados_hw = 0

        for sku, datos in hist.items():
            if 2025 not in datos:
                continue

            anio_inicio = min(datos)
            serie: list[float] = []
            for anio in range(anio_inicio, 2025):
                for mes in range(1, 13):
                    serie.append(datos.get(anio, {}).get(mes, 0.0))

            if len(serie) < 12:
                continue

            serie_clean = [max(v, 0.01) for v in serie]
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    modelo = ExponentialSmoothing(
                        serie_clean,
                        trend='add',
                        seasonal='add',
                        seasonal_periods=12,
                        initialization_method='estimated',
                    ).fit(optimized=True)
                fc_2025 = [max(0.0, float(v)) for v in modelo.forecast(12)]
            except Exception:
                continue

            reales_2025 = [datos[2025].get(m, 0.0) for m in range(1, 13)]
            m_val = mape(reales_2025, fc_2025)
            b_val = bias(reales_2025, fc_2025)
            n = sum(1 for r in reales_2025 if r > 0)

            if m_val is None or n < MIN_SERIE:
                continue

            await conn.execute("""
                INSERT INTO forecast_metricas (sku, modelo, mape, bias_pct, n_meses)
                VALUES ($1, 'holt_winters', $2, $3, $4)
                ON CONFLICT (sku, modelo) DO UPDATE
                  SET mape=$2, bias_pct=$3, n_meses=$4, updated_at=NOW()
            """, sku, m_val, b_val, n)
            mapas_hw.append(m_val)
            if b_val is not None:
                bias_hw.append(b_val)
            insertados_hw += 1

    except ImportError:
        print("  statsmodels no disponible — saltando métricas HW")
        mapas_hw, bias_hw, insertados_hw = [], [], 0

    await conn.close()

    # ── Resumen ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  MÉTRICAS DE FORECAST — DCIC SpA")
    print(f"{'='*60}")
    print(f"\n  Modelo ANCLA-SI-MACRO (forecast 2026 vs real H1-2026):")
    print(f"    SKUs evaluados: {insertados_ancla:>5,}")
    if mapas_ancla:
        print(f"    MAPE promedio:  {mean(mapas_ancla):>6.1f}%")
        print(f"    Bias promedio:  {mean(bias_ancla):>+6.1f}%  (+ sobreestima, - subestima)")

    print(f"\n  Modelo Holt-Winters (backtesting 2025 holdout):")
    print(f"    SKUs evaluados: {insertados_hw:>5,}")
    if mapas_hw:
        print(f"    MAPE promedio:  {mean(mapas_hw):>6.1f}%")
        print(f"    Bias promedio:  {mean(bias_hw):>+6.1f}%")

    if mapas_ancla and mapas_hw:
        mejor = "ANCLA-SI-MACRO" if mean(mapas_ancla) < mean(mapas_hw) else "Holt-Winters"
        print(f"\n  Modelo más preciso: {mejor}")
    print()


if __name__ == '__main__':
    asyncio.run(main())
