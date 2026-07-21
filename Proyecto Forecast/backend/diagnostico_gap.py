"""
Diagnostica por qué la BD tiene ~50% de las filas del Excel.
"""
import asyncio, asyncpg, pandas as pd, shutil, tempfile, os

EXCEL = r"C:\Users\rafae\OneDrive - IMPORTADORA DCIC SPA\DCIC SpA\001. Analisis Informe\Analisis para compra\2024-2026.xlsx"
DB    = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/forecast_dcic")

async def main():
    tmp = os.path.join(tempfile.gettempdir(), "ventas_cmp.xlsx")
    shutil.copy2(EXCEL, tmp)

    df = pd.read_excel(tmp, sheet_name=0)
    df_reg = df[df['Estado de Orden'].astype(str).str.strip() == 'Regular'].copy()
    print(f"Excel Regular: {len(df_reg):,} filas\n")

    conn = await asyncpg.connect(DB)
    skus_bd = {r['sku'] for r in await conn.fetch("SELECT sku FROM productos")}
    canales_bd = {r['nombre_api'] for r in await conn.fetch("SELECT nombre_api FROM canal_mapeo")}
    print(f"SKUs en catálogo BD: {len(skus_bd):,}")
    print(f"Canales mapeados BD: {canales_bd}\n")

    # ── 1. SKUs del Excel que no están en el catálogo ──────────────────
    skus_excel = df_reg['SKU Producto'].astype(str).str.strip()
    sin_sku    = skus_excel.isnull() | (skus_excel == 'nan') | (skus_excel == '')
    fuera_cat  = ~skus_excel.isin(skus_bd) & ~sin_sku
    en_cat     = skus_excel.isin(skus_bd)

    print("=== COBERTURA DE SKUs ===")
    print(f"  Sin SKU:               {sin_sku.sum():>8,} filas ({sin_sku.mean():.1%})")
    print(f"  SKU fuera de catálogo: {fuera_cat.sum():>8,} filas ({fuera_cat.mean():.1%})")
    print(f"  SKU en catálogo:       {en_cat.sum():>8,} filas ({en_cat.mean():.1%})")

    top_skus_fuera = df_reg[fuera_cat]['SKU Producto'].value_counts().head(20)
    print(f"\nTop 20 SKUs fuera de catálogo:")
    for sku, cnt in top_skus_fuera.items():
        print(f"  {sku}: {cnt:,} filas")

    # ── 2. Canales del Excel que no están mapeados ─────────────────────
    canales_excel = df_reg['Canal'].astype(str).str.strip()
    print(f"\n=== COBERTURA DE CANALES ===")
    canal_counts = canales_excel.value_counts()
    for canal, cnt in canal_counts.items():
        en_bd = '✓' if canal in canales_bd else '✗ NO MAPEADO'
        print(f"  {en_bd}  {canal}: {cnt:,} filas")

    # ── 3. Origen (bsale vs wivo) ──────────────────────────────────────
    print(f"\n=== POR ORIGEN ===")
    print(df_reg['Origen'].value_counts().to_string())

    # ── 4. Filas en catálogo con canal mapeado — lo que debería estar en BD ──
    en_cat_y_canal = en_cat & canales_excel.isin(canales_bd)
    print(f"\n=== RESUMEN ESPERADO EN BD ===")
    print(f"  Con SKU en catálogo Y canal mapeado: {en_cat_y_canal.sum():>8,} filas")
    print(f"  BD tiene actualmente:                {158755:>8,} filas")

    await conn.close()

asyncio.run(main())
