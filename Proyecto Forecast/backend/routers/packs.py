# routers/packs.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from database import get_db
from models.models import Pack, PackComponente
from schemas.schemas import PackCreate, PackUpdate, PackOut

router = APIRouter()

async def _load_pack(sku: str, db: AsyncSession):
    result = await db.execute(
        select(Pack)
        .options(
            selectinload(Pack.marca),
            selectinload(Pack.categoria),
            selectinload(Pack.temporada),
            selectinload(Pack.componentes)
        )
        .where(Pack.sku == sku)
    )
    return result.scalar_one_or_none()

@router.get("/", response_model=List[PackOut])
async def listar_packs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Pack).options(
            selectinload(Pack.marca), selectinload(Pack.categoria),
            selectinload(Pack.temporada), selectinload(Pack.componentes)
        ).order_by(Pack.sku)
    )
    return result.scalars().all()

@router.get("/{sku}", response_model=PackOut)
async def obtener_pack(sku: str, db: AsyncSession = Depends(get_db)):
    p = await _load_pack(sku, db)
    if not p:
        raise HTTPException(404, f"Pack {sku} no encontrado")
    return p

@router.post("/", response_model=PackOut, status_code=201)
async def crear_pack(data: PackCreate, db: AsyncSession = Depends(get_db)):
    existente = await db.get(Pack, data.sku)
    if existente:
        raise HTTPException(400, f"SKU {data.sku} ya existe")
    componentes = data.componentes
    pack_data = data.model_dump(exclude={"componentes"})
    nuevo = Pack(**pack_data)
    db.add(nuevo)
    await db.flush()
    for comp in componentes:
        db.add(PackComponente(pack_sku=nuevo.sku, **comp.model_dump()))
    await db.commit()
    return await _load_pack(nuevo.sku, db)

@router.put("/{sku}", response_model=PackOut)
async def actualizar_pack(sku: str, data: PackUpdate, db: AsyncSession = Depends(get_db)):
    p = await db.get(Pack, sku)
    if not p:
        raise HTTPException(404, f"Pack {sku} no encontrado")
    update_data = data.model_dump(exclude_none=True, exclude={"componentes"})
    for campo, valor in update_data.items():
        setattr(p, campo, valor)
    if data.componentes is not None:
        # Reemplazar componentes completos
        result = await db.execute(select(PackComponente).where(PackComponente.pack_sku == sku))
        for comp in result.scalars().all():
            await db.delete(comp)
        await db.flush()
        for comp in data.componentes:
            db.add(PackComponente(pack_sku=sku, **comp.model_dump()))
    await db.commit()
    return await _load_pack(sku, db)

@router.delete("/{sku}", status_code=204)
async def eliminar_pack(sku: str, db: AsyncSession = Depends(get_db)):
    p = await db.get(Pack, sku)
    if not p:
        raise HTTPException(404, f"Pack {sku} no encontrado")
    await db.delete(p)
    await db.commit()
