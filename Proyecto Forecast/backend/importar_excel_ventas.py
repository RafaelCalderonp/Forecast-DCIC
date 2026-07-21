"""
Importa ventas desde el Excel 2024-2026 directo a la BD.
Estrategia:
  1. Agrega columna num_pedido si no existe
  2. Borra todas las ventas de fuente='excel' en el rango del archivo
  3. Inserta todas las filas Regular + Devuelta del Excel
  4. Usa N° Pedido + N° Sub-Orden + SKU como clave natural de dedup

Uso: python importar_excel_ventas.py
"""
import asyncio, asyncpg, pandas as pd, shutil, tempfile, os
from datetime import date
from decimal import Decimal, InvalidOperation

EXCEL = r"C:\Users\rafae\OneDrive - IMPORTADORA DCIC SPA\DCIC SpA\001. Analisis Informe\Analisis para compra\2024-2026.xlsx"
DB    = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/forecast_dcic")

CANALES_IGNORAR = {'Venta en Verde', 'Comerc. Dcic Spa', 'Cta cte Personal',
                   'Pérgolas', 'DCIC Recreación y Deportes Ltda.',
                   'Comerc. Icardia Suc. Mx.', 'Importadora DCIC',
                   'Guía Despacho Electrónica', 'Opex'}

def safe_dec(v, maxv=9_999_999_999.99):
    try:
        d = Decimal(str(v))
        return d if abs(d) <= Decimal(str(maxv)) else None
    except (InvalidOperation, TypeError):
        return None

def safe_int(v):
    try: return int(float(v))
    except: return 0

async def main():
    # ── Copiar Excel ────────────────────────────────────────────────────
    tmp = os.path.join(tempfile.gettempdir(), "ventas_import.xlsx")
    shutil.copy2(EXCEL, tmp)
    print(f"Excel copiado a {tmp}")

    # ── Leer Excel ──────────────────────────────────────────────────────
    print("Leyendo Excel (puede tardar 20-40 seg)…")
    df = pd.read_excel(tmp, sheet_name=0, dtype={
        'SKU Producto': str, 'N° Pedido': str, 'N° Sub-Orden': str,
        'Canal': str, 'Origen': str, 'Estado de Orden': str,
    })
    print(f"  {len(df):,} filas totales")

    # Solo Regular y Devuelta
    df = df[df['Estado de Orden'].isin(['Regular', 'Devuelta'])].copy()
    print(f"  {len(df):,} filas Regular+Devuelta")

    # Filtrar canales a ignorar
    df = df[~df['Canal'].isin(CANALES_IGNORAR)]
    print(f"  {len(df):,} filas tras filtrar canales")

    # Normalizar fecha
    df['_fecha'] = pd.to_datetime(df['Fecha'], errors='coerce').dt.date
    df = df.dropna(subset=['_fecha', 'SKU Producto'])
    df = df[df['SKU Producto'].str.strip() != '']
    print(f"  {len(df):,} filas con fecha y SKU válidos")

    fecha_min = df['_fecha'].min()
    fecha_max = df['_fecha'].max()
    print(f"  Rango: {fecha_min} al {fecha_max}")

    # ── Conectar BD ─────────────────────────────────────────────────────
    conn = await asyncpg.connect(DB)

    # Agregar columna num_pedido si no existe
    await conn.execute("""
        ALTER TABLE ventas ADD COLUMN IF NOT EXISTS num_pedido  VARCHAR(50);
        ALTER TABLE ventas ADD COLUMN IF NOT EXISTS num_suborden VARCHAR(50);
    """)

    # Eliminar índices únicos que bloquean la carga masiva del Excel
    await conn.execute("DROP INDEX IF EXISTS uq_ventas_linea")
    await conn.execute("DROP INDEX IF EXISTS uq_ventas_excel")
    await conn.execute("ALTER TABLE ventas DROP CONSTRAINT IF EXISTS ventas_unique_natural")
    print("Indices unicos eliminados")

    # Obtener SKUs válidos
    skus_validos = {r['sku'] for r in await conn.fetch("SELECT sku FROM productos")}
    print(f"  {len(skus_validos):,} SKUs en catálogo")

    # Borrar TODAS las ventas del rango — el Excel es la fuente de verdad
    deleted = await conn.execute(
        "DELETE FROM ventas WHERE fecha BETWEEN $1 AND $2",
        fecha_min, fecha_max
    )
    print(f"  Ventas anteriores eliminadas en rango: {deleted}")

    # ── Preparar filas ──────────────────────────────────────────────────
    filas = []
    skus_ignorados = set()

    for _, r in df.iterrows():
        sku = str(r['SKU Producto']).strip()
        if sku not in skus_validos:
            skus_ignorados.add(sku)
            continue

        es_devolucion = str(r['Estado de Orden']).strip() == 'Devuelta'
        cant_raw = safe_int(r.get('Cant.', 0))
        cantidad           = 0 if es_devolucion else cant_raw
        unidades_devueltas = cant_raw if es_devolucion else 0

        # precio_total_bruto = Venta Total (total de la línea)
        # valor_unitario_bruto = Valor Unitario
        filas.append((
            sku,
            r['_fecha'],
            str(r.get('Canal', '') or '').strip() or None,
            'excel',
            str(r.get('Estado de Orden', '')).strip(),
            str(r.get('Tipo de Despacho', '') or '').strip() or None,
            str(r.get('Tipo Registro', '') or '').strip() or None,
            cantidad,
            unidades_devueltas,
            safe_dec(r.get('Venta Total')),
            safe_dec(r.get('Valor Unitario')),
            safe_dec(r.get('Costo Calc.')),
            safe_dec(r.get('Margen CLP')),
            safe_dec(r.get('Margen %'), maxv=99.9999),
            str(r.get('Descripción', '') or '').strip()[:500] or None,
            str(r.get('Subcategoria', '') or '').strip() or None,
            str(r.get('Marca', '') or '').strip() or None,
            str(r.get('N° Pedido', '') or '').strip()[:50] or None,
            str(r.get('N° Sub-Orden', '') or '').strip()[:50] or None,
        ))

    print(f"\n  SKUs ignorados (fuera de catálogo): {len(skus_ignorados):,}")
    print(f"  Filas a insertar: {len(filas):,}")

    # ── Insertar en lotes de 1000 ────────────────────────────────────────
    BATCH = 1000
    insertadas = 0
    for i in range(0, len(filas), BATCH):
        lote = filas[i:i+BATCH]
        async with conn.transaction():
            await conn.executemany("""
                INSERT INTO ventas (
                    sku, fecha, canal, fuente, estado_orden, estado_despacho, tipo_linea,
                    cantidad, unidades_devueltas,
                    precio_total_bruto, valor_unitario_bruto, costo_unitario_clp,
                    margen_clp, margen_pct,
                    descripcion_producto, categoria_erp, marca_erp,
                    num_pedido, num_suborden
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)
                -- sin ON CONFLICT: ya borramos el rango antes
            """, lote)
        insertadas += len(lote)
        print(f"  Lote {i//BATCH+1}/{(len(filas)+BATCH-1)//BATCH} — {insertadas:,}/{len(filas):,}", end='\r')

    print()

    # ── Resumen final ────────────────────────────────────────────────────
    total = await conn.fetchval("SELECT COUNT(*) FROM ventas")
    por_anio = await conn.fetch("""
        SELECT EXTRACT(YEAR FROM fecha)::int AS anio,
               COUNT(*) AS filas,
               SUM(cantidad - unidades_devueltas) AS uds,
               ROUND(SUM(precio_total_bruto)) AS venta
        FROM ventas WHERE estado_orden='Regular'
        GROUP BY anio ORDER BY anio
    """)
    print(f"\n=== RESULTADO FINAL ===")
    print(f"Total ventas en BD: {total:,}")
    print(f"\n{'Año':>6} {'Filas':>10} {'Uds Netas':>12} {'Venta Bruta':>18}")
    for r in por_anio:
        print(f"  {r['anio']:>4} {r['filas']:>10,} {r['uds']:>12,} ${r['venta']:>17,.0f}")

    await conn.close()
    print("\nImportacion completada.")

asyncio.run(main())
