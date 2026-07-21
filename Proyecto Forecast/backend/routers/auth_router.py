from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

from database import get_db
from auth import verificar_password, crear_token, get_current_user, hash_password, ROL_NOMBRES, generar_api_key

router = APIRouter()

ROL_IDS = {"admin": 1, "editor": 2, "viewer": 3}


@router.post("/login")
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    row = await db.execute(
        text("SELECT id, email, nombre, password_hash, rol_id, activo FROM usuarios WHERE email=:e"),
        {"e": form.username},
    )
    user = row.mappings().first()

    if not user or not user["activo"] or not verificar_password(form.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")

    token = crear_token({"sub": str(user["id"]), "rol": ROL_NOMBRES[user["rol_id"]]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id":     user["id"],
            "email":  user["email"],
            "nombre": user["nombre"],
            "rol":    ROL_NOMBRES[user["rol_id"]],
        },
    }


@router.get("/me")
async def me(current_user=Depends(get_current_user)):
    return {**current_user, "rol": ROL_NOMBRES.get(current_user["rol_id"], "viewer")}


class ChangePasswordIn(BaseModel):
    password_actual: str
    password_nuevo:  str


@router.post("/change-password")
async def change_password(
    body: ChangePasswordIn,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await db.execute(
        text("SELECT password_hash FROM usuarios WHERE id=:id"),
        {"id": current_user["id"]},
    )
    stored = row.scalar_one_or_none()
    if not stored or not verificar_password(body.password_actual, stored):
        raise HTTPException(status_code=400, detail="Password actual incorrecto")

    new_hash = hash_password(body.password_nuevo)
    await db.execute(
        text("UPDATE usuarios SET password_hash=:h, updated_at=NOW() WHERE id=:id"),
        {"h": new_hash, "id": current_user["id"]},
    )
    await db.commit()
    return {"ok": True}


class CreateUserIn(BaseModel):
    email:    str
    nombre:   str
    password: str
    rol:      str


@router.post("/users")
async def crear_usuario(
    body: CreateUserIn,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user["rol_id"] != 1:
        raise HTTPException(status_code=403, detail="Solo admin puede crear usuarios")
    rol_id = ROL_IDS.get(body.rol)
    if not rol_id:
        raise HTTPException(status_code=400, detail="Rol inválido: admin|editor|viewer")

    try:
        row = await db.execute(
            text("INSERT INTO usuarios (email, nombre, password_hash, rol_id) VALUES (:e,:n,:h,:r) RETURNING id"),
            {"e": body.email, "n": body.nombre, "h": hash_password(body.password), "r": rol_id},
        )
        await db.commit()
        return {"id": row.scalar_one(), "email": body.email, "rol": body.rol}
    except Exception:
        raise HTTPException(status_code=400, detail="Email ya registrado")


@router.get("/users")
async def listar_usuarios(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user["rol_id"] != 1:
        raise HTTPException(status_code=403, detail="Solo admin")
    rows = await db.execute(
        text("SELECT id, email, nombre, rol_id, activo, ultimo_acceso FROM usuarios ORDER BY id")
    )
    return [
        {**dict(r), "rol": ROL_NOMBRES.get(r["rol_id"], "viewer")}
        for r in rows.mappings().all()
    ]


# ── Gestión de API Keys M2M ──────────────────────────────────────────────────

class CreateApiKeyIn(BaseModel):
    nombre: str


@router.post("/api-keys")
async def crear_api_key(
    body: CreateApiKeyIn,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Solo admin. Retorna el token UNA SOLA VEZ — no se puede recuperar después."""
    if current_user["rol_id"] != 1:
        raise HTTPException(status_code=403, detail="Solo admin puede crear API Keys")

    raw, key_hash = generar_api_key()
    await db.execute(
        text("""
            INSERT INTO api_keys (nombre, key_hash, creado_por)
            VALUES (:nombre, :hash, :creado_por)
        """),
        {"nombre": body.nombre, "hash": key_hash, "creado_por": current_user["id"]},
    )
    await db.commit()
    return {
        "nombre": body.nombre,
        "api_key": raw,
        "aviso": "Guarda este token ahora. No se puede recuperar después.",
    }


@router.get("/api-keys")
async def listar_api_keys(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Solo admin. Muestra nombre, estado y último uso (nunca el token)."""
    if current_user["rol_id"] != 1:
        raise HTTPException(status_code=403, detail="Solo admin")
    rows = await db.execute(
        text("SELECT id, nombre, activo, created_at, ultimo_uso FROM api_keys ORDER BY id")
    )
    return [dict(r) for r in rows.mappings().all()]


@router.delete("/api-keys/{key_id}", status_code=204)
async def revocar_api_key(
    key_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Desactiva una API Key (no la elimina, para mantener auditoría)."""
    if current_user["rol_id"] != 1:
        raise HTTPException(status_code=403, detail="Solo admin")
    result = await db.execute(
        text("UPDATE api_keys SET activo = FALSE WHERE id = :id"),
        {"id": key_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="API Key no encontrada")
    await db.commit()
