import asyncio, asyncpg, os

DB = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/forecast_dcic")

async def main():
    conn = await asyncpg.connect(DB)

    print("=== COBERTURA DE CAMPOS DE PRECIO ===")
    r = await conn.fetchrow("""
        SELECT COUNT(*) AS total,
               COUNT(valor_unitario_bruto)  AS con_valor_unit,
               COUNT(precio_total_bruto)    AS con_precio_lista
        FROM ventas WHERE estado_orden = 'Regular'
    """)
    print(f"  Total Regular:           {r['total']:>10,}")
    print(f"  Con valor_unitario_bruto:{r['con_valor_unit']:>10,} ({r['con_valor_unit']/r['total']:.1%})")
    print(f"  Con precio_total_bruto:  {r['con_precio_lista']:>10,} ({r['con_precio_lista']/r['total']:.1%})")

    print("\n=== VENTA DICIEMBRE 2024 (distintas fórmulas) ===")
    r2 = await conn.fetchrow("""
        SELECT
            SUM(cantidad - unidades_devueltas)                                         AS uds_netas,
            ROUND(SUM((cantidad-unidades_devueltas) * COALESCE(valor_unitario_bruto,0))) AS venta_valor_unit,
            ROUND(SUM(COALESCE(precio_total_bruto, 0)))                                AS venta_precio_lista,
            ROUND(SUM(COALESCE(precio_total_bruto, 0)) / 1.19)                        AS venta_precio_lista_neto
        FROM ventas
        WHERE estado_orden = 'Regular'
          AND EXTRACT(YEAR FROM fecha) = 2024
          AND EXTRACT(MONTH FROM fecha) = 12
    """)
    print(f"  Uds netas dic-2024:             {r2['uds_netas']:>15,}")
    print(f"  Venta usando valor_unit×qty:    ${r2['venta_valor_unit']:>15,.0f}")
    print(f"  Venta usando precio_lista SUM:  ${r2['venta_precio_lista']:>15,.0f}")
    print(f"  → Neto (÷1.19):                ${r2['venta_precio_lista_neto']:>15,.0f}")

    print("\n=== VENTA TOTAL 2024 (comparar con Excel $17.3B) ===")
    r3 = await conn.fetchrow("""
        SELECT
            ROUND(SUM((cantidad-unidades_devueltas) * COALESCE(valor_unitario_bruto,0))) AS venta_valor_unit,
            ROUND(SUM(COALESCE(precio_total_bruto, 0)))                                  AS venta_precio_lista
        FROM ventas
        WHERE estado_orden = 'Regular'
          AND EXTRACT(YEAR FROM fecha) = 2024
    """)
    print(f"  Fórmula actual (valor_unit×qty): ${r3['venta_valor_unit']:>15,.0f}")
    print(f"  precio_total_bruto sumado:        ${r3['venta_precio_lista']:>15,.0f}")

    print("\n=== MUESTRA: primeras 5 filas dic-2024 ===")
    rows = await conn.fetch("""
        SELECT sku, canal, fecha, cantidad, unidades_devueltas,
               precio_total_bruto, valor_unitario_bruto
        FROM ventas
        WHERE estado_orden='Regular'
          AND EXTRACT(YEAR FROM fecha)=2024
          AND EXTRACT(MONTH FROM fecha)=12
        LIMIT 5
    """)
    for r in rows:
        print(f"  {r['sku']} | {r['canal']} | cant={r['cantidad']} | precio_lista={r['precio_total_bruto']} | valor_unit={r['valor_unitario_bruto']}")

    await conn.close()

asyncio.run(main())
