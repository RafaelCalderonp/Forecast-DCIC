"""
Router de gestión de API Keys M2M.
Solo accesible para admin. Permite crear, listar y revocar keys.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional

from database import get_db
from auth import require_rol, generar_api_key

router = APIRouter()


class CrearApiKeyRequest(BaseModel):
    nombre: str


@router.post("/", status_code=201)
async def crear_api_key(
    req: CrearApiKeyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_rol("admin")),
):
    """Crea una nueva API Key. Retorna el token en texto claro — solo se muestra una vez."""
    raw, key_hash = generar_api_key()
    await db.execute(
        text("""
            INSERT INTO api_keys (nombre, key_hash, creado_por)
            VALUES (:nombre, :key_hash, :creado_por)
        """),
        {"nombre": req.nombre, "key_hash": key_hash, "creado_por": current_user["id"]},
    )
    await db.commit()
    return {
        "api_key": raw,
        "nombre": req.nombre,
        "aviso": "Guarda este token ahora — no se puede recuperar luego.",
    }


@router.get("/", dependencies=[Depends(require_rol("admin"))])
async def listar_api_keys(db: AsyncSession = Depends(get_db)):
    """Lista todas las API Keys (sin exponer el hash)."""
    rows = await db.execute(text("""
        SELECT id, nombre, activo, created_at, ultimo_uso
        FROM api_keys ORDER BY created_at DESC
    """))
    return [dict(r) for r in rows.mappings().all()]


@router.delete("/{key_id}", status_code=204, dependencies=[Depends(require_rol("admin"))])
async def revocar_api_key(key_id: int, db: AsyncSession = Depends(get_db)):
    """Revoca (desactiva) una API Key."""
    result = await db.execute(
        text("UPDATE api_keys SET activo = FALSE WHERE id = :id AND activo = TRUE"),
        {"id": key_id},
    )
    if result.rowcount == 0:
        raise HTTPException(404, "API Key no encontrada o ya revocada")
    await db.commit()
