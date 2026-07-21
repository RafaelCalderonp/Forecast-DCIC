# routers/marcas.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from database import get_db
from models.models import Marca
from schemas.schemas import MarcaCreate, MarcaOut

router = APIRouter()

@router.get("/", response_model=List[MarcaOut])
async def listar(db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Marca).order_by(Marca.nombre))
    return r.scalars().all()

@router.post("/", response_model=MarcaOut, status_code=201)
async def crear(data: MarcaCreate, db: AsyncSession = Depends(get_db)):
    nuevo = Marca(**data.model_dump())
    db.add(nuevo)
    await db.commit()
    await db.refresh(nuevo)
    return nuevo

@router.delete("/{id}", status_code=204)
async def eliminar(id: int, db: AsyncSession = Depends(get_db)):
    m = await db.get(Marca, id)
    if not m:
        raise HTTPException(404, "Marca no encontrada")
    await db.delete(m)
    await db.commit()
