"""
Sync Stock Bsale → Forecast DCIC
=================================
Trae el stock de la bodega "Ecommerce" en Bsale y lo carga en la
columna stock_base de la tabla stock (sin tocar Full ML, Full Fala,
tránsito, por arribar ni PI).

Uso:
  python sync_stock_bsale.py [--dry-run]

Variables de entorno (.env):
  BSALE_ACCESS_TOKEN   Token de acceso de Bsale (header access_token)
  BSALE_OFICINA        Nombre de la oficina/bodega a sincronizar (default: Ecommerce)
  FORECAST_API_URL     URL base del Forecast DCIC (default: http://localhost:8000)

Bsale API: GET https://api.bsale.io/v1/stocks.json?expand=[variant,office]
Cada item trae variant.code (SKU) y office.name (bodega).
"""

import argparse
import os
import sys
import time
import httpx
from dotenv import load_dotenv
from logger import get_logger

load_dotenv()

log = get_logger("forecast_dcic.sync_stock_bsale")

BSALE_URL      = "https://api.bsale.io/v1/stocks.json"
BSALE_TOKEN    = os.getenv("BSALE_ACCESS_TOKEN", "")
BSALE_OFICINA  = os.getenv("BSALE_OFICINA", "Ecommerce")
FORECAST_URL   = os.getenv("FORECAST_API_URL", "http://localhost:8000")

PAGE_SIZE   = 50
MAX_RETRIES = 3
RETRY_DELAY = 2


def fetch_stocks_bsale() -> list[dict]:
    """Descarga todo el stock de Bsale, expandiendo variant y office."""
    log.info(f"Leyendo stock desde Bsale (bodega objetivo: '{BSALE_OFICINA}')")
    all_items = []

    with httpx.Client(headers={"access_token": BSALE_TOKEN}, timeout=30) as client:
        offset = 0
        while True:
            params = {"expand": "[variant,office]", "limit": PAGE_SIZE, "offset": offset}
            filas = None
            for intento in range(1, MAX_RETRIES + 1):
                try:
                    r = client.get(BSALE_URL, params=params)
                    r.raise_for_status()
                    data = r.json()
                    filas = data.get("items", [])
                    break
                except httpx.HTTPStatusError as e:
                    body = e.response.text[:500] if e.response is not None else ""
                    log.warning(f"HTTP {e.response.status_code} al leer Bsale (intento {intento}): {body}")
                except Exception as e:
                    log.warning(f"Error al leer Bsale (intento {intento}): {e}")
                if intento < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)

            if filas is None:
                log.error(f"No se pudo leer la página offset={offset} tras {MAX_RETRIES} intentos. Abortando.")
                break
            if not filas:
                break

            all_items.extend(filas)
            log.info(f"  Página offset={offset}: {len(filas)} filas | acumulado: {len(all_items)}")
            offset += len(filas)
            if len(filas) < PAGE_SIZE:
                break

    log.info(f"Descarga completa: {len(all_items)} registros de stock (todas las bodegas)")
    return all_items


def filtrar_y_agrupar(items: list[dict]) -> dict[str, int]:
    """Filtra por bodega BSALE_OFICINA y agrupa cantidad disponible por SKU (variant.code)."""
    por_sku: dict[str, int] = {}
    sin_office = 0
    otras_bodegas = 0

    for item in items:
        office = item.get("office") or {}
        variant = item.get("variant") or {}
        office_name = (office.get("name") or "").strip()
        sku = (variant.get("code") or "").strip()

        if not office_name:
            sin_office += 1
            continue
        if BSALE_OFICINA.lower() not in office_name.lower():
            otras_bodegas += 1
            continue
        if not sku:
            continue

        cantidad = item.get("quantityAvailable")
        if cantidad is None:
            cantidad = item.get("quantity", 0)
        por_sku[sku] = por_sku.get(sku, 0) + int(float(cantidad or 0))

    log.info(
        f"Filtrado: {len(por_sku)} SKUs en bodega '{BSALE_OFICINA}' | "
        f"{otras_bodegas} filas de otras bodegas ignoradas | {sin_office} sin bodega"
    )
    return por_sku


def push_to_forecast(stock_por_sku: dict[str, int], dry_run: bool) -> dict:
    if dry_run:
        log.info(f"[DRY-RUN] Se enviarían {len(stock_por_sku)} SKUs. Ejemplo: {dict(list(stock_por_sku.items())[:5])}")
        return {"actualizados": 0, "ignorados": 0, "dry_run": True}

    items = [{"sku": sku, "stock_base": cant} for sku, cant in stock_por_sku.items()]

    with httpx.Client(timeout=60) as client:
        r = client.post(f"{FORECAST_URL}/api/stock/sync-base", json=items)
        r.raise_for_status()
        return r.json()


def main():
    parser = argparse.ArgumentParser(description="Sincroniza stock_base desde Bsale (bodega Ecommerce)")
    parser.add_argument("--dry-run", action="store_true", help="Solo descarga y muestra, no escribe en la BD")
    args = parser.parse_args()

    if not BSALE_TOKEN:
        log.error("Variable BSALE_ACCESS_TOKEN no configurada en .env")
        sys.exit(1)

    log.info("=" * 60)
    log.info("  SYNC STOCK BSALE → FORECAST DCIC")
    log.info(f"  Bodega objetivo: {BSALE_OFICINA}")
    log.info(f"  Dry-run: {args.dry_run}")
    log.info("=" * 60)

    t0 = time.perf_counter()
    items = fetch_stocks_bsale()
    if not items:
        log.warning("No se obtuvieron registros de Bsale. Sync sin efecto.")
        return

    stock_por_sku = filtrar_y_agrupar(items)
    if not stock_por_sku:
        log.warning(f"Ningún SKU encontrado en bodega '{BSALE_OFICINA}'. Revisa BSALE_OFICINA en .env.")
        return

    result = push_to_forecast(stock_por_sku, args.dry_run)
    elapsed = round(time.perf_counter() - t0, 1)

    log.info("=" * 60)
    log.info(f"  RESULTADO FINAL ({elapsed}s)")
    log.info(f"  Actualizados: {result.get('actualizados', 0)}")
    log.info(f"  Ignorados (SKU no existe en productos): {result.get('ignorados', 0)}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
