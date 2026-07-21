import asyncio, asyncpg, os

async def main():
    conn = await asyncpg.connect(
        host='localhost', port=5432,
        user='postgres', password=os.getenv("PGPASSWORD", "postgres"),
        database='forecast_dcic'
    )
    # Ver valores distintos de estado_orden y su conteo
    rows = await conn.fetch("""
        SELECT estado_orden, COUNT(*) as n,
               MIN(fecha) as desde, MAX(fecha) as hasta
        FROM ventas
        GROUP BY estado_orden
        ORDER BY n DESC
    """)
    print("--- estado_orden ---")
    for r in rows:
        print(dict(r))

    # Ver años disponibles
    rows2 = await conn.fetch("""
        SELECT date_part('year', fecha)::int as anio, COUNT(*) as n
        FROM ventas GROUP BY 1 ORDER BY 1
    """)
    print("\n--- años ---")
    for r in rows2:
        print(dict(r))

    await conn.close()

asyncio.run(main())
