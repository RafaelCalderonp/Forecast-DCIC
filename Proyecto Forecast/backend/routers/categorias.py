# routers/categorias.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from database import get_db
from models.models import Categoria
from schemas.schemas import CategoriaCreate, CategoriaOut

router = APIRouter()

@router.get("/", response_model=List[CategoriaOut])
async def listar(db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Categoria).order_by(Categoria.nombre))
    return r.scalars().all()

@router.post("/", response_model=CategoriaOut, status_code=201)
async def crear(data: CategoriaCreate, db: AsyncSession = Depends(get_db)):
    nuevo = Categoria(**data.model_dump())
    db.add(nuevo)
    await db.commit()
    await db.refresh(nuevo)
    return nuevo

@router.delete("/{id}", status_code=204)
async def eliminar(id: int, db: AsyncSession = Depends(get_db)):
    c = await db.get(Categoria, id)
    if not c:
        raise HTTPException(404, "Categoría no encontrada")
    await db.delete(c)
    await db.commit()
