import pandas as pd, shutil, tempfile, os
EXCEL = r"C:\Users\rafae\OneDrive - IMPORTADORA DCIC SPA\DCIC SpA\001. Analisis Informe\Analisis para compra\2024-2026.xlsx"
tmp = os.path.join(tempfile.gettempdir(), "v2.xlsx")
shutil.copy2(EXCEL, tmp)
df = pd.read_excel(tmp, dtype={"SKU Producto": str})
reg = df[df["Estado de Orden"] == "Regular"].copy()
reg["_anio"] = pd.to_datetime(reg["Fecha"], errors="coerce").dt.year

cols = ["Venta Total", "Valor Neto", "Total Neto", "Ingreso Total", "Ingreso por Envio Flex", "Ingreso por promocion"]
for anio in [2024, 2025, 2026]:
    print(f"\n=== {anio} ===")
    sub = reg[reg["_anio"] == anio]
    print(f"  Filas: {len(sub):,}   Uds: {sub['Cant.'].sum():,.0f}")
    for col in cols:
        if col in reg.columns:
            v = sub[col].sum()
            print(f"  {col}: ${v:,.0f}")

# Muestra 3 filas para ver los valores reales
print("\n=== MUESTRA 3 FILAS 2025 ===")
s = reg[reg["_anio"] == 2025].head(3)[["SKU Producto","Canal","Cant.","Venta Total","Total Neto","Ingreso Total"]].to_string()
print(s)
