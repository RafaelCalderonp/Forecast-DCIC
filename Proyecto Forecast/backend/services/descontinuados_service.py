"""
Regla automática de descontinuación de productos.

  - Producto marcado para descontinuar (comentario='Descontinuar' o
    por_discontinuar=True) cuyo stock total llega a 0
        -> se desactiva (activo=False) y se limpia la marca.
  - Producto inactivo que recibe stock > 0 (ej. compra por clasificación ABC)
        -> se reactiva marcado 'por descontinuar' para liquidar ese stock,
           en vez de volver a ser un producto activo normal.

Se ejecuta después de cualquier operación que modifique stock (Excel, Bsale,
bulk-upsert manual) y además vía job nocturno como respaldo.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from logger import get_logger

log = get_logger("forecast_dcic.descontinuados")

_STOCK_TOTAL_SUBQ = """
    COALESCE((
        SELECT stock_base + stock_full_ml + stock_full_fala
               + bodega_transito + por_arribar + pi
        FROM stock WHERE stock.sku = p.sku
    ), 0)
"""


async def sincronizar_descontinuados(db: AsyncSession) -> dict:
    desactivados = await db.execute(text(f"""
        UPDATE productos p SET
            activo = FALSE,
            por_discontinuar = FALSE,
            comentario = NULL
        WHERE p.activo = TRUE
          AND (p.comentario = 'Descontinuar' OR p.por_discontinuar = TRUE)
          AND {_STOCK_TOTAL_SUBQ} = 0
        RETURNING p.sku
    """))
    skus_desactivados = [r[0] for r in desactivados.fetchall()]

    reactivados = await db.execute(text(f"""
        UPDATE productos p SET
            activo = TRUE,
            por_discontinuar = TRUE,
            comentario = 'Descontinuar'
        WHERE p.activo = FALSE
          AND {_STOCK_TOTAL_SUBQ} > 0
        RETURNING p.sku
    """))
    skus_reactivados = [r[0] for r in reactivados.fetchall()]

    await db.commit()

    if skus_desactivados:
        log.info(f"Auto-descontinuados (stock llegó a 0): {len(skus_desactivados)} SKUs -> {skus_desactivados[:15]}")
    if skus_reactivados:
        log.info(f"Auto-marcados por_discontinuar (inactivo recibió stock): {len(skus_reactivados)} SKUs -> {skus_reactivados[:15]}")

    return {"desactivados": skus_desactivados, "reactivados": skus_reactivados}
