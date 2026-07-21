"""
Conector ERP Externo → Forecast DCIC
=====================================
Sincroniza ventas desde la API externa (Bsale/Wivo) al endpoint local
POST /api/ventas/upsert-bulk usando autenticación X-API-Key.

Uso:
  python sync_erp_externo.py [--desde YYYY-MM-DD] [--hasta YYYY-MM-DD]
                             [--fuente bsale|wivo|all]
                             [--dry-run]

Variables de entorno:
  FORECAST_API_URL   URL base del Forecast DCIC  (default: http://localhost:8000)
  FORECAST_API_KEY   API Key generada en /api/auth/api-keys
  ERP_API_URL        URL base del ERP externo     (default: https://dcic-api-production.up.railway.app)

Notas:
  - id_externo = "<num_pedido>-<num_suborden>" cuando están disponibles,
    o fallback a "<fuente>-<fecha>-<sku>-<canal>-<indice>" para evitar duplicados.
  - El endpoint externo entrega ~50% de la cobertura total (ver INFORME_API_ADMINISTRADOR.md).
    Esta limitación es del proveedor externo, no del conector.
"""

import argparse
import os
import sys
import time
import httpx
from datetime import date, timedelta
from logger import get_logger

log = get_logger("forecast_dcic.sync_erp")

# ── Configuración ─────────────────────────────────────────────────────────────

ERP_API_URL   = os.getenv("ERP_API_URL",   "https://dcic-api-production.up.railway.app")
FORECAST_URL  = os.getenv("FORECAST_API_URL", "http://localhost:8000")
API_KEY       = os.getenv("FORECAST_API_KEY", "")

PAGE_SIZE     = 100    # registros por página al leer el ERP externo (máx 100 según API)
BATCH_SIZE    = 500    # registros por lote al hacer upsert-bulk local
MAX_RETRIES   = 3
RETRY_DELAY   = 2      # segundos entre reintentos

# Canales conocidos que NO están en el ERP externo (ver informe sección 2.2)
CANALES_FALTANTES_EN_API = {"Petwoow", "Segunda Seleccion", "Dafiti", "Cta cte Personal"}


# ── Mapeo de campos ───────────────────────────────────────────────────────────

def _id_externo(row: dict, idx: int) -> str:
    """Construye un id_externo único y estable para la fila."""
    num_pedido  = row.get("num_pedido") or ""
    num_suborden = row.get("num_suborden") or ""
    if num_pedido and num_suborden:
        return f"{num_pedido}-{num_suborden}"
    if num_pedido:
        return f"{num_pedido}-{idx}"
    # Fallback determinístico
    fuente = row.get("fuente") or "erp"
    fecha  = row.get("fecha") or "0000-00-00"
    sku    = row.get("sku_id") or row.get("sku") or "NOSKU"
    canal  = (row.get("canal") or "").replace(" ", "_")
    return f"{fuente}-{fecha}-{sku}-{canal}-{idx}"


def _to_venta_upsert(row: dict, idx: int) -> dict:
    """Convierte un registro del ERP externo al schema VentaUpsert."""
    estado = row.get("estado_orden") or "Regular"
    # Calcular unidades devueltas: si el estado indica devolución, marcar cantidad como devuelta
    cantidad = int(row.get("cantidad") or 0)
    devueltas = cantidad if estado.lower() in {"devuelta", "devueltas"} else 0

    return {
        "id_externo":          _id_externo(row, idx),
        "fuente":              row.get("fuente") or "bsale",
        "sku":                 row.get("sku_id") or row.get("sku") or "",
        "fecha":               row.get("fecha") or str(date.today()),
        "canal":               row.get("canal"),
        "cantidad":            cantidad,
        "unidades_devueltas":  devueltas,
        "precio_total_bruto":  row.get("venta_bruto"),
        "valor_unitario_neto": row.get("valor_unitario_bruto"),
        "costo_unitario_clp":  row.get("costo_unitario_neto"),
        "margen_clp":          row.get("margen_clp"),
        "margen_pct":          row.get("margen_pct"),
        "descripcion_producto":row.get("desc_producto"),
        "categoria_erp":       row.get("categoria_producto"),
        "marca_erp":           row.get("marca_producto"),
        "estado_orden":        estado,
    }


# ── Lectura del ERP externo ───────────────────────────────────────────────────

def _fetch_page(client: httpx.Client, fuente: str, desde: str, hasta: str, offset: int) -> tuple[list, int]:
    """
    Descarga una página de ventas del ERP externo.
    Retorna (filas, total_count).
    """
    params = {
        "fecha_desde": desde,
        "fecha_hasta": hasta,
        "limit":  PAGE_SIZE,
        "offset": offset,
    }
    if fuente != "all":
        params["fuente"] = fuente

    for intento in range(1, MAX_RETRIES + 1):
        try:
            r = client.get(f"{ERP_API_URL}/ventas/", params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            # El ERP puede devolver lista directa o dict con "data"/"items"
            if isinstance(data, list):
                filas = data
                total = int(r.headers.get("X-Total-Count", len(filas) + offset))
            elif isinstance(data, dict):
                filas = data.get("data") or data.get("items") or data.get("ventas") or []
                total = int(
                    r.headers.get("X-Total-Count")
                    or data.get("total")
                    or data.get("count")
                    or (len(filas) + offset)
                )
            else:
                filas, total = [], 0
            return filas, total
        except httpx.HTTPStatusError as e:
            try:
                body = e.response.text[:800]
            except Exception:
                body = ""
            log.warning(f"HTTP {e.response.status_code} al leer ERP (intento {intento}): {body}")
        except Exception as e:
            log.warning(f"Error al leer ERP (intento {intento}): {e}")
        if intento < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    return [], 0


def fetch_all_ventas(fuente: str, desde: str, hasta: str) -> list[dict]:
    """Descarga todas las ventas del ERP externo para el rango dado."""
    log.info(f"Iniciando lectura ERP externo — fuente={fuente} desde={desde} hasta={hasta}")
    all_rows = []

    with httpx.Client(follow_redirects=True) as client:
        offset = 0
        total  = None
        while True:
            filas, total_api = _fetch_page(client, fuente, desde, hasta, offset)
            if total is None:
                total = total_api
                log.info(f"Total anunciado por ERP: {total:,} registros")
                if total == 0 and not filas:
                    log.warning("ERP retornó 0 registros. Verificar rango de fechas y fuente.")
                    break

            if not filas:
                break

            all_rows.extend(filas)
            offset += len(filas)
            log.info(f"  Página descargada: {len(filas)} filas | acumulado: {len(all_rows):,} / {total:,}")

            if len(all_rows) >= total or len(filas) < PAGE_SIZE:
                break

    log.info(f"Descarga completa: {len(all_rows):,} filas obtenidas")
    if total and len(all_rows) < total * 0.9:
        log.warning(
            f"Cobertura incompleta: se obtuvieron {len(all_rows):,} de {total:,} "
            f"({len(all_rows)/total*100:.0f}%). Esto es conocido (ver INFORME_API_ADMINISTRADOR.md §2.1)."
        )
    return all_rows


# ── Envío al Forecast DCIC ────────────────────────────────────────────────────

def _send_batch(client: httpx.Client, batch: list[dict], dry_run: bool) -> dict:
    """Envía un lote a POST /api/ventas/upsert-bulk."""
    if dry_run:
        return {"insertados": 0, "actualizados": 0, "omitidos_cancelados": 0, "errores": [], "dry_run": True}

    for intento in range(1, MAX_RETRIES + 1):
        try:
            r = client.post(
                f"{FORECAST_URL}/api/ventas/upsert-bulk",
                json=batch,
                headers={"X-API-Key": API_KEY},
                timeout=60,
            )
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            body = ""
            try:
                body = e.response.text[:500]
            except Exception:
                pass
            log.warning(f"HTTP {e.response.status_code} al enviar lote (intento {intento}): {body}")
        except Exception as e:
            log.warning(f"Error al enviar lote (intento {intento}): {e}")
        if intento < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    return {"insertados": 0, "actualizados": 0, "omitidos_cancelados": 0, "errores": [{"error": "max_retries"}]}


def push_to_forecast(rows: list[dict], dry_run: bool) -> dict:
    """Transforma y envía todas las filas al Forecast DCIC en lotes."""
    payloads = [_to_venta_upsert(r, i) for i, r in enumerate(rows)]
    # Descartar filas sin SKU
    validas = [p for p in payloads if p["sku"]]
    omitidas_sin_sku = len(payloads) - len(validas)
    if omitidas_sin_sku:
        log.warning(f"{omitidas_sin_sku} filas descartadas por SKU vacío")

    totales = {"insertados": 0, "actualizados": 0, "omitidos_cancelados": 0, "errores": []}

    with httpx.Client() as client:
        for start in range(0, len(validas), BATCH_SIZE):
            batch = validas[start: start + BATCH_SIZE]
            result = _send_batch(client, batch, dry_run)
            totales["insertados"]         += result.get("insertados", 0)
            totales["actualizados"]       += result.get("actualizados", 0)
            totales["omitidos_cancelados"]+= result.get("omitidos_cancelados", 0)
            totales["errores"].extend(result.get("errores", []))
            log.info(
                f"  Lote {start//BATCH_SIZE + 1}: "
                f"+{result.get('insertados',0)} ins / "
                f"~{result.get('actualizados',0)} upd / "
                f"{result.get('omitidos_cancelados',0)} omit"
            )

    return totales


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sincroniza ventas del ERP externo al Forecast DCIC")
    parser.add_argument("--desde",   default=str(date.today() - timedelta(days=30)), help="Fecha inicio YYYY-MM-DD")
    parser.add_argument("--hasta",   default=str(date.today()), help="Fecha fin YYYY-MM-DD")
    parser.add_argument("--fuente",  default="all", choices=["bsale", "wivo", "all"], help="Fuente de datos")
    parser.add_argument("--dry-run", action="store_true", help="Solo descarga, no inserta")
    args = parser.parse_args()

    if not API_KEY and not args.dry_run:
        log.error("Variable FORECAST_API_KEY no configurada. Usa --dry-run o exporta la variable.")
        sys.exit(1)

    log.info("=" * 60)
    log.info(f"  SYNC ERP EXTERNO → FORECAST DCIC")
    log.info(f"  Desde:    {args.desde}  |  Hasta: {args.hasta}")
    log.info(f"  Fuente:   {args.fuente}")
    log.info(f"  Dry-run:  {args.dry_run}")
    log.info(f"  ERP URL:  {ERP_API_URL}")
    log.info(f"  FCST URL: {FORECAST_URL}")
    log.info("=" * 60)

    log.warning(
        f"Nota: Los canales {CANALES_FALTANTES_EN_API} no están expuestos por el ERP externo. "
        "Deben importarse manualmente desde Excel (solución transitoria vigente)."
    )

    # 1. Descargar ventas del ERP externo
    t0 = time.perf_counter()
    rows = fetch_all_ventas(args.fuente, args.desde, args.hasta)

    # 2. Enviar al Forecast DCIC
    if rows:
        result = push_to_forecast(rows, args.dry_run)
        elapsed = round(time.perf_counter() - t0, 1)

        log.info("=" * 60)
        log.info(f"  RESULTADO FINAL  ({elapsed}s)")
        log.info(f"  Insertados:   {result['insertados']:>6,}")
        log.info(f"  Actualizados: {result['actualizados']:>6,}")
        log.info(f"  Omitidos:     {result['omitidos_cancelados']:>6,}")
        log.info(f"  Errores:      {len(result['errores']):>6,}")
        if result['errores']:
            for err in result['errores'][:5]:
                log.warning(f"    Error: {err}")
        log.info("=" * 60)
    else:
        log.warning("No se descargaron filas. Sync sin efecto.")


if __name__ == "__main__":
    main()
