"""
Agrega UNIQUE constraint a ventas y elimina duplicados.
Ejecutar UNA VEZ, idealmente cuando el sync no está corriendo.

La clave única es: sku + fecha + canal + fuente + tipo_linea
(suficiente para identificar una línea de venta única)
"""
import asyncio, asyncpg, os

DB = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/forecast_dcic")

async def main():
    conn = await asyncpg.connect(DB)

    # 1. Ver cuántos registros hay ahora
    total = await conn.fetchval("SELECT COUNT(*) FROM ventas")
    print(f"Total registros actuales: {total:,}")

    # 2. Verificar si ya existe el índice
    existe = await conn.fetchval("""
        SELECT COUNT(*) FROM pg_indexes
        WHERE tablename = 'ventas' AND indexname = 'uq_ventas_linea'
    """)
    if existe:
        print("Indice uq_ventas_linea ya existe. Nada que hacer.")
        await conn.close()
        return

    # 3. Eliminar duplicados: conservar el registro con el id más bajo
    dup = await conn.fetchval("""
        SELECT COUNT(*) FROM ventas v
        WHERE v.id > (
            SELECT MIN(v2.id) FROM ventas v2
            WHERE v2.sku = v.sku
              AND v2.fecha = v.fecha
              AND COALESCE(v2.canal, '') = COALESCE(v.canal, '')
              AND COALESCE(v2.fuente, '') = COALESCE(v.fuente, '')
              AND COALESCE(v2.tipo_linea, '') = COALESCE(v.tipo_linea, '')
        )
    """)
    print(f"Duplicados detectados: {dup:,}")

    if dup > 0:
        await conn.execute("""
            DELETE FROM ventas
            WHERE id IN (
                SELECT v.id FROM ventas v
                WHERE v.id > (
                    SELECT MIN(v2.id) FROM ventas v2
                    WHERE v2.sku = v.sku
                      AND v2.fecha = v.fecha
                      AND COALESCE(v2.canal, '') = COALESCE(v.canal, '')
                      AND COALESCE(v2.fuente, '') = COALESCE(v.fuente, '')
                      AND COALESCE(v2.tipo_linea, '') = COALESCE(v.tipo_linea, '')
                )
            )
        """)
        total2 = await conn.fetchval("SELECT COUNT(*) FROM ventas")
        print(f"Duplicados eliminados. Registros restantes: {total2:,}")

    # 4. Crear índice único
    await conn.execute("""
        CREATE UNIQUE INDEX uq_ventas_linea
        ON ventas (sku, fecha, COALESCE(canal,''), COALESCE(fuente,''), COALESCE(tipo_linea,''))
    """)
    print("Indice uq_ventas_linea creado OK.")

    # 5. Verificar años disponibles
    years = await conn.fetch("""
        SELECT EXTRACT(YEAR FROM fecha)::int AS anio, COUNT(*) AS filas
        FROM ventas GROUP BY anio ORDER BY anio
    """)
    print("\nResumen por año:")
    for r in years:
        print(f"  {r['anio']}: {r['filas']:,} filas")

    await conn.close()

asyncio.run(main())
