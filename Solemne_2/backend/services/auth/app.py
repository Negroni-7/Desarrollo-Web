"""Auth Service: credenciales, inicio/cierre de sesión e introspección de tokens.

Autoridad de datos: credenciales (email de acceso, hash de contraseña, rol,
estado) y sesiones (jti). El perfil del cliente pertenece a 'clients'.
"""
import re
import time
import uuid
from datetime import date, datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends
from pydantic import BaseModel, EmailStr, Field, field_validator
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from vu_common.db import get_db
from vu_common.errors import ApiError
from vu_common.internal import CallContext, ServiceClient, require_caller
from vu_common.logs import mask_email
from vu_common.server import create_app, serve
from vu_common.vault import vault

import logging

log = logging.getLogger("vu.auth")

ACCESS_TTL = 30 * 60          # 30 minutos
MAX_FAILED = 5                # intentos antes de bloquear
LOCK_SECONDS = 15 * 60
ISSUER, AUDIENCE = "vu-auth", "vu-gateway"

# Argon2id: hash adaptativo con sal aleatoria por contraseña.
hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
_DUMMY_HASH = hasher.hash("dummy-password-para-tiempo-constante")

app = create_app("Viña Urbana - Auth Service", health_check=lambda: get_db().command("ping"))
clients_api = ServiceClient("clients")


def _db():
    db = get_db()
    return db


@app.on_event("startup")
def _indexes():
    db = _db()
    db.credentials.create_index([("email", ASCENDING)], unique=True)
    db.sessions.create_index("exp", expireAfterSeconds=0)  # limpieza automática de sesiones vencidas
    db.sessions.create_index("userId")


def _keys():
    return vault.read("auth/jwt")


# ---------------------------------------------------------------- modelos
class RegisterIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    telefono: str | None = Field(default=None, max_length=20)
    fechaNacimiento: date
    aceptaTerminos: bool

    @field_validator("password")
    @classmethod
    def password_policy(cls, v: str):
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("debe incluir letras y números")
        return v

    @field_validator("telefono")
    @classmethod
    def phone(cls, v):
        if v and not re.fullmatch(r"\+?[0-9 ]{8,16}", v):
            raise ValueError("formato inválido")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class IntrospectIn(BaseModel):
    token: str = Field(min_length=10, max_length=4096)


def _age(birth: date) -> int:
    today = date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


# ---------------------------------------------------------------- S03 registro
@app.post("/register", status_code=201)
def register(body: RegisterIn, ctx: CallContext = Depends(require_caller("gateway"))):
    if not body.aceptaTerminos:
        raise ApiError(400, "TERMS_REQUIRED", "Debes aceptar los términos")
    if _age(body.fechaNacimiento) < 18:
        # Regla del caso: venta exclusiva a mayores de 18 años (se valida en el servidor).
        raise ApiError(422, "UNDERAGE", "Debes ser mayor de 18 años para registrarte")
    email = body.email.lower()
    user_id = str(uuid.uuid4())
    try:
        _db().credentials.insert_one({
            "_id": user_id,
            "email": email,
            "passwordHash": hasher.hash(body.password),
            "rol": "CLIENTE",
            "estado": "ACTIVO",
            "intentosFallidos": 0,
            "bloqueadoHasta": None,
            "creadoEn": datetime.now(timezone.utc),
        })
    except DuplicateKeyError:
        raise ApiError(409, "EMAIL_IN_USE", "Ya existe una cuenta con ese correo")

    # El perfil lo custodia 'clients'. Si falla, se compensa borrando la credencial.
    resp = None
    try:
        resp = clients_api.request("POST", "/internal/clients", ctx, json={
            "userId": user_id, "nombre": body.nombre, "email": email,
            "telefono": body.telefono, "fechaNacimiento": body.fechaNacimiento.isoformat(),
        })
    finally:
        if resp is None or resp.status_code != 201:
            _db().credentials.delete_one({"_id": user_id})
    if resp.status_code != 201:
        raise ApiError(503, "REGISTRATION_FAILED", "No fue posible completar el registro")
    log.info("user_registered user=%s email=%s", user_id, mask_email(email))
    return {"userId": user_id, "email": email, "nombre": body.nombre}


# ---------------------------------------------------------------- S04 login
@app.post("/login")
def login(body: LoginIn, ctx: CallContext = Depends(require_caller("gateway"))):
    db = _db()
    email = body.email.lower()
    cred = db.credentials.find_one({"email": email, "estado": "ACTIVO"})
    now = datetime.now(timezone.utc)
    if not cred:
        # Se verifica un hash ficticio para no revelar por tiempo si el correo existe.
        try:
            hasher.verify(_DUMMY_HASH, body.password)
        except VerificationError:
            pass
        raise ApiError(401, "INVALID_CREDENTIALS", "Correo o contraseña incorrectos")

    locked = cred.get("bloqueadoHasta")
    if locked and locked.replace(tzinfo=timezone.utc) > now:
        raise ApiError(429, "ACCOUNT_LOCKED", "Demasiados intentos. Intenta más tarde")
    try:
        hasher.verify(cred["passwordHash"], body.password)
    except (VerificationError, InvalidHashError):
        fails = cred.get("intentosFallidos", 0) + 1
        update = {"intentosFallidos": fails}
        if fails >= MAX_FAILED:
            update = {"intentosFallidos": 0, "bloqueadoHasta": now + timedelta(seconds=LOCK_SECONDS)}
        db.credentials.update_one({"_id": cred["_id"]}, {"$set": update})
        raise ApiError(401, "INVALID_CREDENTIALS", "Correo o contraseña incorrectos")

    if hasher.check_needs_rehash(cred["passwordHash"]):
        db.credentials.update_one({"_id": cred["_id"]}, {"$set": {"passwordHash": hasher.hash(body.password)}})
    db.credentials.update_one({"_id": cred["_id"]}, {"$set": {"intentosFallidos": 0, "bloqueadoHasta": None}})

    jti = str(uuid.uuid4())
    exp = now + timedelta(seconds=ACCESS_TTL)
    keys = _keys()
    token = jwt.encode(
        {"sub": cred["_id"], "role": cred["rol"], "jti": jti, "iat": int(now.timestamp()),
         "exp": int(exp.timestamp()), "iss": ISSUER, "aud": AUDIENCE},
        keys["signing_key"], algorithm="HS256", headers={"kid": keys["kid"]},
    )
    db.sessions.insert_one({"_id": jti, "userId": cred["_id"], "exp": exp, "revocada": False, "creadaEn": now})
    return {"accessToken": token, "expiresIn": ACCESS_TTL, "user": {"id": cred["_id"], "email": email, "rol": cred["rol"]}}


def _decode(token: str) -> dict | None:
    keys = _keys()
    candidates = [keys["signing_key"]] + ([keys["previous_key"]] if keys.get("previous_key") else [])
    for key in candidates:
        try:
            return jwt.decode(token, key, algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER,
                              options={"require": ["exp", "sub", "jti", "role"]})
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            continue
    return None


# ---------------------------------------------------------------- introspección (sólo gateway)
@app.post("/internal/introspect")
def introspect(body: IntrospectIn, ctx: CallContext = Depends(require_caller("gateway"))):
    claims = _decode(body.token)
    if not claims:
        return {"active": False}
    db = _db()
    session = db.sessions.find_one({"_id": claims["jti"]})
    if not session or session.get("revocada"):
        return {"active": False}
    cred = db.credentials.find_one({"_id": claims["sub"]}, {"estado": 1, "rol": 1, "email": 1})
    if not cred or cred["estado"] != "ACTIVO":
        return {"active": False}
    # El rol vigente se toma de la base, no del token (si cambia, aplica de inmediato).
    return {"active": True, "sub": claims["sub"], "role": cred["rol"], "jti": claims["jti"],
            "exp": claims["exp"], "email": cred["email"]}


# ---------------------------------------------------------------- S05 / S06
@app.post("/internal/sessions/{jti}/revoke")
def revoke(jti: str, ctx: CallContext = Depends(require_caller("gateway"))):
    user = ctx.require_user()
    _db().sessions.update_one({"_id": jti, "userId": user}, {"$set": {"revocada": True}})
    return {"revocada": True}


@app.get("/session")
def session(ctx: CallContext = Depends(require_caller("gateway"))):
    user = ctx.require_user()
    cred = _db().credentials.find_one({"_id": user}, {"email": 1, "rol": 1})
    if not cred:
        raise ApiError(401, "UNAUTHENTICATED", "Sesión inválida")
    return {"userId": user, "email": cred["email"], "rol": cred["rol"]}


# ---------------------------------------------------------------- baja de cuenta (sólo clients)
@app.post("/internal/users/{user_id}/deactivate")
def deactivate(user_id: str, ctx: CallContext = Depends(require_caller("clients"))):
    db = _db()
    res = db.credentials.update_one(
        {"_id": user_id, "estado": "ACTIVO"},
        # Se elimina el correo y el hash: la cuenta ya no puede autenticarse ni identificar a la persona.
        {"$set": {"estado": "ELIMINADO", "email": f"eliminado-{user_id}@invalid", "passwordHash": "",
                  "eliminadoEn": datetime.now(timezone.utc)}},
    )
    db.sessions.update_many({"userId": user_id}, {"$set": {"revocada": True}})
    return {"desactivado": res.modified_count == 1}


if __name__ == "__main__":
    serve(app)
