"""Cliente gRPC hacia inventory con mTLS, plazos y traducción de errores."""
import logging
import os
import threading

import grpc

import inventory_pb2 as pb
import inventory_pb2_grpc as pb_grpc
from vu_common import settings
from vu_common.errors import ApiError, DependencyError
from vu_common.vault import vault

log = logging.getLogger("vu.orders.grpc")

QUOTE_DEADLINE = 1.0
RESERVATION_DEADLINE = 2.0

_stub = None
_lock = threading.Lock()


def _get_stub():
    global _stub
    with _lock:
        if _stub is None:
            target = os.getenv("INVENTORY_GRPC", "inventory:50051")
            # Reconexión rápida si inventory se reinicia; límites de tamaño de mensaje.
            options = [("grpc.initial_reconnect_backoff_ms", 300), ("grpc.min_reconnect_backoff_ms", 300),
                       ("grpc.max_reconnect_backoff_ms", 3000), ("grpc.max_receive_message_length", 256 * 1024),
                       ("grpc.keepalive_time_ms", 30000)]
            if settings.TLS_ENABLED:
                with open(settings.TLS_CA_FILE, "rb") as ca, open(settings.TLS_KEY_FILE, "rb") as k, open(settings.TLS_CERT_FILE, "rb") as c:
                    creds = grpc.ssl_channel_credentials(root_certificates=ca.read(), private_key=k.read(), certificate_chain=c.read())
                channel = grpc.secure_channel(target, creds, options=options)
            else:
                channel = grpc.insecure_channel(target, options=options)
            _stub = pb_grpc.InventoryReservationsStub(channel)
        return _stub


def _metadata():
    if settings.TLS_ENABLED:
        return None  # la identidad la aporta el certificado de cliente
    token = vault.read("internal/inventory/orders")["token"]
    return (("x-caller-id", "orders"), ("x-service-token", token))


def _items(items: list[dict]):
    return [pb.ItemQuantity(product_id=i["productoId"], quantity=i["cantidad"]) for i in items]


def _call(method: str, request, deadline: float):
    try:
        return getattr(_get_stub(), method)(request, timeout=deadline, metadata=_metadata())
    except grpc.RpcError as err:
        code = err.code()
        log.warning("grpc_error method=%s code=%s", method, code.name)
        if code == grpc.StatusCode.FAILED_PRECONDITION:
            detail = err.details() or ""
            ids = detail.split(":", 1)[1].strip().split(",") if ":" in detail else []
            raise ApiError(409, "PRODUCTS_UNAVAILABLE", "Uno o más productos no tienen stock suficiente",
                           [{"productoId": i} for i in ids if i])
        if code == grpc.StatusCode.INVALID_ARGUMENT:
            raise ApiError(400, "VALIDATION_ERROR", err.details() or "Ítems inválidos")
        if code == grpc.StatusCode.NOT_FOUND:
            raise ApiError(404, "RESERVATION_NOT_FOUND", "Reserva inexistente")
        # UNAVAILABLE, DEADLINE_EXCEEDED, PERMISSION_DENIED, etc.
        raise DependencyError("inventory")


def quote(items: list[dict]):
    return _call("QuoteItems", pb.QuoteRequest(items=_items(items)), QUOTE_DEADLINE).items


def reserve(order_id: str, items: list[dict]):
    return _call("ReserveStock", pb.ReserveRequest(reservation_id=order_id, items=_items(items)), RESERVATION_DEADLINE)


def commit(order_id: str):
    return _call("CommitReservation", pb.ReservationRef(reservation_id=order_id), RESERVATION_DEADLINE)


def release(order_id: str, reason: str):
    return _call("ReleaseReservation", pb.ReservationRef(reservation_id=order_id, reason=reason), RESERVATION_DEADLINE)
