# routers/productos.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from typing import List
from decimal import Decimal, ROUND_HALF_UP
import pandas as pd
import io

from database import get_db
from models.models import Producto, Marca, Categoria, Subcategoria
from schemas.schemas import ProductoCreate, ProductoUpdate, ProductoOut

router = APIRouter()

def calcular_precio_neto(bruto: Decimal) -> Decimal:
    """Precio neto = round(bruto / 1.19, 2)"""
    return (bruto / Decimal("1.19")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def redondear_bruto(bruto: Decimal) -> Decimal:
    return bruto.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

async def get_or_create_marca(nombre: str, db: AsyncSession) -> int:
    r = await db.execute(select(Marca).where(Marca.nombre == nombre.strip()))
    marca = r.scalar_one_or_none()
    if not marca:
        marca = Marca(nombre=nombre.strip())
        db.add(marca)
        await db.flush()
    return marca.id

async def get_or_create_categoria(nombre: str, db: AsyncSession) -> int:
    r = await db.execute(select(Categoria).where(Categoria.nombre == nombre.strip()))
    cat = r.scalar_one_or_none()
    if not cat:
        cat = Categoria(nombre=nombre.strip())
        db.add(cat)
        await db.flush()
    return cat.id

async def _load_producto(sku: str, db: AsyncSession):
    result = await db.execute(
        select(Producto)
        .options(selectinload(Producto.marca), selectinload(Producto.categoria), selectinload(Producto.subcategoria), selectinload(Producto.temporada))
        .where(Producto.sku == sku)
    )
    return result.scalar_one_or_none()

@router.get("/", response_model=List[ProductoOut])
async def listar_productos(
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Producto)
        .options(selectinload(Producto.marca), selectinload(Producto.categoria), selectinload(Producto.subcategoria), selectinload(Producto.temporada))
        .order_by(Producto.sku)
        .offset(offset)
        .limit(limit)
    )
    productos = result.scalars().all()

    # Stock total por SKU
    stock_rows = await db.execute(text("""
        SELECT sku,
               COALESCE(stock_jun,0)
               + COALESCE(llegada_jun,0) + COALESCE(llegada_jul,0)
               + COALESCE(llegada_ago,0) + COALESCE(llegada_sep,0)
               + COALESCE(llegada_oct,0) + COALESCE(llegada_nov,0)
               + COALESCE(llegada_dic,0) AS stock_total
        FROM stock
    """))
    stock_map = {r["sku"]: int(r["stock_total"]) for r in stock_rows.mappings()}

    for p in productos:
        p.stock_total = stock_map.get(p.sku, 0)

    return productos

@router.get("/{sku}", response_model=ProductoOut)
async def obtener_producto(sku: str, db: AsyncSession = Depends(get_db)):
    p = await _load_producto(sku, db)
    if not p:
        raise HTTPException(404, f"Producto {sku} no encontrado")
    return p

@router.post("/", response_model=ProductoOut, status_code=201)
async def crear_producto(data: ProductoCreate, db: AsyncSession = Depends(get_db)):
    existente = await db.get(Producto, data.sku)
    if existente:
        raise HTTPException(400, f"SKU {data.sku} ya existe")
    # Redondear bruto y calcular neto
    bruto = redondear_bruto(Decimal(str(data.precio_venta_bruto)))
    neto  = calcular_precio_neto(bruto)
    nuevo = Producto(**{**data.model_dump(), "precio_venta_bruto": bruto, "precio_venta_neto": neto})
    db.add(nuevo)
    await db.commit()
    return await _load_producto(nuevo.sku, db)

@router.put("/{sku}", response_model=ProductoOut)
async def actualizar_producto(sku: str, data: ProductoUpdate, db: AsyncSession = Depends(get_db)):
    p = await db.get(Producto, sku)
    if not p:
        raise HTTPException(404, f"Producto {sku} no encontrado")
    update = data.model_dump(exclude_unset=True)
    if "precio_venta_bruto" in update:
        bruto = redondear_bruto(Decimal(str(update["precio_venta_bruto"])))
        update["precio_venta_bruto"] = bruto
        update["precio_venta_neto"]  = calcular_precio_neto(bruto)
    for campo, valor in update.items():
        setattr(p, campo, valor)
    await db.commit()
    return await _load_producto(sku, db)

@router.delete("/{sku}", status_code=204)
async def eliminar_producto(sku: str, db: AsyncSession = Depends(get_db)):
    p = await db.get(Producto, sku)
    if not p:
        raise HTTPException(404, f"Producto {sku} no encontrado")
    await db.delete(p)
    await db.commit()

@router.post("/carga-masiva", status_code=201)
async def carga_masiva_excel(
    file: UploadFile = File(...),
    modo: str = Form("upsert"),
    db: AsyncSession = Depends(get_db)
):
    """
    Carga masiva desde Excel.
    modo=upsert (default): crea o actualiza
    modo=nuevo: solo crea, error si SKU ya existe
    modo=actualizar: solo actualiza SKUs existentes, columnas opcionales
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "El archivo debe ser .xlsx o .xls")
    if modo not in ("upsert", "nuevo", "actualizar"):
        raise HTTPException(400, "modo debe ser: upsert, nuevo o actualizar")

    contenido = await file.read()
    df = pd.read_excel(io.BytesIO(contenido))
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    if "sku" not in df.columns:
        raise HTTPException(400, "Columna SKU es obligatoria")

    if modo in ("upsert", "nuevo"):
        columnas_req = {"sku", "marca", "categoria", "temporada", "descripcion", "precio_bruto"}
        if not columnas_req.issubset(set(df.columns)):
            raise HTTPException(400, f"Para modo '{modo}' se requieren: {columnas_req}. Encontradas: {set(df.columns)}")

    creados = 0
    actualizados = 0
    errores = []

    for idx, row in df.iterrows():
        try:
            sku = str(row["sku"]).strip()
            existente = await db.get(Producto, sku)

            if modo == "nuevo" and existente:
                errores.append({"fila": idx + 2, "error": f"SKU {sku} ya existe (modo: solo nuevos)"})
                continue
            if modo == "actualizar" and not existente:
                errores.append({"fila": idx + 2, "error": f"SKU {sku} no existe (modo: solo actualizar)"})
                continue

            if modo in ("upsert", "nuevo"):
                bruto = redondear_bruto(Decimal(str(row["precio_bruto"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                neto  = calcular_precio_neto(bruto)
                marca_id     = await get_or_create_marca(str(row["marca"]), db)
                cat_id       = await get_or_create_categoria(str(row["categoria"]), db)
                temporada_id = int(row["temporada"]) if pd.notna(row["temporada"]) else None
                descripcion  = str(row["descripcion"]).strip() if pd.notna(row["descripcion"]) else None

                if existente:
                    existente.marca_id = marca_id; existente.categoria_id = cat_id
                    existente.temporada_id = temporada_id; existente.descripcion = descripcion
                    existente.precio_venta_bruto = bruto; existente.precio_venta_neto = neto
                    actualizados += 1
                else:
                    db.add(Producto(sku=sku, marca_id=marca_id, categoria_id=cat_id,
                                    temporada_id=temporada_id, descripcion=descripcion,
                                    precio_venta_bruto=bruto, precio_venta_neto=neto))
                    creados += 1

            else:  # modo == "actualizar" — solo campos presentes en el Excel
                cols = set(df.columns)
                if "marca" in cols and pd.notna(row["marca"]):
                    existente.marca_id = await get_or_create_marca(str(row["marca"]), db)
                if "categoria" in cols and pd.notna(row["categoria"]):
                    existente.categoria_id = await get_or_create_categoria(str(row["categoria"]), db)
                if "temporada" in cols and pd.notna(row["temporada"]):
                    existente.temporada_id = int(row["temporada"])
                if "descripcion" in cols and pd.notna(row["descripcion"]):
                    existente.descripcion = str(row["descripcion"]).strip()
                if "precio_bruto" in cols and pd.notna(row["precio_bruto"]):
                    bruto = redondear_bruto(Decimal(str(row["precio_bruto"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                    existente.precio_venta_bruto = bruto
                    existente.precio_venta_neto  = calcular_precio_neto(bruto)
                if "comentario" in cols and pd.notna(row["comentario"]):
                    existente.comentario = str(row["comentario"]).strip() or None
                if "activo" in cols and pd.notna(row["activo"]):
                    val = str(row["activo"]).strip().lower()
                    existente.activo = val in ("1", "true", "si", "sí", "yes")
                actualizados += 1

        except Exception as e:
            errores.append({"fila": idx + 2, "error": str(e)})

    await db.commit()
    return {"creados": creados, "actualizados": actualizados, "errores": errores}
