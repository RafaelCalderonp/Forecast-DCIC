# routers/temporadas.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from database import get_db
from models.models import Temporada
from schemas.schemas import TemporadaCreate, TemporadaOut

router = APIRouter()

@router.get("/", response_model=List[TemporadaOut])
async def listar(db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Temporada).order_by(Temporada.fecha_inicio))
    return r.scalars().all()

@router.post("/", response_model=TemporadaOut, status_code=201)
async def crear(data: TemporadaCreate, db: AsyncSession = Depends(get_db)):
    nuevo = Temporada(**data.model_dump())
    db.add(nuevo)
    await db.commit()
    await db.refresh(nuevo)
    return nuevo

@router.put("/{id}", response_model=TemporadaOut)
async def actualizar(id: int, data: TemporadaCreate, db: AsyncSession = Depends(get_db)):
    t = await db.get(Temporada, id)
    if not t:
        raise HTTPException(404, "Temporada no encontrada")
    for campo, valor in data.model_dump().items():
        setattr(t, campo, valor)
    await db.commit()
    await db.refresh(t)
    return t

@router.delete("/{id}", status_code=204)
async def eliminar(id: int, db: AsyncSession = Depends(get_db)):
    t = await db.get(Temporada, id)
    if not t:
        raise HTTPException(404, "Temporada no encontrada")
    await db.delete(t)
    await db.commit()
