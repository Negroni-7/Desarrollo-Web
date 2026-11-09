"""Clients: perfil del cliente y mensajes de contacto.

Autoridad de datos: perfil (nombre, teléfono, fecha de nacimiento, dirección
predeterminada) y mensajes del formulario de contacto. Todos son datos
personales: se devuelven sólo al propio titular o al administrador.
"""
import logging
import re
import uuid
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import Depends, Query
from pydantic import BaseModel, EmailStr, Field, field_validator
from pymongo import DESCENDING

from vu_common.db import get_db
from vu_common.errors import ApiError
from vu_common.internal import CallContext, ServiceClient, require_caller
from vu_common.server import create_app, serve

log = logging.getLogger("vu.clients")
app = create_app("Viña Urbana - Clients", health_check=lambda: get_db().command("ping"))
auth_api = ServiceClient("auth")
orders_api = ServiceClient("orders")
tastings_api = ServiceClient("tastings")

PHONE = r"\+?[0-9 ]{8,16}"
RETENCION_MENSAJES_DIAS = 365


@app.on_event("startup")
def _indexes():
    db = get_db()
    # Retención: los mensajes de contacto se eliminan automáticamente al año.
    db.contact_messages.create_index("recibidoEn", expireAfterSeconds=RETENCION_MENSAJES_DIAS * 86400)
    db.contact_messages.create_index([("estado", 1), ("recibidoEn", DESCENDING)])


class Direccion(BaseModel):
    calle: str = Field(min_length=2, max_length=80)
    numero: str = Field(min_length=1, max_length=10)
    depto: str | None = Field(default=None, max_length=10)
    comuna: str = Field(min_length=2, max_length=40)
    region: str = Field(min_length=2, max_length=40)


class ProfileCreate(BaseModel):
    userId: str
    nombre: str = Field(min_length=2, max_length=80)
    email: EmailStr
    telefono: str | None = None
    fechaNacimiento: date


class ProfilePut(BaseModel):
    """PUT reemplaza la representación editable completa del perfil."""
    nombre: str = Field(min_length=2, max_length=80)
    telefono: str | None = Field(default=None, max_length=20)
    direccion: Direccion | None = None

    @field_validator("telefono")
    @classmethod
    def phone(cls, v):
        if v and not re.fullmatch(PHONE, v):
            raise ValueError("formato inválido")
        return v


class ContactIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    email: EmailStr
    asunto: Literal["Consulta sobre vinos", "Pedido especial", "Degustación privada", "Otro"]
    mensaje: str = Field(min_length=5, max_length=2000)


class ContactStatus(BaseModel):
    estado: Literal["ATENDIDO", "PENDIENTE"]


def _profile_dto(doc: dict) -> dict:
    # DTO: no expone el _id interno de Mongo ni campos de auditoría.
    return {
        "nombre": doc["nombre"], "email": doc["email"], "telefono": doc.get("telefono"),
        "fechaNacimiento": doc["fechaNacimiento"], "direccion": doc.get("direccion"),
    }


# ---------------------------------------------------------------- creación (sólo auth)
@app.post("/internal/clients", status_code=201)
def create_profile(body: ProfileCreate, ctx: CallContext = Depends(require_caller("auth"))):
    get_db().profiles.insert_one({
        "_id": body.userId, "nombre": body.nombre, "email": body.email.lower(), "telefono": body.telefono,
        "fechaNacimiento": body.fechaNacimiento.isoformat(), "direccion": None,
        "estado": "ACTIVO", "creadoEn": datetime.now(timezone.utc),
    })
    return {"userId": body.userId}


# ---------------------------------------------------------------- S07 / S08 / S09
@app.get("/clients/me")
def get_me(ctx: CallContext = Depends(require_caller("gateway"))):
    user = ctx.require_user()
    doc = get_db().profiles.find_one({"_id": user, "estado": "ACTIVO"})
    if not doc:
        raise ApiError(404, "PROFILE_NOT_FOUND", "Perfil no encontrado")
    return _profile_dto(doc)


@app.put("/clients/me")
def put_me(body: ProfilePut, ctx: CallContext = Depends(require_caller("gateway"))):
    user = ctx.require_user()
    res = get_db().profiles.find_one_and_update(
        {"_id": user, "estado": "ACTIVO"},
        {"$set": {"nombre": body.nombre, "telefono": body.telefono,
                  "direccion": body.direccion.model_dump() if body.direccion else None,
                  "actualizadoEn": datetime.now(timezone.utc)}},
        return_document=True,
    )
    if not res:
        raise ApiError(404, "PROFILE_NOT_FOUND", "Perfil no encontrado")
    return _profile_dto(res)


@app.delete("/clients/me")
def delete_me(ctx: CallContext = Depends(require_caller("gateway"))):
    """Baja de cuenta: se anonimiza el perfil y se desactiva la credencial.
    Los pedidos se conservan (respaldo tributario de las boletas) sin datos de contacto del perfil."""
    user = ctx.require_user()
    active = orders_api.request("GET", f"/internal/orders/active-count?userId={user}", ctx)
    reservations = tastings_api.request("GET", f"/internal/reservations/active-count?userId={user}", ctx)
    if active.status_code != 200 or reservations.status_code != 200:
        raise ApiError(503, "DEPENDENCY_UNAVAILABLE", "No fue posible verificar pedidos y reservas")
    if active.json()["cantidad"] > 0 or reservations.json()["cantidad"] > 0:
        raise ApiError(409, "ACTIVE_OPERATIONS", "Tienes pedidos o reservas en curso; espera a que finalicen")
    db = get_db()
    res = db.profiles.update_one(
        {"_id": user, "estado": "ACTIVO"},
        {"$set": {"estado": "ELIMINADO", "nombre": "Cliente eliminado", "email": None, "telefono": None,
                  "fechaNacimiento": None, "direccion": None, "eliminadoEn": datetime.now(timezone.utc)}},
    )
    if res.modified_count != 1:
        raise ApiError(404, "PROFILE_NOT_FOUND", "Perfil no encontrado")
    deact = auth_api.request("POST", f"/internal/users/{user}/deactivate", ctx)
    if deact.status_code != 200:
        log.error("deactivate_pending user=%s", user)
    return {"eliminado": True}


# ---------------------------------------------------------------- S22 contacto (anónimo)
@app.post("/contact", status_code=201)
def contact(body: ContactIn, ctx: CallContext = Depends(require_caller("gateway"))):
    msg_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    get_db().contact_messages.insert_one({
        "_id": msg_id, "nombre": body.nombre, "email": body.email.lower(), "asunto": body.asunto,
        "mensaje": body.mensaje, "estado": "PENDIENTE", "recibidoEn": now, "userId": ctx.user_id,
    })
    return {"id": msg_id, "recibidoEn": now.isoformat(), "estado": "PENDIENTE"}


# ---------------------------------------------------------------- S32 / S33 administración
@app.get("/admin/contact")
def list_contact(estado: Literal["PENDIENTE", "ATENDIDO"] | None = None,
                 pagina: int = Query(1, ge=1), tamano: int = Query(20, ge=1, le=50),
                 ctx: CallContext = Depends(require_caller("gateway"))):
    ctx.require_role("ADMIN")
    filt = {"estado": estado} if estado else {}
    db = get_db()
    total = db.contact_messages.count_documents(filt)
    items = [
        {"id": d["_id"], "nombre": d["nombre"], "email": d["email"], "asunto": d["asunto"],
         "mensaje": d["mensaje"], "estado": d["estado"], "recibidoEn": d["recibidoEn"].isoformat()}
        for d in db.contact_messages.find(filt).sort("recibidoEn", DESCENDING).skip((pagina - 1) * tamano).limit(tamano)
    ]
    return {"items": items, "total": total, "pagina": pagina, "tamano": tamano}


@app.patch("/admin/contact/{msg_id}")
def patch_contact(msg_id: str, body: ContactStatus, ctx: CallContext = Depends(require_caller("gateway"))):
    ctx.require_role("ADMIN")
    res = get_db().contact_messages.update_one({"_id": msg_id}, {"$set": {"estado": body.estado, "atendidoPor": ctx.user_id}})
    if res.matched_count != 1:
        raise ApiError(404, "NOT_FOUND", "Mensaje no encontrado")
    return {"id": msg_id, "estado": body.estado}


if __name__ == "__main__":
    serve(app)
