"""
Reconciliacion Diciembre 2025: Excel vs BBDD
- Hoja 1: Ventas en Excel que NO estan en la BBDD
- Hoja 2: Ventas en BBDD que NO estan en el Excel

Clave de match:
  - Mercado Libre: SKU + N° Sub-Orden  (num_suborden en BD)
  - Resto:         SKU + N° Pedido     (num_pedido en BD)
"""

import asyncio, asyncpg, os, pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DB = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")

EXCEL_PATH = r"C:\Users\rafae\OneDrive - IMPORTADORA DCIC SPA\DCIC SpA\001. Analisis Informe\Ventas-01-01-2023_al_23-06-2026.xlsx"
OUTPUT_PATH = r"C:\Users\rafae\OneDrive\Escritorio\Proyecto Forecast\Reconciliacion_Diciembre2025.xlsx"


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


async def fetch_db_dic2025():
    conn = await asyncpg.connect(DB)
    rows = await conn.fetch("""
        SELECT sku, fecha, canal, fuente, estado_orden, estado_despacho, tipo_linea,
               cantidad, precio_total_bruto, valor_unitario_bruto,
               num_pedido, num_suborden, id_externo
        FROM ventas
        WHERE fecha >= '2025-12-01' AND fecha <= '2025-12-31'
        ORDER BY fecha, canal, sku
    """)
    await conn.close()
    return [dict(r) for r in rows]


def main():
    print("Leyendo Excel...")
    df_raw = pd.read_excel(EXCEL_PATH, sheet_name="Ventas Consolidadas", dtype=str)

    # Normalizar columnas clave
    col_map = {
        "SKU Producto":  "SKU",
        "Canal":         "Canal",
        "Fecha":         "Fecha",
        "N° Sub-Orden": "SubOrden",
        "N° Pedido":    "Pedido",
        "Origen":        "Origen",
        "Estado de Orden": "EstadoOrden",
        "Venta Total":   "VentaTotal",
        "Cant.":         "Cantidad",
        "Tipo de Despacho": "TipoDespacho",
        "Estado de Despacho": "EstadoDespacho",
        "Tipo Registro": "TipoRegistro",
    }
    df_raw.rename(columns=col_map, inplace=True)

    # Filtrar Diciembre 2025
    df_raw["FechaParsed"] = pd.to_datetime(df_raw["Fecha"], errors="coerce")
    df_dic = df_raw[
        (df_raw["FechaParsed"].dt.year == 2025) &
        (df_raw["FechaParsed"].dt.month == 12)
    ].copy()
    print(f"Excel Dic-2025: {len(df_dic):,} filas")

    # Clave
    df_dic["_key"] = df_dic.apply(make_key, axis=1)

    # Obtener BBDD
    print("Consultando BBDD...")
    db_rows = asyncio.run(fetch_db_dic2025())
    df_db = pd.DataFrame(db_rows)
    print(f"BBDD Dic-2025: {len(df_db):,} filas")

    df_db["_key"] = df_db.apply(make_key_db, axis=1)

    keys_excel = set(df_dic["_key"])
    keys_db    = set(df_db["_key"])

    # Hoja 1: En Excel pero NO en BD
    not_in_db = df_dic[~df_dic["_key"].isin(keys_db)].drop(columns=["_key", "FechaParsed"])
    print(f"En Excel pero NO en BD: {len(not_in_db):,}")

    # Hoja 2: En BD pero NO en Excel
    not_in_excel = df_db[~df_db["_key"].isin(keys_excel)].drop(columns=["_key"])
    print(f"En BD pero NO en Excel: {len(not_in_excel):,}")

    print(f"Guardando en {OUTPUT_PATH} ...")
    with pd.ExcelWriter(OUTPUT_PATH, engine="openpyxl") as writer:
        not_in_db.to_excel(writer, sheet_name="En Excel NO en BD", index=False)
        not_in_excel.to_excel(writer, sheet_name="En BD NO en Excel", index=False)

    print("Listo.")


if __name__ == "__main__":
    main()
