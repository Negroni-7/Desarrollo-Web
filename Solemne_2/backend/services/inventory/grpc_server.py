"""Servidor gRPC de inventory (sólo red privada).

Seguridad:
  - mTLS: el cliente debe presentar un certificado firmado por la CA interna.
  - Autorización por método según el CN del certificado (sólo "orders").
  - Si TLS está deshabilitado (modo desarrollo) se exige el token del tramo
    inventory<-orders en la metadata x-service-token.
Robustez:
  - Plazos: si al llamado le quedan < 50 ms se responde DEADLINE_EXCEEDED.
  - Idempotencia: reservation_id = id del pedido; repetir una llamada no
    descuenta stock dos veces.
"""
import logging
import os
import secrets
from concurrent import futures
from datetime import datetime, timezone

import grpc
from pymongo.errors import DuplicateKeyError

import inventory_pb2 as pb
import inventory_pb2_grpc as pb_grpc
from vu_common import settings
from vu_common.db import get_db
from vu_common.vault import vault

log = logging.getLogger("vu.inventory.grpc")

ALLOWED = {  # método -> identidades permitidas
    "QuoteItems": {"orders"},
    "ReserveStock": {"orders"},
    "CommitReservation": {"orders"},
    "ReleaseReservation": {"orders"},
}
MAX_ITEMS = 50
MAX_QTY = 24


def _identity(context) -> str | None:
    if settings.TLS_ENABLED:
        cn = context.auth_context().get("x509_common_name")
        return cn[0].decode() if cn else None
    md = dict(context.invocation_metadata())
    caller, token = md.get("x-caller-id", ""), md.get("x-service-token", "")
    try:
        expected = vault.read(f"internal/inventory/{caller}")["token"]
    except Exception:
        return None
    return caller if secrets.compare_digest(token.encode(), expected.encode()) else None


def _guard(method: str, context):
    ident = _identity(context)
    if ident not in ALLOWED[method]:
        log.warning("grpc_denied method=%s identity=%s", method, ident)
        context.abort(grpc.StatusCode.PERMISSION_DENIED, "identidad no autorizada")
    remaining = context.time_remaining()
    if remaining is not None and remaining < 0.05:
        context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "plazo insuficiente")


def _merge(items) -> dict[str, int]:
    if len(items) == 0 or len(items) > MAX_ITEMS:
        raise ValueError("cantidad de ítems inválida")
    merged: dict[str, int] = {}
    for it in items:
        if not it.product_id or it.quantity < 1 or it.quantity > MAX_QTY:
            raise ValueError("ítem inválido")
        merged[it.product_id] = merged.get(it.product_id, 0) + it.quantity
        if merged[it.product_id] > MAX_QTY:
            raise ValueError("cantidad máxima por producto excedida")
    return merged


class InventoryReservations(pb_grpc.InventoryReservationsServicer):
    def QuoteItems(self, request, context):
        _guard("QuoteItems", context)
        try:
            wanted = _merge(request.items)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        docs = {d["_id"]: d for d in get_db().products.find({"_id": {"$in": list(wanted)}})}
        out = []
        for pid, qty in wanted.items():
            d = docs.get(pid)
            if not d:
                out.append(pb.QuotedItem(product_id=pid, active=False, available=False, quantity=qty))
                continue
            out.append(pb.QuotedItem(
                product_id=pid, name=d["nombre"], type=d["tipo"], unit_price=d["precio"], image=d["imagen"],
                active=d["activo"], available=d["activo"] and d["stock"] >= qty, quantity=qty))
        return pb.QuoteResponse(items=out)

    def ReserveStock(self, request, context):
        _guard("ReserveStock", context)
        rid = request.reservation_id
        if not rid:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "reservation_id requerido")
        try:
            wanted = _merge(request.items)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        db = get_db()
        now = datetime.now(timezone.utc)
        try:
            db.reservations.insert_one({"_id": rid, "status": "RESERVING", "items": wanted, "creadaEn": now})
        except DuplicateKeyError:
            # Idempotencia: la misma reserva ya fue procesada; se informa su estado sin volver a descontar.
            prev = db.reservations.find_one({"_id": rid})
            if prev["status"] == "FAILED":
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "sin stock: " + ",".join(prev.get("unavailable", [])))
            return pb.ReservationResult(reservation_id=rid, status=prev["status"])

        decremented, unavailable = [], []
        for pid in sorted(wanted):
            qty = wanted[pid]
            res = db.products.update_one({"_id": pid, "activo": True, "stock": {"$gte": qty}}, {"$inc": {"stock": -qty}})
            if res.modified_count == 1:
                decremented.append(pid)
            else:
                unavailable.append(pid)
        if unavailable:
            for pid in decremented:  # compensación: se devuelve lo ya descontado
                db.products.update_one({"_id": pid}, {"$inc": {"stock": wanted[pid]}})
            db.reservations.update_one({"_id": rid}, {"$set": {"status": "FAILED", "unavailable": unavailable}})
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "sin stock: " + ",".join(unavailable))
        db.reservations.update_one({"_id": rid}, {"$set": {"status": "HELD", "actualizadaEn": now}})
        return pb.ReservationResult(reservation_id=rid, status="HELD")

    def CommitReservation(self, request, context):
        _guard("CommitReservation", context)
        db = get_db()
        rid = request.reservation_id
        doc = db.reservations.find_one_and_update(
            {"_id": rid, "status": "HELD"}, {"$set": {"status": "COMMITTED", "actualizadaEn": datetime.now(timezone.utc)}})
        if doc:
            return pb.ReservationResult(reservation_id=rid, status="COMMITTED")
        current = db.reservations.find_one({"_id": rid})
        if not current:
            context.abort(grpc.StatusCode.NOT_FOUND, "reserva inexistente")
        if current["status"] == "COMMITTED":
            return pb.ReservationResult(reservation_id=rid, status="COMMITTED")
        context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"reserva en estado {current['status']}")

    def ReleaseReservation(self, request, context):
        _guard("ReleaseReservation", context)
        db = get_db()
        rid = request.reservation_id
        doc = db.reservations.find_one_and_update(
            {"_id": rid, "status": "HELD"},
            {"$set": {"status": "RELEASED", "motivo": request.reason[:60], "actualizadaEn": datetime.now(timezone.utc)}})
        if doc:
            for pid, qty in doc["items"].items():  # recuperación de stock
                db.products.update_one({"_id": pid}, {"$inc": {"stock": qty}})
            return pb.ReservationResult(reservation_id=rid, status="RELEASED")
        current = db.reservations.find_one({"_id": rid})
        return pb.ReservationResult(reservation_id=rid, status=current["status"] if current else "NONE")


def start_grpc_server():
    port = int(os.getenv("GRPC_PORT", "50051"))
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=16),
        options=[("grpc.max_receive_message_length", 64 * 1024), ("grpc.max_send_message_length", 256 * 1024)],
    )
    pb_grpc.add_InventoryReservationsServicer_to_server(InventoryReservations(), server)
    addr = f"{settings.HOST}:{port}"
    if settings.TLS_ENABLED:
        with open(settings.TLS_KEY_FILE, "rb") as k, open(settings.TLS_CERT_FILE, "rb") as c, open(settings.TLS_CA_FILE, "rb") as ca:
            creds = grpc.ssl_server_credentials([(k.read(), c.read())], root_certificates=ca.read(),
                                                require_client_auth=True)
        server.add_secure_port(addr, creds)
    else:
        server.add_insecure_port(addr)
    server.start()
    log.info("grpc_server_started port=%s mtls=%s", port, settings.TLS_ENABLED)
    return server
