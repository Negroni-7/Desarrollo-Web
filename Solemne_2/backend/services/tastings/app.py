"""Tastings: paquetes de degustación, cupos por sesión y reservas.

Sistema complementario exigido por el caso (pantalla "Degustaciones y
Maridaje"). Se separa de orders porque su ciclo de vida es distinto: no hay
despacho ni stock de botellas, sino cupos por fecha y hora en la sala de cata,
y el pago se realiza en el local el día de la degustación.

Autoridad de datos: paquetes, sesiones (cupos ocupados) y reservas.
Los comentarios pueden contener alergias o restricciones alimentarias (dato
sensible de salud): sólo los ven el titular, el sommelier y el administrador,
y se eliminan 30 días después de la fecha de la degustación.
"""
import logging
import os
import re
import threading
import time
import uuid
from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import Depends, Query
from pydantic import BaseModel, EmailStr, Field, field_validator
from pymongo import ASCENDING, ReturnDocument

from vu_common.db import get_db
from vu_common.errors import ApiError
from vu_common.internal import CallContext, require_caller
from vu_common.outbox import new_event, start_dispatcher
from vu_common.server import create_app, serve

log = logging.getLogger("vu.tastings")
app = create_app("Viña Urbana - Tastings", health_check=lambda: get_db().command("ping"))

TZ = ZoneInfo("America/Santiago")
HORAS = ["10:00", "12:00", "16:00", "18:00", "20:00"]
CAPACIDAD_SALA = int(os.getenv("TASTING_ROOM_CAPACITY", "12"))
MAX_DIAS_ANTICIPACION = 90
CANCELACION_HORAS = 24
RETENCION_COMENTARIOS_DIAS = 30


@app.on_event("startup")
def _startup():
    db = get_db()
    db.reservations.create_index([("clienteId", 1), ("fecha", 1)])
    db.reservations.create_index([("fecha", 1), ("hora", 1)])
    start_dispatcher(get_db)
    threading.Thread(target=_purge_comments, daemon=True).start()


def _today() -> date:
    return datetime.now(TZ).date()


def _check_date(fecha: date):
    if fecha <= _today():
        raise ApiError(422, "INVALID_DATE", "La fecha debe ser posterior a hoy")
    if fecha > _today() + timedelta(days=MAX_DIAS_ANTICIPACION):
        raise ApiError(422, "INVALID_DATE", f"Se puede reservar con hasta {MAX_DIAS_ANTICIPACION} días de anticipación")
    if fecha.weekday() == 6:
        raise ApiError(422, "CLOSED_DAY", "Atendemos de lunes a sábado")


def package_dto(p: dict) -> dict:
    return {"id": p["_id"], "nombre": p["nombre"], "descripcion": p["descripcion"], "incluye": p["incluye"],
            "duracionMin": p["duracionMin"], "precioPorPersona": p["precioPorPersona"], "imagen": p["imagen"]}


def reservation_dto(r: dict, staff: bool = False) -> dict:
    dto = {"id": r["_id"], "paqueteId": r["paqueteId"], "paquete": r["paqueteNombre"], "fecha": r["fecha"],
           "hora": r["hora"], "personas": r["personas"], "total": r["total"], "estado": r["estado"],
           "comentarios": r.get("comentarios"), "creadaEn": r["creadaEn"].isoformat()}
    if staff:
        dto["contacto"] = r["contacto"]
    return dto


# ---------------------------------------------------------------- S17 / S18 (anónimos)
@app.get("/tastings/packages")
def packages(ctx: CallContext = Depends(require_caller("gateway"))):
    return {"items": [package_dto(p) for p in get_db().packages.find({"activo": True}).sort("precioPorPersona", ASCENDING)]}


@app.get("/tastings/availability")
def availability(fecha: date, ctx: CallContext = Depends(require_caller("gateway"))):
    _check_date(fecha)
    slots = {s["hora"]: s["ocupados"] for s in get_db().sessions.find({"fecha": fecha.isoformat()})}
    return {"fecha": fecha.isoformat(), "capacidad": CAPACIDAD_SALA,
            "horarios": [{"hora": h, "cuposDisponibles": CAPACIDAD_SALA - slots.get(h, 0)} for h in HORAS]}


# ---------------------------------------------------------------- S19 reservar
class Contacto(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    email: EmailStr
    telefono: str = Field(pattern=r"^\+?[0-9 ]{8,16}$")


class ReservationIn(BaseModel):
    model_config = {"extra": "forbid"}
    paqueteId: str = Field(pattern=r"^[a-z0-9\-]{3,40}$")
    fecha: date
    hora: str
    personas: int = Field(ge=1, le=CAPACIDAD_SALA)
    contacto: Contacto
    comentarios: str | None = Field(default=None, max_length=500)

    @field_validator("hora")
    @classmethod
    def hora_ok(cls, v):
        if v not in HORAS:
            raise ValueError("horario no disponible")
        return v


@app.post("/tastings/reservations", status_code=201)
def reserve(body: ReservationIn, ctx: CallContext = Depends(require_caller("gateway"))):
    ctx.require_role("CLIENTE")
    _check_date(body.fecha)
    db = get_db()
    pkg = db.packages.find_one({"_id": body.paqueteId, "activo": True})
    if not pkg:
        raise ApiError(404, "PACKAGE_NOT_FOUND", "Paquete no encontrado")
    fecha = body.fecha.isoformat()
    slot_id = f"{fecha}#{body.hora}"
    db.sessions.update_one({"_id": slot_id}, {"$setOnInsert": {"fecha": fecha, "hora": body.hora, "ocupados": 0}}, upsert=True)
    # Actualización condicional atómica: dos reservas simultáneas no pueden superar la capacidad.
    slot = db.sessions.find_one_and_update(
        {"_id": slot_id, "ocupados": {"$lte": CAPACIDAD_SALA - body.personas}},
        {"$inc": {"ocupados": body.personas}}, return_document=ReturnDocument.AFTER)
    if not slot:
        raise ApiError(409, "NO_CAPACITY", "No quedan cupos suficientes en ese horario")
    now = datetime.now(timezone.utc)
    doc = {"_id": str(uuid.uuid4()), "clienteId": ctx.user_id, "paqueteId": pkg["_id"], "paqueteNombre": pkg["nombre"],
           "fecha": fecha, "hora": body.hora, "personas": body.personas,
           "total": pkg["precioPorPersona"] * body.personas,  # precio oficial del servidor
           "contacto": body.contacto.model_dump(), "comentarios": body.comentarios,
           "estado": "CONFIRMADA", "creadaEn": now}
    db.reservations.insert_one(doc)
    db.outbox.insert_one(new_event("booking.created", {"reservaId": doc["_id"], "paqueteId": pkg["_id"],
                                                        "paquete": pkg["nombre"], "personas": body.personas,
                                                        "fecha": fecha, "total": doc["total"]}))
    return reservation_dto(doc)


# ---------------------------------------------------------------- S20 / S21
@app.get("/tastings/reservations/me")
def mine(ctx: CallContext = Depends(require_caller("gateway"))):
    ctx.require_role("CLIENTE")
    docs = get_db().reservations.find({"clienteId": ctx.user_id}).sort([("fecha", -1), ("hora", -1)]).limit(50)
    return {"items": [reservation_dto(r) for r in docs]}


def _release(db, r: dict):
    db.sessions.update_one({"_id": f"{r['fecha']}#{r['hora']}"}, {"$inc": {"ocupados": -r["personas"]}})


@app.post("/tastings/reservations/{rid}/cancel")
def cancel(rid: str, ctx: CallContext = Depends(require_caller("gateway"))):
    ctx.require_role("CLIENTE")
    db = get_db()
    r = db.reservations.find_one({"_id": rid, "clienteId": ctx.user_id})
    if not r:
        raise ApiError(404, "RESERVATION_NOT_FOUND", "Reserva no encontrada")
    start = datetime.combine(date.fromisoformat(r["fecha"]), dtime.fromisoformat(r["hora"]), tzinfo=TZ)
    if start - datetime.now(TZ) < timedelta(hours=CANCELACION_HORAS):
        raise ApiError(409, "TOO_LATE", f"Sólo se puede cancelar con {CANCELACION_HORAS} horas de anticipación")
    upd = db.reservations.find_one_and_update({"_id": rid, "estado": "CONFIRMADA"},
                                              {"$set": {"estado": "CANCELADA", "canceladaEn": datetime.now(timezone.utc)}},
                                              return_document=ReturnDocument.AFTER)
    if not upd:
        raise ApiError(409, "INVALID_TRANSITION", f"La reserva está {r['estado']}")
    _release(db, upd)
    return reservation_dto(upd)


@app.get("/internal/reservations/active-count")
def active_count(userId: str, ctx: CallContext = Depends(require_caller("clients"))):
    return {"cantidad": get_db().reservations.count_documents(
        {"clienteId": userId, "estado": "CONFIRMADA", "fecha": {"$gte": _today().isoformat()}})}


# ---------------------------------------------------------------- S30 / S31 personal
class StaffStatus(BaseModel):
    estado: Literal["ASISTIDA", "NO_ASISTIO", "CANCELADA"]


@app.get("/admin/tastings/reservations")
def staff_list(fecha: date | None = None, ctx: CallContext = Depends(require_caller("gateway"))):
    ctx.require_role("ADMIN", "SOMMELIER")
    filt = {"fecha": fecha.isoformat()} if fecha else {"fecha": {"$gte": _today().isoformat()}}
    docs = get_db().reservations.find(filt).sort([("fecha", 1), ("hora", 1)]).limit(200)
    return {"items": [reservation_dto(r, staff=True) for r in docs]}


@app.patch("/admin/tastings/reservations/{rid}/status")
def staff_status(rid: str, body: StaffStatus, ctx: CallContext = Depends(require_caller("gateway"))):
    ctx.require_role("ADMIN", "SOMMELIER")
    db = get_db()
    upd = db.reservations.find_one_and_update({"_id": rid, "estado": "CONFIRMADA"},
                                              {"$set": {"estado": body.estado, "gestionadaPor": ctx.user_id}},
                                              return_document=ReturnDocument.AFTER)
    if not upd:
        if not db.reservations.find_one({"_id": rid}):
            raise ApiError(404, "RESERVATION_NOT_FOUND", "Reserva no encontrada")
        raise ApiError(409, "INVALID_TRANSITION", "La reserva ya fue gestionada")
    if body.estado == "CANCELADA":
        _release(db, upd)
    return reservation_dto(upd, staff=True)


def _purge_comments():
    """Minimización: borra comentarios (posibles datos de salud) 30 días después de la degustación."""
    while True:
        try:
            limite = (_today() - timedelta(days=RETENCION_COMENTARIOS_DIAS)).isoformat()
            get_db().reservations.update_many({"fecha": {"$lt": limite}, "comentarios": {"$ne": None}},
                                              {"$set": {"comentarios": None}})
        except Exception as exc:
            log.warning("purge_error err=%s", type(exc).__name__)
        time.sleep(3600)


if __name__ == "__main__":
    serve(app)
