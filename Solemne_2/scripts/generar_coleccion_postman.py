"""Genera docs/postman/VinaUrbana.postman_collection.json para probar la API a mano
(Postman o Insomnia). Sin secretos: las contraseñas se escriben en variables.

Variables: baseUrl, emailCliente, passwordCliente, emailAdmin, passwordAdmin,
pedidoId, pagoId (los dos últimos se completan solos con los scripts de prueba).
"""
import json
import uuid
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "postman"
OUT.mkdir(parents=True, exist_ok=True)

H = [{"key": "X-Requested-With", "value": "XMLHttpRequest"}, {"key": "Content-Type", "value": "application/json"}]


def req(name, method, path, body=None, extra_headers=None, query=None, tests=None):
    url = {"raw": "{{baseUrl}}" + path + ("?" + "&".join(f"{k}={v}" for k, v in query.items()) if query else ""),
           "host": ["{{baseUrl}}"], "path": [p for p in path.strip("/").split("/")]}
    if query:
        url["query"] = [{"key": k, "value": v} for k, v in query.items()]
    item = {"name": name, "request": {"method": method, "header": H + (extra_headers or []), "url": url}}
    if body is not None:
        item["request"]["body"] = {"mode": "raw", "raw": json.dumps(body, ensure_ascii=False, indent=2),
                                   "options": {"raw": {"language": "json"}}}
    if tests:
        item["event"] = [{"listen": "test", "script": {"type": "text/javascript", "exec": tests}}]
    return item


ENTREGA = {"nombreReceptor": "Ana Pérez", "calle": "Av. Providencia", "numero": "1500", "comuna": "Providencia",
           "region": "Metropolitana", "telefono": "+56955551234"}
gql = lambda q, v=None: {"query": q, **({"variables": v} if v else {})}

folders = [
    ("1. Público (datos del frontend)", [
        req("S01 Catálogo", "GET", "/api/v1/products"),
        req("S01 Catálogo tintos", "GET", "/api/v1/products", query={"tipo": "tinto"}),
        req("S01 Recomendados", "GET", "/api/v1/products", query={"recomendado": "true"}),
        req("S02 Cotizar carrito", "POST", "/api/v1/orders/quote",
            {"items": [{"productoId": "kuyen-tinto", "cantidad": 1}, {"productoId": "cipreses-blanco", "cantidad": 2}],
             "destino": {"comuna": "Providencia", "region": "Metropolitana"}}),
        req("S17 Paquetes de degustación", "GET", "/api/v1/tastings/packages"),
        req("S18 Cupos", "GET", "/api/v1/tastings/availability", query={"fecha": "2026-12-05"}),
        req("S22 Contacto", "POST", "/api/v1/contact", {"nombre": "Pedro", "email": "pedro@correo.cl",
                                                       "asunto": "Pedido especial", "mensaje": "¿Tienen cajas de regalo?"}),
    ]),
    ("2. Cuenta de cliente", [
        req("S03 Registro", "POST", "/api/v1/auth/register",
            {"nombre": "Ana Pérez", "email": "{{emailCliente}}", "password": "{{passwordCliente}}",
             "telefono": "+56 9 5555 1234", "fechaNacimiento": "1998-03-10", "aceptaTerminos": True}),
        req("S04 Login cliente", "POST", "/api/v1/auth/login", {"email": "{{emailCliente}}", "password": "{{passwordCliente}}"}),
        req("S06 Sesión", "GET", "/api/v1/auth/session"),
        req("S07 Mi perfil", "GET", "/api/v1/clients/me"),
        req("S08 Modificar perfil", "PUT", "/api/v1/clients/me",
            {"nombre": "Ana Pérez", "telefono": "+56 9 5555 1234",
             "direccion": {"calle": "Av. Providencia", "numero": "1500", "comuna": "Providencia", "region": "Metropolitana"}}),
    ]),
    ("3. Compra y pago", [
        req("S10 Crear pedido", "POST", "/api/v1/orders",
            {"items": [{"productoId": "kuyen-tinto", "cantidad": 1}], "entrega": ENTREGA},
            [{"key": "Idempotency-Key", "value": "{{$guid}}"}],
            tests=["if (pm.response.code === 201) pm.collectionVariables.set('pedidoId', pm.response.json().id);"]),
        req("S14 Iniciar pago (abrir redirectUrl en el navegador)", "POST", "/api/v1/payments", {"pedidoId": "{{pedidoId}}"},
            tests=["if (pm.response.code === 201) pm.collectionVariables.set('pagoId', pm.response.json().pagoId);"]),
        req("S15 Verificar pago", "POST", "/api/v1/payments/{{pagoId}}/verify"),
        req("S11 GraphQL mis pedidos", "POST", "/api/v1/graphql",
            gql("{ misPedidos(tamano: 5) { total items { numero estado total items { nombre cantidad producto { imagen disponible } } "
                "pago { estado boleta { folio neto iva total } } } } }")),
        req("S12 GraphQL resumen de pedido", "POST", "/api/v1/graphql",
            gql("query($id: ID!) { resumenPedido(id: $id) { numero estado total historial { estado fecha } } }", {"id": "{{pedidoId}}"})),
        req("S13 Anular pedido pendiente", "POST", "/api/v1/orders/{{pedidoId}}/cancel"),
    ]),
    ("4. Degustaciones", [
        req("S19 Reservar", "POST", "/api/v1/tastings/reservations",
            {"paqueteId": "maridaje-gourmet", "fecha": "2026-12-05", "hora": "18:00", "personas": 4,
             "contacto": {"nombre": "Ana Pérez", "email": "{{emailCliente}}", "telefono": "+56955551234"},
             "comentarios": "Uno es vegetariano"}),
        req("S20 Mis reservas", "GET", "/api/v1/tastings/reservations/me"),
    ]),
    ("5. Administración (login admin primero)", [
        req("S04 Login admin", "POST", "/api/v1/auth/login", {"email": "{{emailAdmin}}", "password": "{{passwordAdmin}}"}),
        req("S23 Inventario", "GET", "/api/v1/admin/products"),
        req("S26 Ajustar stock", "PATCH", "/api/v1/admin/products/almaviva-especial/stock", {"delta": 6, "motivo": "INGRESO_BODEGA"}),
        req("S28 Pedidos pagados", "GET", "/api/v1/admin/orders", query={"estado": "PAGADO"}),
        req("S29 Avanzar despacho", "PATCH", "/api/v1/admin/orders/{{pedidoId}}/status", {"estado": "EN_PREPARACION"}),
        req("S30 Reservas", "GET", "/api/v1/admin/tastings/reservations"),
        req("S32 Mensajes", "GET", "/api/v1/admin/contact", query={"estado": "PENDIENTE"}),
        req("S34 Panel de ventas (GraphQL)", "POST", "/api/v1/graphql",
            gql("{ panelVentas(desde: \"2026-11-01\", hasta: \"2026-11-30\") { totalVentas pedidosPagados ticketPromedio "
                "topProductos { nombre unidades } stockBajo { nombre stock } } }")),
        req("S05 Cerrar sesión", "POST", "/api/v1/auth/logout"),
    ]),
]

collection = {
    "info": {"_postman_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "vina-urbana-eval2")), "name": "Viña Urbana — Backend (Evaluación 2)",
             "description": "Cliente HTTP de la API. La sesión queda en la cookie vu_session (Postman la guarda sola). "
                            "Desactiva 'SSL certificate verification' o agrega runtime/certs/ca.crt como CA en Settings.",
             "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
    "variable": [{"key": "baseUrl", "value": "https://localhost:8443"},
                 {"key": "emailCliente", "value": "ana.demo@correo.cl"}, {"key": "passwordCliente", "value": "ClaveSegura2026"},
                 {"key": "emailAdmin", "value": "admin@vinaurbana.cl"},
                 {"key": "passwordAdmin", "value": "<ver runtime/seed-out/seed_credentials.txt>"},
                 {"key": "pedidoId", "value": ""}, {"key": "pagoId", "value": ""}],
    "item": [{"name": n, "item": items} for n, items in folders],
}
(OUT / "VinaUrbana.postman_collection.json").write_text(json.dumps(collection, ensure_ascii=False, indent=2), encoding="utf-8")
print("✓", sum(len(i) for _, i in folders), "solicitudes →", OUT / "VinaUrbana.postman_collection.json")
