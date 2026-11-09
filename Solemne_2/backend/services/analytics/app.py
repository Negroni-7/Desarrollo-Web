"""Analytics: servicio privado de reportes, separado de las transacciones.

- Origen de datos: eventos de dominio que orders y tastings publican (outbox).
  Analytics NO lee las bases de otros servicios.
- Actualización: casi en tiempo real (el despachador del outbox envía cada
  2 s). Retraso aceptado: hasta 1 minuto.
- Datos personales: los eventos no contienen identificadores de clientes,
  nombres, correos ni direcciones; sólo región, productos y montos.
- Acceso: sólo GraphQL (rol ADMIN verificado aguas arriba y aquí).
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import Depends, Query
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from vu_common.db import get_db
from vu_common.errors import ApiError
from vu_common.internal import CallContext, require_caller
from vu_common.server import create_app, serve

log = logging.getLogger("vu.analytics")
app = create_app("Viña Urbana - Analytics", health_check=lambda: get_db().command("ping"))


@app.on_event("startup")
def _startup():
    db = get_db()
    db.events.create_index([("tipo", 1), ("dia", 1)])


class EventIn(BaseModel):
    eventId: str = Field(min_length=8, max_length=64)
    tipo: Literal["order.paid", "order.cancelled", "order.delivered", "booking.created"]
    ocurridoEn: datetime
    datos: dict


ALLOWED_SOURCES = {"order.paid": "orders", "order.cancelled": "orders", "order.delivered": "orders",
                   "booking.created": "tastings"}


@app.post("/internal/events", status_code=201)
def ingest(ev: EventIn, ctx: CallContext = Depends(require_caller("orders", "tastings"))):
    if ALLOWED_SOURCES[ev.tipo] != ctx.caller:
        raise ApiError(403, "FORBIDDEN_EVENT", "El emisor no es autoridad de este evento")
    datos = dict(ev.datos)
    for forbidden in ("clienteId", "email", "nombre", "telefono", "entrega", "contacto"):
        datos.pop(forbidden, None)  # defensa adicional contra datos personales
    try:
        get_db().events.insert_one({"_id": ev.eventId, "tipo": ev.tipo, "ocurridoEn": ev.ocurridoEn,
                                    "dia": ev.ocurridoEn.astimezone(timezone.utc).date().isoformat(),
                                    "datos": datos, "fuente": ctx.caller, "recibidoEn": datetime.now(timezone.utc)})
    except DuplicateKeyError:
        return {"duplicado": True}
    return {"duplicado": False}


@app.get("/internal/sales-summary")
def sales_summary(desde: date, hasta: date, ctx: CallContext = Depends(require_caller("graphql"))):
    if ctx.role != "ADMIN":
        raise ApiError(403, "FORBIDDEN", "Sólo administración")
    if hasta < desde or (hasta - desde).days > 366:
        raise ApiError(400, "INVALID_RANGE", "Rango inválido (máximo 1 año)")
    rango = {"dia": {"$gte": desde.isoformat(), "$lte": hasta.isoformat()}}
    db = get_db()
    paid = {"tipo": "order.paid", **rango}

    totals = list(db.events.aggregate([{"$match": paid},
                                       {"$group": {"_id": None, "ventas": {"$sum": "$datos.total"}, "pedidos": {"$sum": 1}}}]))
    ventas = totals[0]["ventas"] if totals else 0
    pedidos = totals[0]["pedidos"] if totals else 0

    por_dia = [{"dia": d["_id"], "ventas": d["ventas"], "pedidos": d["pedidos"]} for d in db.events.aggregate([
        {"$match": paid}, {"$group": {"_id": "$dia", "ventas": {"$sum": "$datos.total"}, "pedidos": {"$sum": 1}}},
        {"$sort": {"_id": 1}}])]

    items = [{"$match": paid}, {"$unwind": "$datos.items"}]
    por_tipo = [{"tipo": d["_id"], "ventas": d["ventas"], "unidades": d["unidades"]} for d in db.events.aggregate(items + [
        {"$group": {"_id": "$datos.items.tipo", "ventas": {"$sum": "$datos.items.subtotal"}, "unidades": {"$sum": "$datos.items.cantidad"}}},
        {"$sort": {"ventas": -1}}])]
    top = [{"productoId": d["_id"], "nombre": d["nombre"], "unidades": d["unidades"], "ventas": d["ventas"]}
           for d in db.events.aggregate(items + [
               {"$group": {"_id": "$datos.items.productoId", "nombre": {"$last": "$datos.items.nombre"},
                           "unidades": {"$sum": "$datos.items.cantidad"}, "ventas": {"$sum": "$datos.items.subtotal"}}},
               {"$sort": {"unidades": -1}}, {"$limit": 5}])]
    por_region = [{"region": d["_id"], "pedidos": d["pedidos"]} for d in db.events.aggregate([
        {"$match": paid}, {"$group": {"_id": "$datos.region", "pedidos": {"$sum": 1}}}, {"$sort": {"pedidos": -1}}])]
    reservas = [{"paquete": d["_id"], "reservas": d["reservas"], "personas": d["personas"]} for d in db.events.aggregate([
        {"$match": {"tipo": "booking.created", **rango}},
        {"$group": {"_id": "$datos.paquete", "reservas": {"$sum": 1}, "personas": {"$sum": "$datos.personas"}}},
        {"$sort": {"reservas": -1}}])]
    cancelados = db.events.count_documents({"tipo": "order.cancelled", **rango})
    return {"desde": desde.isoformat(), "hasta": hasta.isoformat(), "totalVentas": ventas, "pedidosPagados": pedidos,
            "ticketPromedio": round(ventas / pedidos) if pedidos else 0, "pedidosCancelados": cancelados,
            "ventasPorDia": por_dia, "ventasPorTipo": por_tipo, "topProductos": top, "pedidosPorRegion": por_region,
            "reservasPorPaquete": reservas, "generadoEn": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    serve(app)
