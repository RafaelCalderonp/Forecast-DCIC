"""
Autenticacion JWT para Forecast DCIC
Roles: admin (1), editor (2), viewer (3)
M2M: API Keys para integración ERP (header X-API-Key)
"""

import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from database import get_db

SECRET_KEY  = os.getenv("JWT_SECRET", "dcic-forecast-secret-2026-change-in-prod")
ALGORITHM   = "HS256"
TOKEN_HORAS = 12

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
ROL_NOMBRES  = {1: "admin", 2: "editor", 3: "viewer"}


def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verificar_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def crear_token(data: dict, horas: int = TOKEN_HORAS) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(hours=horas)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[int] = payload.get("sub")
        if user_id is None:
            raise exc
    except JWTError:
        raise exc

    row = await db.execute(
        text("SELECT id, email, nombre, rol_id, activo FROM usuarios WHERE id=:id"),
        {"id": int(user_id)},
    )
    user = row.mappings().first()
    if not user or not user["activo"]:
        raise exc

    await db.execute(
        text("UPDATE usuarios SET ultimo_acceso=NOW() WHERE id=:id"),
        {"id": int(user_id)},
    )
    await db.commit()
    return dict(user)


def require_rol(*roles: str):
    rol_ids = {"admin": 1, "editor": 2, "viewer": 3}
    allowed_ids = {rol_ids[r] for r in roles}

    async def _dep(current_user=Depends(get_current_user)):
        if current_user["rol_id"] not in allowed_ids:
            raise HTTPException(status_code=403, detail="No tienes permiso para esta acción")
        return current_user

    return _dep


def is_admin(user: dict) -> bool:
    return user["rol_id"] == 1


# ── Autenticación M2M (API Key) ──────────────────────────────────────────────

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generar_api_key() -> tuple[str, str]:
    """Retorna (token_raw, token_hash). Guardar solo el hash en DB."""
    raw = secrets.token_urlsafe(32)
    return raw, _hash_key(raw)


async def require_api_key(
    api_key: Optional[str] = Security(_api_key_header),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Dependency para endpoints M2M. Valida X-API-Key contra la tabla api_keys."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere X-API-Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    key_hash = _hash_key(api_key)
    row = await db.execute(
        text("SELECT id, nombre FROM api_keys WHERE key_hash = :h AND activo = TRUE"),
        {"h": key_hash},
    )
    record = row.mappings().first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API Key inválida o desactivada",
        )
    # Actualizar último uso (fire-and-forget, sin bloquear la respuesta)
    await db.execute(
        text("UPDATE api_keys SET ultimo_uso = NOW() WHERE id = :id"),
        {"id": record["id"]},
    )
    await db.commit()
    return {"api_key_id": record["id"], "nombre": record["nombre"]}
