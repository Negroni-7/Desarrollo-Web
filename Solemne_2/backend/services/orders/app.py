"""Orders: cotización, creación y ciclo de vida de pedidos (incluye despacho).

Autoridad de datos: pedidos, sus ítems (copia del nombre y precio al momento
de la compra), dirección de entrega y estado oficial del pedido.
El precio oficial lo entrega inventory; el resultado del pago lo informa
payments. El navegador nunca decide precios, totales ni el estado "PAGADO".

Ciclo de vida:
  PENDIENTE_PAGO -> PAGADO -> EN_PREPARACION -> DESPACHADO -> ENTREGADO
  PENDIENTE_PAGO -> CANCELADO   (cliente, o vencimiento del plazo de pago)
"""
import logging
import os
import re
import threading
import time
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import Depends, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from pymongo import DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError

import inventory_client as inventory
from vu_common.db import get_db
from vu_common.errors import ApiError, DependencyError
from vu_common.internal import CallContext, require_caller
from vu_common.outbox import new_event, start_dispatcher
from vu_common.server import create_app, serve

log = logging.getLogger("vu.orders")
app = create_app("Viña Urbana - Orders", health_check=lambda: get_db().command("ping"))

PAYMENT_WINDOW = int(os.getenv("PAYMENT_WINDOW_SECONDS", "900"))  # 15 min para pagar
SWEEP_INTERVAL = float(os.getenv("SWEEP_INTERVAL_SECONDS", "10"))
ENVIO_GRATIS_DESDE = 50_000
COSTO_RM, COSTO_REGIONES = 3_990, 6_990
REGIONES = ["Arica y Parinacota", "Tarapacá", "Antofagasta", "Atacama", "Coquimbo", "Valparaíso", "Metropolitana",
            "O'Higgins", "Maule", "Ñuble", "Biobío", "La Araucanía", "Los Ríos", "Los Lagos", "Aysén", "Magallanes"]
ACTIVOS = ["PENDIENTE_PAGO", "PAGADO", "EN_PREPARACION", "DESPACHADO"]
TRANSICIONES_ADMIN = {"PAGADO": "EN_PREPARACION", "EN_PREPARACION": "DESPACHADO", "DESPACHADO": "ENTREGADO"}


@app.on_event("startup")
def _startup():
    db = get_db()
    db.orders.create_index([("clienteId", 1), ("idempotencyKey", 1)], unique=True)
    db.orders.create_index([("clienteId", 1), ("creadoEn", DESCENDING)])
    db.orders.create_index([("estado", 1), ("venceEn", 1)])
    start_dispatcher(get_db)
    threading.Thread(target=_sweeper, daemon=True, name="sweeper").start()


# ---------------------------------------------------------------- modelos
class ItemIn(BaseModel):
    productoId: str = Field(pattern=r"^[a-z0-9\-]{3,40}$")
    cantidad: int = Field(ge=1, le=24)


class Destino(BaseModel):
    comuna: str = Field(min_length=2, max_length=40)
    region: str

    @field_validator("region")
    @classmethod
    def region_ok(cls, v):
        if v not in REGIONES:
            raise ValueError("región inválida")
        return v


class QuoteIn(BaseModel):
    items: list[ItemIn] = Field(min_length=1, max_length=50)
    destino: Destino | None = None


class Entrega(Destino):
    nombreReceptor: str = Field(min_length=2, max_length=80)
    calle: str = Field(min_length=2, max_length=80)
    numero: str = Field(min_length=1, max_length=10)
    depto: str | None = Field(default=None, max_length=10)
    telefono: str = Field(pattern=r"^\+?[0-9 ]{8,16}$")
    indicaciones: str | None = Field(default=None, max_length=200)


class OrderIn(BaseModel):
    # Nota: no existe campo de precio ni total. Si el navegador los envía, se rechazan (extra=forbid).
    model_config = {"extra": "forbid"}
    items: list[ItemIn] = Field(min_length=1, max_length=50)
    entrega: Entrega


class PaymentResultIn(BaseModel):
    pagoId: str
    resultado: Literal["APROBADO", "RECHAZADO"]
    monto: int


class StatusIn(BaseModel):
    estado: Literal["EN_PREPARACION", "DESPACHADO", "ENTREGADO"]


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().strip().lower()


def costo_despacho(subtotal: int, destino: Destino | None) -> int | None:
    """Regla del caso: despacho gratis sobre $50.000 en Providencia; tarifa RM o regiones en otro caso."""
    if destino is None:
        return None
    if _norm(destino.comuna) == "providencia" and subtotal >= ENVIO_GRATIS_DESDE:
        return 0
    return COSTO_RM if destino.region == "Metropolitana" else COSTO_REGIONES


def _quote(items: list[ItemIn]) -> tuple[list[dict], list[str]]:
    quoted = inventory.quote([i.model_dump() for i in items])
    lines, unavailable = [], []
    for q in quoted:
        if not q.active or not q.available:
            unavailable.append(q.product_id)
        if q.active:
            lines.append({"productoId": q.product_id, "nombre": q.name, "tipo": q.type, "imagen": q.image,
                          "precioUnitario": q.unit_price, "cantidad": q.quantity,
                          "subtotal": q.unit_price * q.quantity, "disponible": q.available})
    return lines, unavailable


def order_dto(o: dict, admin: bool = False) -> dict:
    dto = {
        "id": o["_id"], "numero": o["numero"], "estado": o["estado"],
        "items": [{k: i[k] for k in ("productoId", "nombre", "tipo", "imagen", "precioUnitario", "cantidad", "subtotal")}
                  for i in o["items"]],
        "subtotal": o["subtotal"], "despacho": o["despacho"], "total": o["total"],
        "entrega": o["entrega"], "creadoEn": o["creadoEn"].isoformat(),
        "venceEn": o["venceEn"].isoformat() if o["estado"] == "PENDIENTE_PAGO" else None,
        "historial": [{"estado": h["estado"], "fecha": h["fecha"].isoformat()} for h in o["historial"]],
    }
    if admin:
        dto["clienteId"] = o["clienteId"]
    return dto


def _next_number(db) -> int:
    doc = db.counters.find_one_and_update({"_id": "orders"}, {"$inc": {"seq": 1}}, upsert=True,
                                          return_document=ReturnDocument.AFTER)
    return doc["seq"]


# ---------------------------------------------------------------- S02 cotizar carrito (anónimo)
@app.post("/orders/quote")
def quote(body: QuoteIn, ctx: CallContext = Depends(require_caller("gateway"))):
    lines, unavailable = _quote(body.items)
    subtotal = sum(l["subtotal"] for l in lines if l["disponible"])
    despacho = costo_despacho(subtotal, body.destino)
    return {"items": lines, "noDisponibles": unavailable, "subtotal": subtotal, "despacho": despacho,
            "total": subtotal + (despacho or 0), "envioGratisDesde": ENVIO_GRATIS_DESDE}


# ---------------------------------------------------------------- S10 crear pedido
@app.post("/orders", status_code=201)
def create_order(body: OrderIn, ctx: CallContext = Depends(require_caller("gateway")),
                 idempotency_key: str = Header(default="", alias="Idempotency-Key")):
    ctx.require_role("CLIENTE")
    if not re.fullmatch(r"[0-9a-fA-F\-]{16,64}", idempotency_key):
        raise ApiError(400, "IDEMPOTENCY_KEY_REQUIRED", "Falta la cabecera Idempotency-Key")
    db = get_db()
    previous = db.orders.find_one({"clienteId": ctx.user_id, "idempotencyKey": idempotency_key})
    if previous:  # reintento del mismo checkout: no se crea un segundo pedido
        return JSONResponse(status_code=200, content=order_dto(previous))

    lines, unavailable = _quote(body.items)
    if unavailable:
        raise ApiError(409, "PRODUCTS_UNAVAILABLE", "Uno o más productos no están disponibles",
                       [{"productoId": p} for p in unavailable])
    order_id = str(uuid.uuid4())
    try:
        inventory.reserve(order_id, [{"productoId": l["productoId"], "cantidad": l["cantidad"]} for l in lines])
    except DependencyError:
        # La reserva pudo aplicarse aunque la respuesta no llegó: se libera de forma idempotente.
        try:
            inventory.release(order_id, "timeout-creacion")
        except ApiError:
            pass
        raise

    subtotal = sum(l["subtotal"] for l in lines)
    despacho = costo_despacho(subtotal, body.entrega)
    now = datetime.now(timezone.utc)
    order = {
        "_id": order_id, "numero": _next_number(db), "clienteId": ctx.user_id, "estado": "PENDIENTE_PAGO",
        "items": [{k: v for k, v in l.items() if k != "disponible"} for l in lines],
        "subtotal": subtotal, "despacho": despacho, "total": subtotal + despacho,
        "entrega": body.entrega.model_dump(), "idempotencyKey": idempotency_key,
        "historial": [{"estado": "PENDIENTE_PAGO", "fecha": now, "actor": "cliente"}],
        "creadoEn": now, "actualizadoEn": now, "venceEn": now + timedelta(seconds=PAYMENT_WINDOW),
    }
    try:
        db.orders.insert_one(order)
    except DuplicateKeyError:
        inventory.release(order_id, "duplicado")
        return JSONResponse(status_code=200, content=order_dto(db.orders.find_one(
            {"clienteId": ctx.user_id, "idempotencyKey": idempotency_key})))
    log.info("order_created order=%s total=%s", order_id, order["total"])
    return order_dto(order)


def _cancel(db, order_id: str, filt: dict, actor: str, motivo: str) -> dict | None:
    now = datetime.now(timezone.utc)
    doc = db.orders.find_one_and_update(
        {"_id": order_id, "estado": "PENDIENTE_PAGO", **filt},
        {"$set": {"estado": "CANCELADO", "actualizadoEn": now, "liberacionPendiente": True},
         "$push": {"historial": {"estado": "CANCELADO", "fecha": now, "actor": actor, "motivo": motivo}}},
        return_document=ReturnDocument.AFTER)
    if doc:
        db.outbox.insert_one(new_event("order.cancelled", {"orderId": order_id, "motivo": motivo}))
        try:
            inventory.release(order_id, motivo)
            db.orders.update_one({"_id": order_id}, {"$set": {"liberacionPendiente": False}})
        except ApiError:
            log.warning("release_pending order=%s", order_id)  # el barrido lo reintenta
    return doc


# ---------------------------------------------------------------- S13 anular pedido pendiente
@app.post("/orders/{order_id}/cancel")
def cancel(order_id: str, ctx: CallContext = Depends(require_caller("gateway"))):
    ctx.require_role("CLIENTE")
    db = get_db()
    doc = _cancel(db, order_id, {"clienteId": ctx.user_id}, "cliente", "anulado-por-cliente")
    if doc:
        return order_dto(doc)
    existing = db.orders.find_one({"_id": order_id, "clienteId": ctx.user_id})
    if not existing:
        raise ApiError(404, "ORDER_NOT_FOUND", "Pedido no encontrado")
    raise ApiError(409, "INVALID_TRANSITION", f"Un pedido en estado {existing['estado']} no se puede anular")


# ---------------------------------------------------------------- lecturas internas
@app.get("/internal/orders")
def my_orders(pagina: int = Query(1, ge=1), tamano: int = Query(10, ge=1, le=20),
              ctx: CallContext = Depends(require_caller("graphql"))):
    user = ctx.require_user()  # sólo pedidos del usuario verificado
    db = get_db()
    filt = {"clienteId": user}
    total = db.orders.count_documents(filt)
    docs = db.orders.find(filt).sort("creadoEn", DESCENDING).skip((pagina - 1) * tamano).limit(tamano)
    return {"items": [order_dto(o) for o in docs], "total": total, "pagina": pagina, "tamano": tamano}


@app.get("/internal/orders/active-count")
def active_count(userId: str, ctx: CallContext = Depends(require_caller("clients"))):
    return {"cantidad": get_db().orders.count_documents({"clienteId": userId, "estado": {"$in": ACTIVOS}})}


@app.get("/internal/orders/{order_id}")
def get_order(order_id: str, ctx: CallContext = Depends(require_caller("graphql", "payments"))):
    o = get_db().orders.find_one({"_id": order_id})
    if ctx.caller == "payments":
        if not o:
            raise ApiError(404, "ORDER_NOT_FOUND", "Pedido no encontrado")
        # payments sólo necesita lo mínimo para cobrar: no recibe la dirección.
        return {"id": o["_id"], "numero": o["numero"], "clienteId": o["clienteId"], "estado": o["estado"], "total": o["total"]}
    user = ctx.require_user()
    is_admin = ctx.role == "ADMIN"
    if not o or (o["clienteId"] != user and not is_admin):
        # 404 y no 403: no se revela si existe un pedido de otra persona.
        raise ApiError(404, "ORDER_NOT_FOUND", "Pedido no encontrado")
    return order_dto(o, admin=is_admin)


# ---------------------------------------------------------------- resultado de pago (sólo payments)
@app.post("/internal/orders/{order_id}/payment-result")
def payment_result(order_id: str, body: PaymentResultIn, ctx: CallContext = Depends(require_caller("payments"))):
    db = get_db()
    now = datetime.now(timezone.utc)
    if body.resultado == "RECHAZADO":
        db.orders.update_one({"_id": order_id, "estado": "PENDIENTE_PAGO"},
                             {"$push": {"historial": {"estado": "PAGO_RECHAZADO", "fecha": now, "actor": "payments"}}})
        return {"estado": "PENDIENTE_PAGO"}
    doc = db.orders.find_one_and_update(
        {"_id": order_id, "estado": "PENDIENTE_PAGO", "total": body.monto},
        {"$set": {"estado": "PAGADO", "pagoId": body.pagoId, "actualizadoEn": now, "confirmacionStockPendiente": True},
         "$push": {"historial": {"estado": "PAGADO", "fecha": now, "actor": "payments"}}},
        return_document=ReturnDocument.AFTER)
    if not doc:
        current = db.orders.find_one({"_id": order_id})
        if not current:
            raise ApiError(404, "ORDER_NOT_FOUND", "Pedido no encontrado")
        if current["estado"] != "PENDIENTE_PAGO" and current.get("pagoId") == body.pagoId:
            return {"estado": current["estado"]}  # notificación repetida: idempotente
        if current["total"] != body.monto:
            raise ApiError(422, "AMOUNT_MISMATCH", "El monto pagado no coincide con el pedido")
        raise ApiError(409, "ORDER_NOT_PAYABLE", f"El pedido está {current['estado']}")
    db.outbox.insert_one(new_event("order.paid", {
        "orderId": order_id, "total": doc["total"], "despacho": doc["despacho"], "region": doc["entrega"]["region"],
        "items": [{"productoId": i["productoId"], "nombre": i["nombre"], "tipo": i["tipo"],
                   "cantidad": i["cantidad"], "subtotal": i["subtotal"]} for i in doc["items"]]}))
    try:
        inventory.commit(order_id)
        db.orders.update_one({"_id": order_id}, {"$set": {"confirmacionStockPendiente": False}})
    except ApiError:
        log.warning("commit_pending order=%s", order_id)
    return {"estado": "PAGADO"}


# ---------------------------------------------------------------- S28 / S29 administración y despacho
@app.get("/admin/orders")
def admin_orders(estado: Literal["PENDIENTE_PAGO", "PAGADO", "EN_PREPARACION", "DESPACHADO", "ENTREGADO", "CANCELADO"] | None = None,
                 pagina: int = Query(1, ge=1), tamano: int = Query(20, ge=1, le=50),
                 ctx: CallContext = Depends(require_caller("gateway"))):
    ctx.require_role("ADMIN")
    db = get_db()
    filt = {"estado": estado} if estado else {}
    total = db.orders.count_documents(filt)
    docs = db.orders.find(filt).sort("creadoEn", DESCENDING).skip((pagina - 1) * tamano).limit(tamano)
    return {"items": [order_dto(o, admin=True) for o in docs], "total": total, "pagina": pagina, "tamano": tamano}


@app.patch("/admin/orders/{order_id}/status")
def admin_status(order_id: str, body: StatusIn, ctx: CallContext = Depends(require_caller("gateway"))):
    ctx.require_role("ADMIN")
    origen = {v: k for k, v in TRANSICIONES_ADMIN.items()}[body.estado]
    now = datetime.now(timezone.utc)
    db = get_db()
    doc = db.orders.find_one_and_update(
        {"_id": order_id, "estado": origen},
        {"$set": {"estado": body.estado, "actualizadoEn": now},
         "$push": {"historial": {"estado": body.estado, "fecha": now, "actor": f"admin:{ctx.user_id}"}}},
        return_document=ReturnDocument.AFTER)
    if not doc:
        current = db.orders.find_one({"_id": order_id})
        if not current:
            raise ApiError(404, "ORDER_NOT_FOUND", "Pedido no encontrado")
        raise ApiError(409, "INVALID_TRANSITION", f"No se puede pasar de {current['estado']} a {body.estado}")
    if body.estado == "ENTREGADO":
        db.outbox.insert_one(new_event("order.delivered", {"orderId": order_id}))
    return order_dto(doc, admin=True)


# ---------------------------------------------------------------- barrido periódico
def _sweeper():
    """Cancela pedidos con el plazo de pago vencido (recupera stock) y
    reintenta confirmaciones/liberaciones de stock que quedaron pendientes."""
    while True:
        try:
            db = get_db()
            now = datetime.now(timezone.utc)
            for o in db.orders.find({"estado": "PENDIENTE_PAGO", "venceEn": {"$lt": now}}, {"_id": 1}).limit(100):
                _cancel(db, o["_id"], {}, "sistema", "plazo-de-pago-vencido")
            for o in db.orders.find({"liberacionPendiente": True}, {"_id": 1}).limit(100):
                inventory.release(o["_id"], "reintento")
                db.orders.update_one({"_id": o["_id"]}, {"$set": {"liberacionPendiente": False}})
            for o in db.orders.find({"confirmacionStockPendiente": True}, {"_id": 1}).limit(100):
                inventory.commit(o["_id"])
                db.orders.update_one({"_id": o["_id"]}, {"$set": {"confirmacionStockPendiente": False}})
        except Exception as exc:
            log.warning("sweeper_error err=%s", type(exc).__name__)
        time.sleep(SWEEP_INTERVAL)


if __name__ == "__main__":
    serve(app)
