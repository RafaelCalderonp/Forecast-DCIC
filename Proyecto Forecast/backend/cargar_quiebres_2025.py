"""
Carga la corrección de demanda por quiebres de stock 2025 desde el Excel
"Analisis_Quiebres_Consolidado.xlsx" (hoja "Resumen Quiebres") a la tabla
quiebres_stock_2025.

Solo se insertan filas donde real != base (hubo corrección real).
Formato de celda "Real→Base": "271→400" (quiebre) o "71" (sin corrección).
"""
import re
import openpyxl
from fastapi.testclient import TestClient

EXCEL_PATH = r"C:\Users\rafae\OneDrive\Escritorio\Proyecto Forecast\Analisis_Quiebres_Consolidado (1).xlsx"

MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
ANIO = 2025


def parsear_real_base(valor):
    """Retorna (real, base) o None si no hay corrección."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return None  # sin flecha = sin corrección
    s = str(valor).strip()
    if not s or s == "—":
        return None
    m = re.match(r"^([\d.,]+)\s*→\s*([\d.,]+)$", s)
    if not m:
        return None
    real = float(m.group(1).replace(".", "").replace(",", "."))
    base = float(m.group(2).replace(".", "").replace(",", "."))
    if real == base:
        return None
    return real, base


def main():
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    ws = wb["Resumen Quiebres"]

    filas_a_cargar = []
    for row in ws.iter_rows(min_row=5, values_only=True):
        sku = row[0]
        if not sku:
            continue
        for idx_mes, nombre_mes in enumerate(MESES):
            col_offset = 5 + idx_mes * 3
            dias_q = row[col_offset]
            pct_mes_raw = row[col_offset + 1]
            real_base_raw = row[col_offset + 2]

            parsed = parsear_real_base(real_base_raw)
            if parsed is None:
                continue
            real, base = parsed

            pct_mes = None
            if isinstance(pct_mes_raw, str) and pct_mes_raw.strip().endswith("%"):
                try:
                    pct_mes = float(pct_mes_raw.strip().rstrip("%"))
                except ValueError:
                    pct_mes = None
            elif isinstance(pct_mes_raw, (int, float)):
                pct_mes = float(pct_mes_raw) * 100 if pct_mes_raw <= 1 else float(pct_mes_raw)

            dias_q_val = int(dias_q) if isinstance(dias_q, (int, float)) else None

            filas_a_cargar.append({
                "sku": sku,
                "anio": ANIO,
                "mes": idx_mes + 1,
                "dias_quiebre": dias_q_val,
                "pct_mes_quiebre": pct_mes,
                "ventas_real": real,
                "demanda_base": base,
            })

    print(f"Filas con corrección a cargar: {len(filas_a_cargar)}")
    print("Ejemplo:", filas_a_cargar[:3])

    from database import AsyncSessionLocal
    from sqlalchemy import text
    import asyncio

    async def cargar():
        async with AsyncSessionLocal() as db:
            insertadas = 0
            for f in filas_a_cargar:
                await db.execute(text("""
                    INSERT INTO quiebres_stock_2025
                        (sku, anio, mes, dias_quiebre, pct_mes_quiebre, ventas_real, demanda_base)
                    VALUES (:sku, :anio, :mes, :dias_quiebre, :pct_mes_quiebre, :ventas_real, :demanda_base)
                    ON CONFLICT (sku, anio, mes) DO UPDATE SET
                        dias_quiebre = EXCLUDED.dias_quiebre,
                        pct_mes_quiebre = EXCLUDED.pct_mes_quiebre,
                        ventas_real = EXCLUDED.ventas_real,
                        demanda_base = EXCLUDED.demanda_base
                """), f)
                insertadas += 1
            await db.commit()
            print(f"Insertadas/actualizadas: {insertadas}")

    asyncio.run(cargar())


if __name__ == "__main__":
    main()
