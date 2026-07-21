"""
Compara ventas del Excel 2024-2026 vs lo que hay en la BD.
Solo toma filas donde columna K (estado_orden) == 'Regular'.
"""
import asyncio, asyncpg, pandas as pd, sys, shutil, tempfile, os
from pathlib import Path

EXCEL = r"C:\Users\rafae\OneDrive - IMPORTADORA DCIC SPA\DCIC SpA\001. Analisis Informe\Analisis para compra\2024-2026.xlsx"
DB    = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/forecast_dcic")

async def main():
    # Copiar a temp para evitar bloqueo de OneDrive/Excel
    tmp = os.path.join(tempfile.gettempdir(), "ventas_cmp.xlsx")
    shutil.copy2(EXCEL, tmp)
    print(f"Archivo copiado a {tmp}")

    # ── Leer Excel ──────────────────────────────────────────────────────
    EXCEL_READ = tmp
    print("Leyendo Excel…")
    df = pd.read_excel(EXCEL_READ, sheet_name=0)
    print(f"  Filas totales: {len(df):,}")
    print(f"  Columnas ({len(df.columns)}): {list(df.columns)}")

    # Identificar columna K (índice 10) y columna de fecha/año
    col_k = df.columns[10]
    print(f"  Columna K = '{col_k}'")

    # Filtrar solo Regular
    df_reg = df[df[col_k].astype(str).str.strip() == 'Regular'].copy()
    print(f"  Filas Regular: {len(df_reg):,}")

    # Detectar columna de fecha
    fecha_col = None
    for c in df.columns:
        if 'fecha' in str(c).lower() or 'date' in str(c).lower():
            fecha_col = c; break
    if fecha_col is None:
        # buscar columna con fechas
        for c in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[c]) or (df[c].dtype == object and '2024' in df[c].astype(str).str[:4].values):
                fecha_col = c; break
    print(f"  Columna fecha = '{fecha_col}'")

    df_reg['_fecha'] = pd.to_datetime(df_reg[fecha_col], errors='coerce')
    df_reg['_anio']  = df_reg['_fecha'].dt.year
    df_reg['_mes']   = df_reg['_fecha'].dt.month

    # Detectar columna de cantidad
    cant_col = None
    for c in df.columns:
        if 'cantidad' in str(c).lower() or 'qty' in str(c).lower() or 'units' in str(c).lower():
            cant_col = c; break
    print(f"  Columna cantidad = '{cant_col}'")

    # Detectar columna venta bruta
    venta_col = None
    for c in df.columns:
        if 'brut' in str(c).lower() or 'venta' in str(c).lower() or 'revenue' in str(c).lower():
            venta_col = c; break
    print(f"  Columna venta bruta = '{venta_col}'")

    # Resumen Excel por año/mes
    agg = {'filas': ('_fecha', 'count')}
    if cant_col:  agg['uds_excel']   = (cant_col,  'sum')
    if venta_col: agg['venta_excel'] = (venta_col, 'sum')
    excel_sum = df_reg.groupby(['_anio','_mes']).agg(**agg).reset_index()

    # ── Leer BD ──────────────────────────────────────────────────────────
    print("\nConectando a BD…")
    conn = await asyncpg.connect(DB)
    rows = await conn.fetch("""
        SELECT EXTRACT(YEAR  FROM fecha)::int AS anio,
               EXTRACT(MONTH FROM fecha)::int AS mes,
               COUNT(*)                        AS filas_bd,
               SUM(cantidad)                   AS uds_bd,
               SUM(precio_total_bruto * cantidad) AS venta_bd
        FROM ventas
        WHERE estado_orden = 'Regular'
        GROUP BY anio, mes
        ORDER BY anio, mes
    """)
    await conn.close()
    bd = pd.DataFrame([dict(r) for r in rows])

    # ── Merge y comparación ──────────────────────────────────────────────
    merged = pd.merge(excel_sum, bd, left_on=['_anio','_mes'], right_on=['anio','mes'], how='outer')
    merged['_anio'] = merged['_anio'].fillna(merged['anio'])
    merged['_mes']  = merged['_mes'].fillna(merged['mes'])
    merged = merged.sort_values(['_anio','_mes'])

    print(f"\n{'Año-Mes':<10} {'Filas Excel':>12} {'Filas BD':>10} {'Dif Filas':>10} {'Uds Excel':>12} {'Uds BD':>10} {'Dif Uds':>10}")
    print("-"*80)
    for _, r in merged.iterrows():
        anio = int(r['_anio']) if pd.notna(r['_anio']) else '?'
        mes  = int(r['_mes'])  if pd.notna(r['_mes'])  else '?'
        fe   = int(r['filas'])        if pd.notna(r.get('filas'))    else 0
        fb   = int(r['filas_bd'])     if pd.notna(r.get('filas_bd')) else 0
        ue   = int(r['uds_excel'])    if pd.notna(r.get('uds_excel')) and cant_col else 0
        ub   = int(r['uds_bd'])       if pd.notna(r.get('uds_bd'))   else 0
        df_  = fe - fb
        du   = ue - ub
        flag = ' <-- FALTA' if abs(df_) > fe * 0.05 else ''
        print(f"{anio}-{mes:02d}   {fe:>12,} {fb:>10,} {df_:>+10,} {ue:>12,} {ub:>10,} {du:>+10,}{flag}")

    print("\n=== TOTALES ===")
    print(f"  Excel Regular: {len(df_reg):,} filas")
    print(f"  BD Regular:    {bd['filas_bd'].sum():,} filas")
    if venta_col:
        ve = df_reg[venta_col].sum()
        vb = bd['venta_bd'].sum() if 'venta_bd' in bd else 0
        print(f"  Venta Bruta Excel: ${ve:,.0f}")
        print(f"  Venta Bruta BD:    ${vb:,.0f}")

asyncio.run(main())
