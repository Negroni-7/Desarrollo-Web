"""Payments: inicio de pagos, verificación del resultado con el proveedor,
notificaciones firmadas (webhook) y emisión de boletas.

Autoridad de datos: transacciones de pago, eventos del proveedor y boletas.
Reglas de seguridad:
  - El monto se obtiene de orders, nunca del navegador.
  - El estado APROBADO sólo se acepta desde el proveedor: consulta servidor a
    servidor (verify) o notificación con firma HMAC válida y reciente.
  - Cada notificación se procesa una sola vez (event_id único).
  - Un pedido no puede quedar con dos pagos aprobados: el segundo se marca
    REQUIERE_REVERSA para devolución.
"""
import hashlib
import hmac
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone

from fastapi import Depends, Query, Request
from pydantic import BaseModel
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from providers import get_provider
from vu_common.db import get_db
from vu_common.errors import ApiError, DependencyError
from vu_common.internal import CallContext, ServiceClient, require_caller
from vu_common.server import create_app, serve
from vu_common.vault import vault

log = logging.getLogger("vu.payments")
app = create_app("Viña Urbana - Payments", health_check=lambda: get_db().command("ping"))
orders_api = ServiceClient("orders")
provider = get_provider()

RETURN_URL = os.getenv("PAYMENT_RETURN_URL", "https://localhost:8443/")
WEBHOOK_TOLERANCE = 300  # segundos
IVA = 0.19


@app.on_event("startup")
def _startup():
    db = get_db()
    db.payments.create_index("pedidoId")
    db.payments.create_index("tokenProveedor", unique=True, sparse=True)
    # A lo más un pago INICIADO y uno APROBADO por pedido.
    db.payments.create_index("pedidoId", name="uniq_iniciado", unique=True,
                             partialFilterExpression={"estado": "INICIADO"})
    db.payments.create_index("pedidoId", name="uniq_aprobado", unique=True,
                             partialFilterExpression={"estado": "APROBADO"})
    threading.Thread(target=_retry_notifications, daemon=True).start()


class PaymentIn(BaseModel):
    model_config = {"extra": "forbid"}  # un "monto" enviado por el navegador se rechaza
    pedidoId: str


def payment_dto(p: dict) -> dict:
    return {"pagoId": p["_id"], "pedidoId": p["pedidoId"], "estado": p["estado"], "monto": p["monto"],
            "actualizadoEn": p["actualizadoEn"].isoformat(), "boleta": p.get("boleta")}


# ---------------------------------------------------------------- S14 iniciar pago
@app.post("/payments", status_code=201)
def start_payment(body: PaymentIn, ctx: CallContext = Depends(require_caller("gateway"))):
    ctx.require_role("CLIENTE")
    resp = orders_api.request("GET", f"/internal/orders/{body.pedidoId}", ctx)
    if resp.status_code == 404:
        raise ApiError(404, "ORDER_NOT_FOUND", "Pedido no encontrado")
    if resp.status_code != 200:
        raise DependencyError("orders")
    order = resp.json()
    if order["clienteId"] != ctx.user_id:
        raise ApiError(404, "ORDER_NOT_FOUND", "Pedido no encontrado")
    if order["estado"] != "PENDIENTE_PAGO":
        raise ApiError(409, "ORDER_NOT_PAYABLE", f"El pedido está {order['estado']}")

    db = get_db()
    existing = db.payments.find_one({"pedidoId": order["id"], "estado": "INICIADO"})
    if existing:  # el cliente volvió a presionar "Pagar": se reutiliza la transacción
        return {**payment_dto(existing), "redirectUrl": existing["redirectUrl"]}

    pago_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    doc = {"_id": pago_id, "pedidoId": order["id"], "clienteId": ctx.user_id, "monto": order["total"],
           "estado": "INICIADO", "proveedor": provider.name, "creadoEn": now, "actualizadoEn": now,
           "notificacionPedido": "NO_APLICA"}
    try:
        db.payments.insert_one(doc)
    except DuplicateKeyError:
        existing = db.payments.find_one({"pedidoId": order["id"], "estado": "INICIADO"})
        return {**payment_dto(existing), "redirectUrl": existing.get("redirectUrl")}
    try:
        tx = provider.create(buy_order=f"VU{order['numero']:08d}", session_id=pago_id, amount=order["total"],
                             return_url=f"{RETURN_URL}?pago={pago_id}")
    except DependencyError:
        db.payments.update_one({"_id": pago_id}, {"$set": {"estado": "ERROR_PROVEEDOR"}})
        raise
    db.payments.update_one({"_id": pago_id}, {"$set": {"tokenProveedor": tx["token"], "redirectUrl": tx["redirect_url"]}})
    doc["redirectUrl"] = tx["redirect_url"]
    log.info("payment_started pago=%s pedido=%s", pago_id, order["id"])
    return {**payment_dto(doc), "redirectUrl": tx["redirect_url"]}


# ---------------------------------------------------------------- aplicación del resultado
def _emit_receipt(db, monto: int) -> dict:
    folio = db.counters.find_one_and_update({"_id": "boleta"}, {"$inc": {"seq": 1}}, upsert=True,
                                            return_document=ReturnDocument.AFTER)["seq"]
    neto = round(monto / (1 + IVA))
    return {"folio": folio, "neto": neto, "iva": monto - neto, "total": monto,
            "emitidaEn": datetime.now(timezone.utc).isoformat()}


def _notify_order(db, pago: dict):
    try:
        r = orders_api.request("POST", f"/internal/orders/{pago['pedidoId']}/payment-result",
                               json={"pagoId": pago["_id"], "resultado": pago["estado"], "monto": pago["monto"]})
    except DependencyError:
        db.payments.update_one({"_id": pago["_id"]}, {"$set": {"notificacionPedido": "PENDIENTE"}})
        return
    if r.status_code == 200:
        db.payments.update_one({"_id": pago["_id"]}, {"$set": {"notificacionPedido": "OK"}})
    elif r.status_code in (409, 422) and pago["estado"] == "APROBADO":
        # El pedido ya no admite pago (p. ej. venció y se anuló): se marca para devolución.
        db.payments.update_one({"_id": pago["_id"]}, {"$set": {"estado": "REQUIERE_REVERSA", "notificacionPedido": "RECHAZADA"},
                                                      "$unset": {"boleta": ""}})
        log.warning("payment_requires_refund pago=%s", pago["_id"])
    else:
        db.payments.update_one({"_id": pago["_id"]}, {"$set": {"notificacionPedido": "PENDIENTE"}})


def apply_result(pago: dict, resultado: str, monto: int, origen: str) -> dict:
    db = get_db()
    if resultado not in ("APROBADO", "RECHAZADO"):
        return pago
    if monto != pago["monto"]:
        log.error("amount_mismatch pago=%s origen=%s", pago["_id"], origen)
        db.payments.update_one({"_id": pago["_id"], "estado": "INICIADO"}, {"$set": {"estado": "REQUIERE_REVISION"}})
        return db.payments.find_one({"_id": pago["_id"]})
    now = datetime.now(timezone.utc)
    update = {"estado": resultado, "actualizadoEn": now, "origenResultado": origen, "notificacionPedido": "PENDIENTE"}
    if resultado == "APROBADO":
        update["boleta"] = _emit_receipt(db, monto)
    try:
        updated = db.payments.find_one_and_update({"_id": pago["_id"], "estado": "INICIADO"}, {"$set": update},
                                                  return_document=ReturnDocument.AFTER)
    except DuplicateKeyError:
        # Ya existe otro pago aprobado para el mismo pedido: este cobro debe devolverse.
        updated = db.payments.find_one_and_update(
            {"_id": pago["_id"], "estado": "INICIADO"},
            {"$set": {"estado": "REQUIERE_REVERSA", "actualizadoEn": now, "notificacionPedido": "NO_APLICA"}},
            return_document=ReturnDocument.AFTER)
        return updated or db.payments.find_one({"_id": pago["_id"]})
    if not updated:  # ya estaba resuelto: idempotente
        return db.payments.find_one({"_id": pago["_id"]})
    _notify_order(db, updated)
    return db.payments.find_one({"_id": pago["_id"]})


# ---------------------------------------------------------------- S15 verificar resultado
@app.post("/payments/{pago_id}/verify")
def verify(pago_id: str, ctx: CallContext = Depends(require_caller("gateway"))):
    ctx.require_role("CLIENTE")
    pago = get_db().payments.find_one({"_id": pago_id, "clienteId": ctx.user_id})
    if not pago:
        raise ApiError(404, "PAYMENT_NOT_FOUND", "Pago no encontrado")
    if pago["estado"] == "INICIADO" and pago.get("tokenProveedor"):
        st = provider.status(pago["tokenProveedor"])  # consulta servidor a servidor
        pago = apply_result(pago, st["resultado"], st["monto"], "verify")
    return payment_dto(pago)


# ---------------------------------------------------------------- S16 webhook del proveedor
@app.post("/payments/webhook")
async def webhook(request: Request, ctx: CallContext = Depends(require_caller("gateway"))):
    raw = await request.body()
    ts = request.headers.get("x-provider-timestamp", "")
    sig = request.headers.get("x-provider-signature", "")
    secret = vault.read("payments/provider")["webhook_secret"]
    expected = "sha256=" + hmac.new(secret.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    if not ts.isdigit() or abs(time.time() - int(ts)) > WEBHOOK_TOLERANCE or not hmac.compare_digest(sig, expected):
        log.warning("webhook_rejected reason=signature")
        raise ApiError(401, "INVALID_SIGNATURE", "Firma inválida")
    try:
        event = json.loads(raw)
        event_id, token = str(event["event_id"]), str(event["token"])
        status, amount = str(event["status"]), int(event["amount"])
    except (ValueError, KeyError, TypeError):
        raise ApiError(400, "INVALID_EVENT", "Evento inválido")
    db = get_db()
    try:
        db.webhook_events.insert_one({"_id": event_id, "token": token, "recibidoEn": datetime.now(timezone.utc)})
    except DuplicateKeyError:
        return {"recibido": True, "duplicado": True}  # ya procesado: no se repiten efectos
    pago = db.payments.find_one({"tokenProveedor": token})
    if not pago:
        raise ApiError(404, "PAYMENT_NOT_FOUND", "Transacción desconocida")
    resultado = {"AUTHORIZED": "APROBADO", "REJECTED": "RECHAZADO"}.get(status, "INICIADO")
    apply_result(pago, resultado, amount, "webhook")
    return {"recibido": True, "duplicado": False}


# ---------------------------------------------------------------- lectura para GraphQL
@app.get("/internal/payments")
def by_orders(pedidoIds: str = Query(..., max_length=4000), ctx: CallContext = Depends(require_caller("graphql"))):
    user = ctx.require_user()
    ids = [i for i in pedidoIds.split(",") if i][:50]
    filt = {"pedidoId": {"$in": ids}}
    if ctx.role != "ADMIN":
        filt["clienteId"] = user
    result: dict[str, dict] = {}
    for p in get_db().payments.find(filt).sort("actualizadoEn", 1):
        result[p["pedidoId"]] = payment_dto(p)  # queda el más reciente por pedido
    return {"items": list(result.values())}


def _retry_notifications():
    while True:
        try:
            db = get_db()
            for p in db.payments.find({"notificacionPedido": "PENDIENTE", "estado": {"$in": ["APROBADO", "RECHAZADO"]}}).limit(50):
                _notify_order(db, p)
        except Exception as exc:
            log.warning("retry_error err=%s", type(exc).__name__)
        time.sleep(10)


if __name__ == "__main__":
    serve(app)
