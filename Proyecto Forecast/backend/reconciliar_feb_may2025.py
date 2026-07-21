"""
Reconciliacion Febrero y Mayo 2025: Excel vs BBDD
"""

import asyncio, asyncpg, os, pandas as pd
from dotenv import load_dotenv

load_dotenv()
DB = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")

EXCEL_PATH = r"C:\Users\rafae\OneDrive - IMPORTADORA DCIC SPA\DCIC SpA\001. Analisis Informe\Ventas-01-01-2023_al_23-06-2026.xlsx"


def make_key(row):
    canal = str(row.get("Canal", "") or "").strip()
    sku   = str(row.get("SKU", "") or "").strip()
    if "mercado" in canal.lower() or canal.upper() == "ML":
        val = str(row.get("SubOrden", "") or "").strip()
    else:
        val = str(row.get("Pedido", "") or "").strip()
    return f"{sku}|{val}"


def make_key_db(row):
    canal = str(row.get("canal", "") or "").strip()
    sku   = str(row.get("sku", "") or "").strip()
    if "mercado" in canal.lower():
        val = str(row.get("num_suborden", "") or "").strip()
    else:
        val = str(row.get("num_pedido", "") or "").strip()
    return f"{sku}|{val}"


async def fetch_db(mes):
    conn = await asyncpg.connect(DB)
    rows = await conn.fetch("""
        SELECT sku, fecha, canal, fuente, estado_orden, tipo_linea,
               cantidad, precio_total_bruto, valor_unitario_bruto,
               num_pedido, num_suborden, id_externo
        FROM ventas
        WHERE fecha >= $1 AND fecha <= $2
        ORDER BY fecha, canal, sku
    """, f"2025-{mes:02d}-01", f"2025-{mes:02d}-28" if mes == 2 else f"2025-{mes:02d}-31")
    await conn.close()
    return [dict(r) for r in rows]


def reconciliar_mes(df_raw, mes, nombre):
    df_raw2 = df_raw.copy()
    col_map = {
        "SKU Producto": "SKU", "Canal": "Canal", "Fecha": "Fecha",
        "N° Sub-Orden": "SubOrden", "N° Pedido": "Pedido",
        "Estado de Orden": "EstadoOrden", "Venta Total": "VentaTotal",
        "Cant.": "Cantidad", "Tipo Registro": "TipoRegistro",
    }
    df_raw2.rename(columns={k:v for k,v in col_map.items() if k in df_raw2.columns}, inplace=True)

    df_raw2["FechaParsed"] = pd.to_datetime(df_raw2["Fecha"], errors="coerce")
    df_mes = df_raw2[
        (df_raw2["FechaParsed"].dt.year == 2025) &
        (df_raw2["FechaParsed"].dt.month == mes)
    ].copy()

    # Solo Regular + PRODUCTO (mismas reglas que sync)
    if "EstadoOrden" in df_mes.columns:
        df_mes = df_mes[df_mes["EstadoOrden"].str.strip() == "Regular"]
    if "TipoRegistro" in df_mes.columns:
        df_mes = df_mes[df_mes["TipoRegistro"].str.upper().str.strip() == "PRODUCTO"]

    print(f"Excel {nombre}: {len(df_mes):,} filas (Regular+PRODUCTO)")
    df_mes["_key"] = df_mes.apply(make_key, axis=1)

    db_rows = asyncio.run(fetch_db(mes))
    df_db = pd.DataFrame(db_rows)
    print(f"BBDD  {nombre}: {len(df_db):,} filas")
    df_db["_key"] = df_db.apply(make_key_db, axis=1)

    keys_excel = set(df_mes["_key"])
    keys_db    = set(df_db["_key"])

    not_in_db    = df_mes[~df_mes["_key"].isin(keys_db)].drop(columns=["_key","FechaParsed"])
    not_in_excel = df_db[~df_db["_key"].isin(keys_excel)].drop(columns=["_key"])
    print(f"  En Excel NO en BD: {len(not_in_db)}")
    print(f"  En BD NO en Excel: {len(not_in_excel)}")
    return not_in_db, not_in_excel


def main():
    print("Leyendo Excel...")
    df_raw = pd.read_excel(EXCEL_PATH, sheet_name="Ventas Consolidadas", dtype=str)
    print(f"Total Excel: {len(df_raw):,} filas")

    results = {}
    for mes, nombre in [(2, "Febrero"), (5, "Mayo")]:
        print(f"\n--- {nombre} 2025 ---")
        not_in_db, not_in_excel = reconciliar_mes(df_raw, mes, nombre)
        results[nombre] = (not_in_db, not_in_excel)

    for nombre, (not_in_db, not_in_excel) in results.items():
        out = fr"C:\Users\rafae\OneDrive\Escritorio\Proyecto Forecast\Reconciliacion_{nombre}2025.xlsx"
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            not_in_db.to_excel(writer, sheet_name="En Excel NO en BD", index=False)
            not_in_excel.to_excel(writer, sheet_name="En BD NO en Excel", index=False)
        print(f"Guardado: {out}")


if __name__ == "__main__":
    main()
