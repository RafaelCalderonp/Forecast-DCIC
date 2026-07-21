"""
Busca registros que la API devuelve como validos (Regular + PRODUCTO)
pero que NO estan en la BD — para Febrero y Mayo 2025.
"""

import asyncio, asyncpg, os, httpx
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()
DB      = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
ERP_URL = os.getenv("ERP_API_URL", "https://dcic-api-production.up.railway.app")
FUENTES = ["bsale", "wivo"]

async def get_ids_bd(conn, mes):
    rows = await conn.fetch(
        "SELECT id_externo FROM ventas WHERE EXTRACT(YEAR FROM fecha)=2025 AND EXTRACT(MONTH FROM fecha)=$1",
        mes
    )
    return {r["id_externo"] for r in rows}


async def fetch_dia(client, ft, dia):
    filas = []
    offset = 0
    while True:
        r = await client.get(f"{ERP_URL}/ventas/", params={
            "fecha_desde": str(dia), "fecha_hasta": str(dia),
            "fuente": ft, "limit": 100, "offset": offset
        })
        r.raise_for_status()
        data = r.json()
        page = data if isinstance(data, list) else (data.get("data") or data.get("items") or data.get("ventas") or [])
        if not page:
            break
        filas.extend(page)
        if len(page) < 100:
            break
        offset += 100
    return filas


async def main():
    conn = await asyncpg.connect(DB)

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        for mes, nombre in [(2, "Febrero"), (5, "Mayo")]:
            print(f"\n=== {nombre} 2025 ===")
            ids_bd = await get_ids_bd(conn, mes)
            print(f"  IDs en BD: {len(ids_bd)}")

            faltantes = []
            inicio = date(2025, mes, 1)
            if mes == 2:
                fin = date(2025, 2, 28)
            elif mes == 5:
                fin = date(2025, 5, 31)

            cur = inicio
            while cur <= fin:
                for ft in FUENTES:
                    filas = await fetch_dia(client, ft, cur)
                    for row in filas:
                        estado    = (row.get("estado_orden") or "").strip()
                        tipo      = str(row.get("tipo_linea") or "").upper().strip()
                        if estado != "Regular" or tipo != "PRODUCTO":
                            continue
                        id_ext = str(row["id"]) if row.get("id") is not None else None
                        if id_ext and id_ext not in ids_bd:
                            faltantes.append({
                                "fuente": ft,
                                "fecha": str(cur),
                                "id_externo": id_ext,
                                "sku": row.get("sku_id") or row.get("sku"),
                                "canal": row.get("canal"),
                                "n_orden": row.get("n_orden"),
                                "n_pedido": row.get("n_pedido"),
                                "estado_orden": estado,
                                "tipo_linea": row.get("tipo_linea"),
                                "cantidad": row.get("cantidad"),
                                "venta_bruto": row.get("venta_bruto"),
                            })
                cur += timedelta(days=1)

            print(f"  Registros validos en API NO en BD: {len(faltantes)}")
            if faltantes:
                for f in faltantes:
                    print(f"    {f}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
