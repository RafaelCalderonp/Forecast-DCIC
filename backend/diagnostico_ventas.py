import asyncio, asyncpg, os

DB = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/forecast_dcic")

async def main():
    conn = await asyncpg.connect(DB)

    print("=== VENTAS EN BD POR AÑO/MES ===")
    rows = await conn.fetch("""
        SELECT EXTRACT(YEAR FROM fecha)::int AS anio,
               EXTRACT(MONTH FROM fecha)::int AS mes,
               COUNT(*) AS filas,
               SUM(cantidad) AS uds
        FROM ventas
        GROUP BY anio, mes
        ORDER BY anio, mes
    """)
    for r in rows:
        print(f"  {r['anio']}-{r['mes']:02d}  filas={r['filas']:>6,}  uds={r['uds']:>8,}")

    print("\n=== SYNC_LOG (últimos 60 registros) ===")
    logs = await conn.fetch("""
        SELECT fecha_inicio_datos, fecha_fin_datos, fuente, estado,
               registros_api, registros_upsert, error_detalle
        FROM sync_log
        ORDER BY fecha_inicio_datos, fuente
        LIMIT 120
    """)
    for r in logs:
        estado = r['estado']
        marca = '✓' if estado == 'completado' else ('✗' if estado == 'error' else '…')
        err = f" ERR: {r['error_detalle'][:60]}" if r['error_detalle'] else ""
        print(f"  {marca} {r['fecha_inicio_datos']} {r['fuente']:6} api={r['registros_api'] or 0:>5} upsert={r['registros_upsert'] or 0:>5}{err}")

    await conn.close()

asyncio.run(main())
