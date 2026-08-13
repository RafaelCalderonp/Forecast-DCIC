"""
Carga la corrección de forecast por alza de precios 2026 en ajuste_precio_2026.

Compara el precio nuevo (Monitor_Ventas, promedio de canales) contra el precio
actual en productos.precio_venta_bruto. Solo registra SKUs activos con delta
de precio relevante (>1% en cualquier dirección). factor_ajuste usa una
elasticidad conservadora fija (ver constants.ELASTICIDAD_PRECIO_DEFAULT) como
piso sobre el forecast, no una elasticidad estimada por SKU.
"""
import asyncio
from datetime import date
import openpyxl
from database import AsyncSessionLocal
from sqlalchemy import text
from constants import (
    ELASTICIDAD_PRECIO_DEFAULT,
    FACTOR_AJUSTE_PRECIO_MIN,
    FACTOR_AJUSTE_PRECIO_MAX,
)

MONITOR_PATH = r"C:\Users\rafae\OneDrive\Escritorio\Proyecto Forecast\Monitor_Ventas_2026-08-12.xlsx"
FECHA_DETECCION = date(2026, 8, 12)


def leer_precios_nuevos() -> dict:
    wb = openpyxl.load_workbook(MONITOR_PATH, data_only=True)
    ws = wb["Monitor Ventas"]
    precios = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        sku = row[0]
        if not sku:
            continue
        canales = [row[4], row[5], row[6], row[7], row[8], row[9]]
        presentes = [c for c in canales if c is not None]
        if presentes:
            precios[sku] = sum(presentes) / len(presentes)
    return precios


def factor_ajuste(delta_pct: float) -> float:
    factor = 1 + ELASTICIDAD_PRECIO_DEFAULT * delta_pct / 100
    return max(FACTOR_AJUSTE_PRECIO_MIN, min(FACTOR_AJUSTE_PRECIO_MAX, factor))


async def main():
    precios_nuevos = leer_precios_nuevos()
    print(f"Precios leídos del monitor: {len(precios_nuevos)}")

    async with AsyncSessionLocal() as db:
        r = await db.execute(text("SELECT sku, precio_venta_bruto FROM productos WHERE activo = TRUE"))
        precios_actuales = {row[0]: float(row[1] or 0) for row in r.fetchall()}

        filas = []
        for sku, precio_nuevo in precios_nuevos.items():
            precio_actual = precios_actuales.get(sku)
            if precio_actual is None or precio_actual <= 0:
                continue
            delta_pct = (precio_nuevo - precio_actual) / precio_actual * 100
            if abs(delta_pct) < 1:
                continue
            filas.append({
                "sku": sku,
                "precio_anterior": round(precio_actual, 2),
                "precio_nuevo": round(precio_nuevo, 2),
                "delta_pct": round(delta_pct, 2),
                "factor_ajuste": round(factor_ajuste(delta_pct), 3),
                "fecha": FECHA_DETECCION,
            })

        print(f"SKUs con cambio de precio relevante: {len(filas)}")

        for f in filas:
            await db.execute(text("""
                INSERT INTO ajuste_precio_2026
                    (sku, precio_anterior, precio_nuevo, delta_pct, factor_ajuste, fecha_deteccion)
                VALUES (:sku, :precio_anterior, :precio_nuevo, :delta_pct, :factor_ajuste, :fecha)
                ON CONFLICT (sku) DO UPDATE SET
                    precio_anterior = EXCLUDED.precio_anterior,
                    precio_nuevo    = EXCLUDED.precio_nuevo,
                    delta_pct       = EXCLUDED.delta_pct,
                    factor_ajuste   = EXCLUDED.factor_ajuste,
                    fecha_deteccion = EXCLUDED.fecha_deteccion,
                    activo          = TRUE
            """), f)
        await db.commit()

        subieron = [f for f in filas if f["delta_pct"] > 0]
        bajaron  = [f for f in filas if f["delta_pct"] < 0]
        print(f"Insertadas/actualizadas: {len(filas)} (subieron: {len(subieron)}, bajaron: {len(bajaron)})")
        criticos = [f for f in filas if f["delta_pct"] > 30]
        print(f"SKUs con alza >30% (candidatos a congelar compra): {len(criticos)}")
        for f in criticos:
            print(" ", f["sku"], f"+{f['delta_pct']}%", "factor:", f["factor_ajuste"])


if __name__ == "__main__":
    asyncio.run(main())
