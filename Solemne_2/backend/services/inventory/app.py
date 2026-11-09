"""Inventory: catálogo, stock y reservas de stock.

Autoridad de datos: productos (precio oficial, disponibilidad, activo) y
reservas de stock. Expone:
  - REST (vía gateway/graphql): catálogo público y administración.
  - gRPC (sólo para orders, con mTLS): cotizar, reservar, confirmar y liberar.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Literal

from fastapi import Depends, Query
from pydantic import BaseModel, Field, field_validator
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from vu_common.db import get_db
from vu_common.errors import ApiError
from vu_common.internal import CallContext, require_caller
from vu_common.server import create_app, serve

log = logging.getLogger("vu.inventory")
app = create_app("Viña Urbana - Inventory", health_check=lambda: get_db().command("ping"))

TIPOS = ("tinto", "blanco", "rosado", "especial")
IMAGE_RE = r"images/vinos/[a-z0-9\-]+\.(jpg|jpeg|png|webp|avif)"


@app.on_event("startup")
def _startup():
    db = get_db()
    db.products.create_index([("tipo", ASCENDING), ("activo", ASCENDING)])
    db.stock_movements.create_index("productoId")
    # El servidor gRPC corre en el mismo proceso: comparte la autoridad sobre el stock.
    from grpc_server import start_grpc_server
    # Se guarda la referencia: si el objeto servidor se libera, gRPC deja de escuchar.
    app.state.grpc_server = start_grpc_server()


def public_dto(p: dict) -> dict:
    """Campos públicos del catálogo: no incluye stock exacto ni datos de auditoría."""
    return {
        "id": p["_id"], "nombre": p["nombre"], "tipo": p["tipo"], "vina": p["vina"],
        "volumenMl": p["volumenMl"], "gradoAlcohol": p["gradoAlcohol"], "precio": p["precio"],
        "imagen": p["imagen"], "recomendado": p.get("recomendado", False),
        "disponible": p["activo"] and p["stock"] > 0,
    }


def admin_dto(p: dict) -> dict:
    return {**public_dto(p), "stock": p["stock"], "activo": p["activo"],
            "actualizadoEn": p.get("actualizadoEn").isoformat() if p.get("actualizadoEn") else None}


# ---------------------------------------------------------------- S01 catálogo público
@app.get("/products")
def list_products(
    tipo: Literal["tinto", "blanco", "rosado", "especial"] | None = None,
    recomendado: bool | None = None,
    pagina: int = Query(1, ge=1, le=100),
    tamano: int = Query(24, ge=1, le=50),
    ctx: CallContext = Depends(require_caller("gateway", "graphql")),
):
    filt = {"activo": True}
    if tipo:
        filt["tipo"] = tipo
    if recomendado is not None:
        filt["recomendado"] = recomendado
    db = get_db()
    total = db.products.count_documents(filt)
    cursor = db.products.find(filt).sort("nombre", ASCENDING).skip((pagina - 1) * tamano).limit(tamano)
    return {"items": [public_dto(p) for p in cursor], "total": total, "pagina": pagina, "tamano": tamano}


@app.get("/internal/products/batch")
def batch(ids: str = Query(..., max_length=2000), ctx: CallContext = Depends(require_caller("graphql"))):
    """Lectura por lote para el DataLoader de GraphQL (evita N llamadas por ítem)."""
    id_list = [i for i in ids.split(",") if i][:100]
    docs = get_db().products.find({"_id": {"$in": id_list}})
    return {"items": [public_dto(p) | {"activo": p["activo"]} for p in docs]}


@app.get("/internal/products/low-stock")
def low_stock(umbral: int = Query(5, ge=0, le=100), ctx: CallContext = Depends(require_caller("graphql"))):
    if ctx.role != "ADMIN":
        raise ApiError(403, "FORBIDDEN", "Sólo administración")
    docs = get_db().products.find({"activo": True, "stock": {"$lte": umbral}}).sort("stock", ASCENDING)
    return {"items": [{"id": p["_id"], "nombre": p["nombre"], "stock": p["stock"]} for p in docs]}


# ---------------------------------------------------------------- administración (S23-S27)
class ProductIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    tipo: Literal["tinto", "blanco", "rosado", "especial"]
    vina: str = Field(min_length=2, max_length=60)
    volumenMl: int = Field(ge=187, le=3000)
    gradoAlcohol: float = Field(ge=5, le=20)
    precio: int = Field(ge=1000, le=5_000_000)
    imagen: str
    recomendado: bool = False

    @field_validator("imagen")
    @classmethod
    def image(cls, v):
        if not re.fullmatch(IMAGE_RE, v):
            raise ValueError("debe ser una ruta images/vinos/<archivo>")
        return v


class ProductCreate(ProductIn):
    id: str = Field(pattern=r"^[a-z0-9\-]{3,40}$")
    stock: int = Field(ge=0, le=10000)


class StockAdjust(BaseModel):
    delta: int = Field(ge=-1000, le=1000)
    motivo: Literal["INGRESO_BODEGA", "AJUSTE_INVENTARIO", "MERMA"]

    @field_validator("delta")
    @classmethod
    def non_zero(cls, v):
        if v == 0:
            raise ValueError("no puede ser 0")
        return v


@app.get("/admin/products")
def admin_list(ctx: CallContext = Depends(require_caller("gateway"))):
    ctx.require_role("ADMIN")
    return {"items": [admin_dto(p) for p in get_db().products.find().sort("nombre", ASCENDING)]}


@app.post("/admin/products", status_code=201)
def admin_create(body: ProductCreate, ctx: CallContext = Depends(require_caller("gateway"))):
    ctx.require_role("ADMIN")
    now = datetime.now(timezone.utc)
    doc = body.model_dump()
    doc["_id"] = doc.pop("id")
    doc.update(activo=True, creadoEn=now, actualizadoEn=now)
    try:
        get_db().products.insert_one(doc)
    except DuplicateKeyError:
        raise ApiError(409, "PRODUCT_EXISTS", "Ya existe un producto con ese identificador")
    return admin_dto(doc)


@app.put("/admin/products/{pid}")
def admin_put(pid: str, body: ProductIn, ctx: CallContext = Depends(require_caller("gateway"))):
    """Reemplaza la ficha comercial. El stock NO se modifica aquí (tiene su propia operación auditada)."""
    ctx.require_role("ADMIN")
    res = get_db().products.find_one_and_update(
        {"_id": pid}, {"$set": {**body.model_dump(), "actualizadoEn": datetime.now(timezone.utc)}}, return_document=True)
    if not res:
        raise ApiError(404, "PRODUCT_NOT_FOUND", "Producto no encontrado")
    return admin_dto(res)


@app.patch("/admin/products/{pid}/stock")
def admin_stock(pid: str, body: StockAdjust, ctx: CallContext = Depends(require_caller("gateway"))):
    ctx.require_role("ADMIN")
    db = get_db()
    cond = {"_id": pid}
    if body.delta < 0:
        cond["stock"] = {"$gte": -body.delta}  # nunca deja stock negativo
    res = db.products.find_one_and_update(
        cond, {"$inc": {"stock": body.delta}, "$set": {"actualizadoEn": datetime.now(timezone.utc)}}, return_document=True)
    if not res:
        if db.products.count_documents({"_id": pid}) == 0:
            raise ApiError(404, "PRODUCT_NOT_FOUND", "Producto no encontrado")
        raise ApiError(409, "INSUFFICIENT_STOCK", "El ajuste dejaría stock negativo")
    db.stock_movements.insert_one({"productoId": pid, "delta": body.delta, "motivo": body.motivo,
                                   "actor": ctx.user_id, "fecha": datetime.now(timezone.utc)})
    return admin_dto(res)


@app.delete("/admin/products/{pid}")
def admin_delete(pid: str, ctx: CallContext = Depends(require_caller("gateway"))):
    """Eliminación lógica: el producto sale del catálogo, pero los pedidos
    históricos conservan su nombre y precio porque guardan una copia."""
    ctx.require_role("ADMIN")
    res = get_db().products.update_one({"_id": pid}, {"$set": {"activo": False, "actualizadoEn": datetime.now(timezone.utc)}})
    if res.matched_count != 1:
        raise ApiError(404, "PRODUCT_NOT_FOUND", "Producto no encontrado")
    return {"id": pid, "activo": False}


if __name__ == "__main__":
    serve(app)
