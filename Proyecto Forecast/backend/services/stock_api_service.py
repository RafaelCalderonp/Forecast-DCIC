"""
Sync de stock desde dcic-stock-loader (Railway) — consolida en una sola
llamada lo que antes venían de fuentes separadas: Bsale (bodega Ecommerce),
Full ML, Full Falabella, tránsito y proforma (compras con ETA).

Mapeo de bodegas -> columnas de `stock`:
  10  Ecommerce/Marketplaces      -> stock_base
  3   Bodegas Full MeLi           -> stock_full_ml
  4   Bodegas Full Falabella      -> stock_full_fala
  102 En tránsito · órdenes       -> bodega_transito / eta_transito (ya zarpó,
                                     fecha real de naviera vía B/L)
  101 Proforma (compra con ETA)   -> por_arribar / eta_arribar (aún no zarpa)
  2   Importaciones en Tránsito   -> IGNORADA a propósito. Es el tránsito que
                                     registra Bsale directamente y hoy está
                                     casi vacía; la doc de la API advierte que
                                     sumarla junto a la 102 cuenta la misma
                                     carga dos veces. Lo real "por llegar" es
                                     101 + 102 (el propio servicio ya expone
                                     esa suma en el campo `por_llegar`).
  1   Bodegas Full (legacy)       -> ignorada, siempre 0
"""
import os
from datetime import date
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from logger import get_logger
from services.descontinuados_service import sincronizar_descontinuados


def _parse_eta(valor):
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


log = get_logger("forecast_dcic.stock_api")

STOCK_API_URL = os.getenv("STOCK_API_URL", "https://dcic-stock-loader-production.up.railway.app")
STOCK_API_KEY = os.getenv("STOCK_API_KEY", "")


async def _fetch_stock_api() -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(
            f"{STOCK_API_URL}/api/stock/por-bodega",
            params={"solo_con_stock": "false"},
            headers={"X-API-Key": STOCK_API_KEY},
        )
        r.raise_for_status()
        return r.json()


async def sincronizar_stock_desde_api(db: AsyncSession) -> dict:
    if not STOCK_API_KEY:
        raise RuntimeError("STOCK_API_KEY no configurada")

    data = await _fetch_stock_api()
    stock = data.get("stock", {})
    log.info(f"stock-loader: {data.get('n', len(stock))} SKUs recibidos, actualizado={data.get('actualizado')}")

    skus = list(stock.keys())
    result = await db.execute(text("SELECT sku FROM productos WHERE sku = ANY(:skus)"), {"skus": skus})
    validos = {r[0] for r in result.fetchall()}

    actualizados = 0
    for sku, fila in stock.items():
        if sku not in validos:
            continue
        b = fila.get("bodegas", {})
        eta_bod = fila.get("eta_por_bodega", {}) or {}
        eta_transito = _parse_eta(eta_bod.get("102"))
        eta_arribar = _parse_eta(eta_bod.get("101"))

        await db.execute(text("""
            INSERT INTO stock (
                sku, stock_base, stock_full_ml, stock_full_fala,
                bodega_transito, eta_transito, por_arribar, eta_arribar, fecha_actualizacion
            )
            VALUES (:sku, :base, :ml, :fala, :transito, :eta_transito, :arribar, :eta_arribar, CURRENT_DATE)
            ON CONFLICT (sku) DO UPDATE SET
                stock_base      = EXCLUDED.stock_base,
                stock_full_ml   = EXCLUDED.stock_full_ml,
                stock_full_fala = EXCLUDED.stock_full_fala,
                bodega_transito = EXCLUDED.bodega_transito,
                eta_transito    = EXCLUDED.eta_transito,
                por_arribar     = EXCLUDED.por_arribar,
                eta_arribar     = EXCLUDED.eta_arribar,
                fecha_actualizacion = CURRENT_DATE,
                updated_at      = NOW()
        """), {
            "sku": sku,
            "base": int(b.get("10", 0)),
            "ml": int(b.get("3", 0)),
            "fala": int(b.get("4", 0)),
            "transito": int(b.get("102", 0)),
            "eta_transito": eta_transito,
            "arribar": int(b.get("101", 0)),
            "eta_arribar": eta_arribar,
        })
        actualizados += 1

    await db.commit()
    cambios = await sincronizar_descontinuados(db)

    resultado = {
        "actualizados": actualizados,
        "ignorados": len(skus) - actualizados,
        "actualizado_fuente": data.get("actualizado"),
        **cambios,
    }
    log.info(f"sync stock-loader: {actualizados} actualizados, {resultado['ignorados']} ignorados")
    return resultado
