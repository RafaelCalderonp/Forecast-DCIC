"""
Intervalos de Confianza del Forecast — DCIC SpA
================================================
Genera bandas lower/upper para 80% y 95% de confianza por SKU/mes.

Método por modelo:
- ancla_si_macro: usa MAPE individual del SKU (o global si no hay)
  lower_80 = fc * (1 - 1.28 * mape/100)
  upper_80 = fc * (1 + 1.28 * mape/100)
  lower_95 = fc * (1 - 1.96 * mape/100)
  upper_95 = fc * (1 + 1.96 * mape/100)

- holt_winters: usa simulación Monte Carlo de statsmodels (más preciso)
  Si falla, usa el mismo método MAPE.

Uso:
  python calcular_intervalos.py
"""
import asyncio
import asyncpg
import os
from statistics import mean

DB = dict(host='localhost', port=5432, user='postgres', password=os.getenv("PGPASSWORD", "postgres"), database='forecast_dcic')

# Z-scores para intervalos
Z_80 = 1.28
Z_95 = 1.96

# MAPE global de respaldo (calculado en sesión anterior)
MAPE_GLOBAL_FALLBACK = 64.6


def intervalo_mape(fc: int, mape_pct: float) -> dict:
    """Calcula intervalos basados en MAPE como proxy de desviación estándar."""
    sigma = mape_pct / 100
    return {
        "lower_80": max(0, round(fc * (1 - Z_80 * sigma))),
        "upper_80": max(0, round(fc * (1 + Z_80 * sigma))),
        "lower_95": max(0, round(fc * (1 - Z_95 * sigma))),
        "upper_95": max(0, round(fc * (1 + Z_95 * sigma))),
    }


async def main():
    conn = await asyncpg.connect(**DB)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS forecast_intervalos (
            sku          VARCHAR(50)  NOT NULL,
            anio         SMALLINT     NOT NULL,
            mes          SMALLINT     NOT NULL CHECK (mes BETWEEN 1 AND 12),
            modelo       VARCHAR(50)  NOT NULL,
            cantidad     INTEGER      NOT NULL,
            lower_80     INTEGER,
            upper_80     INTEGER,
            lower_95     INTEGER,
            upper_95     INTEGER,
            mape_usado   NUMERIC(8,2),
            updated_at   TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (sku, anio, mes, modelo)
        )
    """)

    # ── MAPE por SKU desde forecast_metricas ─────────────────────────────────
    mape_rows = await conn.fetch(
        "SELECT sku, modelo, mape FROM forecast_metricas WHERE mape IS NOT NULL"
    )
    mape_ancla: dict[str, float] = {}
    mape_hw:    dict[str, float] = {}
    for r in mape_rows:
        if r['modelo'] == 'ancla_si_macro':
            mape_ancla[r['sku']] = float(r['mape'])
        elif r['modelo'] == 'holt_winters':
            mape_hw[r['sku']] = float(r['mape'])

    mape_global_ancla = mean(mape_ancla.values()) if mape_ancla else MAPE_GLOBAL_FALLBACK
    mape_global_hw    = mean(mape_hw.values())    if mape_hw    else MAPE_GLOBAL_FALLBACK

    print(f"MAPE global ANCLA-SI-MACRO: {mape_global_ancla:.1f}%  ({len(mape_ancla)} SKUs con MAPE propio)")
    print(f"MAPE global Holt-Winters:   {mape_global_hw:.1f}%  ({len(mape_hw)} SKUs con MAPE propio)")

    # ── 1. Intervalos Forecast 2026 (ANCLA-SI-MACRO) ─────────────────────────
    fc_rows = await conn.fetch("""
        SELECT f.sku, f.mes, f.cantidad
        FROM forecast f
        JOIN productos p ON p.sku = f.sku
        WHERE f.anio = 2026 AND p.activo = TRUE AND p.es_pack = FALSE
    """)

    insertados_ancla = 0
    for r in fc_rows:
        sku = r['sku']
        mes = r['mes']
        fc  = int(r['cantidad'])
        mape = mape_ancla.get(sku, mape_global_ancla)
        iv = intervalo_mape(fc, mape)
        await conn.execute("""
            INSERT INTO forecast_intervalos
              (sku, anio, mes, modelo, cantidad, lower_80, upper_80, lower_95, upper_95, mape_usado)
            VALUES ($1, 2026, $2, 'ancla_si_macro', $3, $4, $5, $6, $7, $8)
            ON CONFLICT (sku, anio, mes, modelo) DO UPDATE
              SET cantidad=$3, lower_80=$4, upper_80=$5, lower_95=$6, upper_95=$7,
                  mape_usado=$8, updated_at=NOW()
        """, sku, mes, fc, iv['lower_80'], iv['upper_80'], iv['lower_95'], iv['upper_95'], round(mape, 2))
        insertados_ancla += 1

    # ── 2. Intervalos Forecast 2027 Holt-Winters con simulación ──────────────
    hw_rows = await conn.fetch(
        "SELECT sku, mes, cantidad FROM forecast_hw_2027"
    )

    # Cargar historia para simulación HW
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
    """)
    hist: dict[str, dict] = {}
    for r in hist_rows:
        hist.setdefault(r['sku'], {}).setdefault(r['anio'], {})[r['mes']] = r['qty']

    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        import numpy as np
        import warnings
        hw_simulacion = True
    except ImportError:
        hw_simulacion = False
        print("statsmodels no disponible — usando MAPE para intervalos HW")

    # Agrupar forecast HW por SKU
    hw_by_sku: dict[str, dict] = {}
    for r in hw_rows:
        hw_by_sku.setdefault(r['sku'], {})[r['mes']] = int(r['cantidad'])

    insertados_hw = 0
    for sku, meses_fc in hw_by_sku.items():
        # Construir serie histórica
        datos = hist.get(sku, {})
        anio_inicio = min(datos) if datos else None
        serie = []
        if anio_inicio:
            for anio in range(anio_inicio, 2026):
                for mes in range(1, 13):
                    serie.append(max(datos.get(anio, {}).get(mes, 0.0), 0.01))

        # Intentar simulación Monte Carlo con HW
        sim_intervals: dict[int, dict] | None = None
        if hw_simulacion and len(serie) >= 18:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    modelo = ExponentialSmoothing(
                        serie,
                        trend='add', seasonal='add', seasonal_periods=12,
                        initialization_method='estimated',
                    ).fit(optimized=True)
                    # Simulación: 1000 trayectorias de 12 pasos
                    sims = modelo.simulate(12, repetitions=1000, error='add')
                    sims_arr = np.array(sims)
                    sim_intervals = {}
                    for i in range(12):
                        col = sims_arr[i] if sims_arr.ndim > 1 else sims_arr[:, i]
                        sim_intervals[i + 1] = {
                            "lower_80": max(0, int(np.percentile(col, 10))),
                            "upper_80": max(0, int(np.percentile(col, 90))),
                            "lower_95": max(0, int(np.percentile(col, 2.5))),
                            "upper_95": max(0, int(np.percentile(col, 97.5))),
                        }
            except Exception:
                sim_intervals = None

        for mes, fc in meses_fc.items():
            if sim_intervals and mes in sim_intervals:
                iv = sim_intervals[mes]
                mape_usado = None
            else:
                mape = mape_hw.get(sku, mape_global_hw)
                iv = intervalo_mape(fc, mape)
                mape_usado = round(mape, 2)

            await conn.execute("""
                INSERT INTO forecast_intervalos
                  (sku, anio, mes, modelo, cantidad, lower_80, upper_80, lower_95, upper_95, mape_usado)
                VALUES ($1, 2027, $2, 'holt_winters', $3, $4, $5, $6, $7, $8)
                ON CONFLICT (sku, anio, mes, modelo) DO UPDATE
                  SET cantidad=$3, lower_80=$4, upper_80=$5, lower_95=$6, upper_95=$7,
                      mape_usado=$8, updated_at=NOW()
            """, sku, mes, fc, iv['lower_80'], iv['upper_80'], iv['lower_95'], iv['upper_95'], mape_usado)
            insertados_hw += 1

    await conn.close()

    print(f"\n{'='*60}")
    print(f"  INTERVALOS DE CONFIANZA — DCIC SpA")
    print(f"{'='*60}")
    print(f"  ANCLA-SI-MACRO 2026:  {insertados_ancla:>6,} filas")
    print(f"  Holt-Winters   2027:  {insertados_hw:>6,} filas")
    print(f"  Método HW: {'simulación Monte Carlo' if hw_simulacion else 'MAPE-based'}")
    print()


if __name__ == '__main__':
    asyncio.run(main())
