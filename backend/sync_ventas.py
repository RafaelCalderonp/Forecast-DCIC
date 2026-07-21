"""
Sincronizacion de ventas desde API DCIC (Bsale + Wivo)
https://dcic-api-production.up.railway.app

Uso:
    python sync_ventas.py                          # sincroniza desde 2024-01-01 hasta hoy
    python sync_ventas.py --desde 2025-01-01       # desde fecha especifica
    python sync_ventas.py --desde 2024-01-01 --hasta 2024-12-31
    python sync_ventas.py --fuente wivo            # solo wivo o bsale
"""

import os, sys, asyncio, argparse, json
from datetime import date, timedelta, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import asyncpg
import requests as _requests
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
API_BASE     = "https://dcic-api-production.up.railway.app"
PAGE_SIZE    = 100
MAX_RETRIES  = 3

# Solo ventas regulares
ESTADOS_VALIDOS = {"Regular"}
# Ignorar: Devuelta, Cancelada, Otros

# Todos los canales disponibles en la API se procesan
CANALES_IGNORAR: set = set()

INSERT_SQL = """
    INSERT INTO ventas (
        sku, fecha, canal, fuente, estado_orden, estado_despacho, tipo_linea,
        cantidad, unidades_devueltas,
        precio_total_bruto, valor_unitario_bruto, costo_unitario_clp,
        margen_clp, margen_pct,
        descripcion_producto, categoria_erp, marca_erp,
        id_externo, num_pedido, num_suborden
    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)
    ON CONFLICT (id_externo) WHERE id_externo IS NOT NULL DO NOTHING
"""


def api_get(params: dict) -> tuple[list, dict]:
    """Llama GET /ventas con los params dados. Retorna (registros, headers)."""
    url = f"{API_BASE}/ventas"
    for intento in range(1, MAX_RETRIES + 1):
        try:
            resp = _requests.get(url, params=params, timeout=(5, 20),
                                 headers={"Connection": "close"})
            resp.raise_for_status()
            headers = {
                "x-returned-count": int(resp.headers.get("X-Returned-Count", 0)),
                "x-limit":          int(resp.headers.get("X-Limit", PAGE_SIZE)),
            }
            return resp.json(), headers
        except Exception as e:
            if intento == MAX_RETRIES:
                raise
            import time; time.sleep(2 ** intento)


def safe_date(valor):
    if valor is None:
        return None
    if isinstance(valor, date):
        return valor
    try:
        return datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def safe_decimal(valor, max_abs=Decimal("9999999999.99")):
    if valor is None:
        return None
    try:
        d = Decimal(str(valor))
        if abs(d) > max_abs:
            return None
        return d
    except InvalidOperation:
        return None

MAX_MARGEN_PCT = Decimal("99.9999")


async def cargar_canal_mapeo(conn) -> dict:
    rows = await conn.fetch("SELECT nombre_api, canal_id FROM canal_mapeo")
    return {r["nombre_api"]: r["canal_id"] for r in rows}


async def cargar_skus_validos(conn) -> set:
    rows = await conn.fetch("SELECT sku FROM productos")
    return {r["sku"] for r in rows}


async def sync_mes(conn, fecha_desde: date, fecha_hasta: date, fuente: str,
                   canal_mapeo: dict, skus_validos: set, log_id: int):
    offset = 0
    total_api = 0
    total_upsert = 0
    filas_upsert = []
    skus_fuera_catalogo = set()

    while True:
        params = {
            "fecha_desde": str(fecha_desde),
            "fecha_hasta":  str(fecha_hasta),
            "fuente":       fuente,
            "limit":        PAGE_SIZE,
            "offset":       offset,
        }
        registros, headers = api_get(params)
        returned = headers["x-returned-count"]
        total_api += returned

        for r in registros:
            sku = r.get("sku_id")
            canal_nombre = r.get("canal") or ""
            estado_orden = r.get("estado_orden") or ""
            fuente_reg   = fuente

            # Ignorar registros sin SKU
            if not sku:
                continue

            # Alertar SKUs fuera de catalogo pero igual insertarlos
            if sku not in skus_validos:
                skus_fuera_catalogo.add(sku)

            # Ignorar canales obsoletos
            if canal_nombre in CANALES_IGNORAR:
                continue

            # Solo regulares
            if estado_orden not in ESTADOS_VALIDOS:
                continue

            # Solo productos (excluir servicios y otros)
            if str(r.get("tipo_linea") or "").upper() != "PRODUCTO":
                continue

            canal_id = canal_mapeo.get(canal_nombre)

            cantidad           = int(r.get("cantidad") or 0)
            unidades_devueltas = 0
            cantidad_venta     = cantidad

            filas_upsert.append((
                sku,
                safe_date(r.get("fecha")),
                canal_nombre,
                fuente_reg,
                estado_orden,
                r.get("estado_despacho"),
                r.get("tipo_linea"),
                cantidad_venta,
                unidades_devueltas,
                safe_decimal(r.get("venta_bruto")),
                safe_decimal(r.get("valor_unitario_bruto")),
                safe_decimal(r.get("costo_unitario_neto")),
                safe_decimal(r.get("margen_clp")),
                safe_decimal(r.get("margen_pct"), MAX_MARGEN_PCT),
                r.get("desc_producto"),
                r.get("categoria_producto"),
                r.get("marca_producto"),
                str(r["id"]) if r.get("id") is not None else None,
                r.get("n_orden"),
                r.get("n_pedido"),
            ))

        # Actualizar ultimo_offset en sync_log
        await conn.execute(
            "UPDATE sync_log SET registros_api=$1, ultimo_offset=$2 WHERE id=$3",
            total_api, offset, log_id
        )

        # Flush parcial cada 500 filas para evitar OOM
        if len(filas_upsert) >= 500:
            await conn.execute("SELECT 1")  # keepalive
            async with conn.transaction():
                await conn.executemany(INSERT_SQL, filas_upsert)
            total_upsert += len(filas_upsert)
            filas_upsert.clear()

        if len(registros) == 0 or len(registros) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        if offset > 50000:  # guard anti-bucle-infinito
            print(f"   [WARN] Abortando paginacion en offset={offset}")
            break

    # Flush final
    if filas_upsert:
        await conn.execute("SELECT 1")  # keepalive
        async with conn.transaction():
            await conn.executemany(INSERT_SQL, filas_upsert)
        total_upsert += len(filas_upsert)

    return total_api, total_upsert, skus_fuera_catalogo


async def primer_mes_incompleto(conn, desde: date) -> date:
    """
    Busca el primer mes desde 'desde' que no fue completado.
    Retorna ese mes para que el sync lo reintente.
    """
    rows = await conn.fetch("""
        SELECT fecha_inicio_datos, estado
        FROM sync_log
        WHERE fecha_inicio_datos >= $1
        ORDER BY fecha_inicio_datos DESC
    """, desde)

    completados = {r["fecha_inicio_datos"] for r in rows if r["estado"] == "completado"}

    cursor = date(desde.year, desde.month, 1)
    hoy = date.today()
    while cursor <= hoy:
        if cursor not in completados:
            return cursor
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)

    return hoy  # todo completo


async def main(args):
    conn = await asyncpg.connect(DATABASE_URL)
    print(f"[OK] Conectado a la BD")

    canal_mapeo  = await cargar_canal_mapeo(conn)
    skus_validos = await cargar_skus_validos(conn)
    print(f"[OK] {len(skus_validos)} SKUs validos | {len(canal_mapeo)} canales mapeados")

    fecha_hasta = args.hasta
    fuentes     = ["bsale", "wivo"]

    # Auto-resume: si no se pasó --desde explícito, detectar primer mes incompleto
    if args.desde == date(2024, 1, 1):
        retomar = await primer_mes_incompleto(conn, date(2024, 1, 1))
        if retomar < date.today():
            print(f"[RESUME] Primer mes incompleto detectado: {retomar}")
            fecha_desde = retomar
        else:
            fecha_desde = args.desde
            print(f"[COMPLETO] Todo sincronizado hasta hoy")
    else:
        fecha_desde = args.desde
        print(f"[INICIO] Sincronizando desde {fecha_desde}")

    # Iterar dia a dia para evitar saltos por paginacion offset inestable
    cursor = fecha_desde
    skus_nuevos: set = set()
    while cursor <= fecha_hasta:
        for fuente in fuentes:
            log_id = await conn.fetchval("""
                INSERT INTO sync_log (fecha_inicio_datos, fecha_fin_datos, fuente, estado)
                VALUES ($1, $2, $3, 'iniciado') RETURNING id
            """, cursor, cursor, fuente)

            try:
                total_api, total_upsert, fuera = await sync_mes(
                    conn, cursor, cursor, fuente,
                    canal_mapeo, skus_validos, log_id
                )
                skus_nuevos |= fuera
                await conn.execute("""
                    UPDATE sync_log
                    SET estado='completado', registros_api=$1, registros_upsert=$2,
                        finalizado_en=NOW()
                    WHERE id=$3
                """, total_api, total_upsert, log_id)
                print(f"[SYNC] {cursor} | {fuente}: {total_api} API -> {total_upsert} upsert")
            except Exception as e:
                await conn.execute("""
                    UPDATE sync_log SET estado='error', error_detalle=$1, finalizado_en=NOW()
                    WHERE id=$2
                """, str(e), log_id)
                print(f"[ERR] {cursor} | {fuente}: {e}")

        cursor += timedelta(days=1)

    if skus_nuevos:
        print(f"\n[ALERTA] {len(skus_nuevos)} SKUs con ventas NO existen en productos:")
        for s in sorted(skus_nuevos):
            print(f"  - {s}")

    # Resumen final
    total_v = await conn.fetchval("SELECT COUNT(*) FROM ventas")
    print(f"\n[OK] Sync completada. Total ventas en BD: {total_v}")
    await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--desde", type=date.fromisoformat, default=date(2024, 1, 1))
    parser.add_argument("--hasta", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    asyncio.run(main(args))
