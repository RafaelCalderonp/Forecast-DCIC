"""
Carga hoja Inventario del Excel v17 a la tabla stock.
Columnas: CODIGO, DESCRIPCION, Stock Jun, Llegadas Jun, Stock Jul, Llegadas Jul, ...

Uso:
    python cargar_inventario.py
    python cargar_inventario.py --excel "ruta/al/archivo.xlsx"
"""
import os, sys, asyncio, argparse, openpyxl
from pathlib import Path
from dotenv import load_dotenv
import asyncpg

load_dotenv()
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/forecast_dcic"
).replace("postgresql+asyncpg://", "postgresql://")

EXCEL_DEFAULT = r"C:\Users\rafae\OneDrive - IMPORTADORA DCIC SPA\DCIC SpA\001. Analisis Informe\Forecast_2026 v17.xlsx"


def a_int(v):
    if v is None or str(v).strip() == '': return 0
    try: return max(0, int(float(str(v).replace(',', '.'))))
    except: return 0


def leer_inventario(ruta):
    wb = openpyxl.load_workbook(ruta, data_only=True, read_only=True)
    hojas = [s for s in wb.sheetnames if 'nventario' in s]
    if not hojas:
        raise ValueError(f"No se encontro hoja Inventario. Hojas: {wb.sheetnames}")
    ws = wb[hojas[0]]
    print(f"[OK] Hoja: '{hojas[0]}'")

    # Buscar fila de headers
    header_row = None
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=5, values_only=True), 1):
        if row[0] and str(row[0]).strip().upper() in ('CODIGO', 'SKU', 'CÓDIGO'):
            header_row = i
            break
    if not header_row:
        raise ValueError("No encontre fila de headers con 'CODIGO'")

    headers = [str(c or '').strip().lower() for c in
               next(ws.iter_rows(min_row=header_row, max_row=header_row, values_only=True))]
    print(f"[OK] Headers: {headers[:17]}")

    def col(nombre):
        for i, h in enumerate(headers):
            if nombre.lower() in h:
                return i
        return None

    idx_sku      = col('codigo') if col('codigo') is not None else col('sku')
    idx_stock    = col('stock jun')
    idx_l_jun    = col('llegadas jun')
    idx_l_jul    = col('llegadas jul')
    idx_l_ago    = col('llegadas ago')
    idx_l_sep    = col('llegadas sep')
    idx_l_oct    = col('llegadas oct')
    idx_l_nov    = col('llegadas nov')
    idx_l_dic    = col('llegadas dic')

    print(f"  stock_jun={idx_stock} | llegadas jun={idx_l_jun} jul={idx_l_jul} ago={idx_l_ago} "
          f"sep={idx_l_sep} oct={idx_l_oct} nov={idx_l_nov} dic={idx_l_dic}")

    if idx_sku is None or idx_stock is None:
        raise ValueError("No encontre columnas CODIGO o 'Stock Jun'")

    registros = []
    for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
        sku = str(row[idx_sku] or '').strip()
        if not sku or sku.upper().startswith('TOTAL'):
            continue
        registros.append({
            'sku':        sku,
            'stock_jun':  a_int(row[idx_stock]),
            'leg_jun':    a_int(row[idx_l_jun]) if idx_l_jun is not None else 0,
            'leg_jul':    a_int(row[idx_l_jul]) if idx_l_jul is not None else 0,
            'leg_ago':    a_int(row[idx_l_ago]) if idx_l_ago is not None else 0,
            'leg_sep':    a_int(row[idx_l_sep]) if idx_l_sep is not None else 0,
            'leg_oct':    a_int(row[idx_l_oct]) if idx_l_oct is not None else 0,
            'leg_nov':    a_int(row[idx_l_nov]) if idx_l_nov is not None else 0,
            'leg_dic':    a_int(row[idx_l_dic]) if idx_l_dic is not None else 0,
        })
    print(f"[OK] {len(registros)} SKUs leidos del Inventario")
    return registros


async def main(args):
    conn = await asyncpg.connect(DATABASE_URL)
    print("[OK] Conectado a BD")

    skus_validos = {r['sku'] for r in await conn.fetch("SELECT sku FROM productos")}
    print(f"[OK] {len(skus_validos)} SKUs validos en BD")

    registros = leer_inventario(args.excel)

    ignorados = [r for r in registros if r['sku'] not in skus_validos]
    validos   = [r for r in registros if r['sku'] in skus_validos]
    print(f"[OK] Validos: {len(validos)} | Ignorados (no en catalogo): {len(ignorados)}")

    if ignorados[:3]:
        print(f"  Ejemplos ignorados: {[r['sku'] for r in ignorados[:3]]}")

    filas = [
        (r['sku'], r['stock_jun'], r['leg_jun'], r['leg_jul'], r['leg_ago'],
         r['leg_sep'], r['leg_oct'], r['leg_nov'], r['leg_dic'])
        for r in validos
    ]

    async with conn.transaction():
        await conn.executemany("""
            INSERT INTO stock (
                sku, stock_jun,
                llegada_jun, llegada_jul, llegada_ago,
                llegada_sep, llegada_oct, llegada_nov, llegada_dic,
                stock_base, fecha_actualizacion
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$2,CURRENT_DATE)
            ON CONFLICT (sku) DO UPDATE SET
                stock_jun      = EXCLUDED.stock_jun,
                stock_base     = EXCLUDED.stock_jun,
                llegada_jun    = EXCLUDED.llegada_jun,
                llegada_jul    = EXCLUDED.llegada_jul,
                llegada_ago    = EXCLUDED.llegada_ago,
                llegada_sep    = EXCLUDED.llegada_sep,
                llegada_oct    = EXCLUDED.llegada_oct,
                llegada_nov    = EXCLUDED.llegada_nov,
                llegada_dic    = EXCLUDED.llegada_dic,
                fecha_actualizacion = CURRENT_DATE,
                updated_at     = NOW()
        """, filas)

    total = await conn.fetchval("SELECT COUNT(*) FROM stock WHERE stock_base > 0 OR llegada_jun > 0 OR llegada_sep > 0")
    print(f"[OK] Carga completa. Productos con stock/llegadas: {total}")

    # Resumen
    sample = await conn.fetch("""
        SELECT sku, stock_jun, llegada_jun, llegada_jul, llegada_ago,
               llegada_sep, llegada_oct, llegada_nov, llegada_dic
        FROM stock
        WHERE stock_jun > 0 OR llegada_sep > 0
        ORDER BY sku LIMIT 5
    """)
    print("\n[MUESTRA] Primeros 5 con datos:")
    for r in sample:
        print(f"  {r['sku']}: jun={r['stock_jun']} | leg={r['llegada_jun']}/{r['llegada_jul']}/{r['llegada_ago']}/{r['llegada_sep']}/{r['llegada_oct']}/{r['llegada_nov']}/{r['llegada_dic']}")

    await conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--excel', default=EXCEL_DEFAULT)
    args = parser.parse_args()
    asyncio.run(main(args))
