"""Endpoint de migración — solo activo con MIGRATION_MODE=1. No exponer en producción."""
import os
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from database import get_db
from auth import require_rol

router = APIRouter(tags=["migracion"])

def nom_propio(s: str) -> str:
    if not s or not isinstance(s, str):
        return s
    conectores = {'de','del','la','las','el','los','y','a','en','con','para','por','o','e','al','un','una','unos','unas'}
    palabras = s.strip().split()
    resultado = []
    for i, p in enumerate(palabras):
        if i == 0 or p.lower() not in conectores:
            resultado.append(p[0].upper() + p[1:] if p else p)
        else:
            resultado.append(p.lower())
    return ' '.join(resultado)

@router.post("/run", dependencies=[Depends(require_rol("admin"))])
async def run_migration(db: AsyncSession = Depends(get_db)):
    await db.execute(text("ALTER TABLE productos ADD COLUMN IF NOT EXISTS tipo_producto VARCHAR(150)"))
    await db.commit()
    return {"ok": True, "msg": "columna tipo_producto lista"}

@router.post("/importar-clasificacion", dependencies=[Depends(require_rol("admin"))])
async def importar_clasificacion(
    archivo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Recibe el Excel de clasificación como archivo adjunto — sin rutas hardcodeadas."""
    import io
    contenido = await archivo.read()
    df = pd.read_excel(io.BytesIO(contenido), header=1)
    df.columns = ['SKU','Producto','Marca','Categoria_Principal','Subcategoria','Tipo_Producto','Temporada']
    df = df.dropna(subset=['SKU'])

    df['SKU']           = df['SKU'].astype(str).str.strip()
    df['Subcategoria']  = df['Subcategoria'].fillna('').astype(str).str.strip().apply(lambda x: nom_propio(x) if x else None)
    df['Tipo_Producto'] = df['Tipo_Producto'].fillna('').astype(str).str.strip().apply(lambda x: nom_propio(x) if x else None)

    # Cargar mapa nombre -> id de subcategorias
    res = await db.execute(text("SELECT id, nombre FROM subcategorias"))
    subcat_map = {row[1].strip().lower(): row[0] for row in res.fetchall()}

    ok_tipo = 0
    ok_sub  = 0
    sin_match_db   = 0
    sin_match_sub  = 0

    for _, row in df.iterrows():
        sku       = row['SKU']
        tipo      = row['Tipo_Producto']
        subcat    = row['Subcategoria']

        # Buscar el producto en DB
        exists = await db.execute(text("SELECT sku FROM productos WHERE sku = :sku"), {'sku': sku})
        if not exists.fetchone():
            sin_match_db += 1
            continue

        # Actualizar tipo_producto
        if tipo:
            await db.execute(text("UPDATE productos SET tipo_producto = :tipo WHERE sku = :sku"), {'tipo': tipo, 'sku': sku})
            ok_tipo += 1

        # Actualizar subcategoria_id si se encuentra el nombre en subcategorias
        if subcat:
            subcat_id = subcat_map.get(subcat.lower())
            if subcat_id:
                await db.execute(
                    text("UPDATE productos SET subcategoria_id = :sid WHERE sku = :sku"),
                    {'sid': subcat_id, 'sku': sku}
                )
                ok_sub += 1
            else:
                sin_match_sub += 1

    await db.commit()

    sin_tipo = await db.execute(text("SELECT COUNT(*) FROM productos WHERE tipo_producto IS NULL OR tipo_producto = ''"))
    sin_sub  = await db.execute(text("SELECT COUNT(*) FROM productos WHERE subcategoria_id IS NULL"))

    return {
        "ok": True,
        "tipo_producto_actualizados": ok_tipo,
        "subcategoria_actualizados":  ok_sub,
        "sku_sin_match_db":           sin_match_db,
        "subcategoria_sin_match":     sin_match_sub,
        "productos_sin_tipo_aun":     sin_tipo.scalar(),
        "productos_sin_subcat_aun":   sin_sub.scalar(),
    }

# Mantener el endpoint anterior por compatibilidad
@router.post("/importar-tipo-producto", dependencies=[Depends(require_rol("admin"))])
async def importar_tipo_producto(archivo: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    return await importar_clasificacion(archivo, db)
