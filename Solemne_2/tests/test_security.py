"""Casos de validación de seguridad del módulo 7 (V1-V6) y controles del gateway.

V1 acceso anónimo a catálogo                → test_V1_*
V2 operación protegida sin sesión válida     → test_V2_*
V3 administración desde un rol sin permiso   → test_V3_*
V4 consulta de un pedido ajeno               → test_V4_*
V5 acceso directo al backend sin identidad   → test_V5_*
V6 confirmar pago con datos alterados        → test_V6_*
"""
import os
import uuid
from pathlib import Path

import grpc
import httpx
import pytest

from conftest import (ADMIN, API, CA, CERTS_DIR, CLIENT, CREDS, H, INTERNAL, INVENTORY_GRPC, ROOT, create_order, gql,
                      login, new_client, register_and_login)


# ------------------------------------------------------------------ V1
def test_V1_catalogo_anonimo_permitido(anon):
    assert anon.get("/products").status_code == 200
    assert anon.get("/tastings/packages").status_code == 200


# ------------------------------------------------------------------ V2
@pytest.mark.parametrize("method,path", [
    ("POST", "/orders"), ("GET", "/clients/me"), ("POST", "/payments"), ("GET", "/auth/session"),
    ("POST", "/graphql"), ("GET", "/tastings/reservations/me"), ("GET", "/admin/products"),
])
def test_V2_operacion_protegida_sin_sesion_401(anon, method, path):
    r = anon.request(method, path, json={} if method == "POST" else None)
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHENTICATED"


def test_V2_token_falso_o_alterado_401():
    c = new_client()
    r = c.get("/clients/me", headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.firma-falsa"})
    assert r.status_code == 401


def test_V2_logout_revoca_la_sesion():
    c = login(CLIENT)
    cookie = c.cookies.get("vu_session")
    assert c.post("/auth/logout").status_code == 200
    replay = new_client()
    r = replay.get("/clients/me", headers={"Authorization": f"Bearer {cookie}"})
    assert r.status_code == 401  # el token robado ya no sirve


# ------------------------------------------------------------------ V3
@pytest.mark.parametrize("method,path,body", [
    ("GET", "/admin/products", None),
    ("POST", "/admin/products", {"id": "hack-vino", "nombre": "x", "tipo": "tinto", "vina": "x", "volumenMl": 750,
                                 "gradoAlcohol": 13, "precio": 1000, "imagen": "images/vinos/x.jpg", "stock": 1}),
    ("DELETE", "/admin/products/kuyen-tinto", None),
    ("GET", "/admin/orders", None),
    ("GET", "/admin/contact", None),
])
def test_V3_cliente_no_administra(client_a, method, path, body):
    r = client_a.request(method, path, json=body)
    assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN"


def test_V3_cabeceras_de_identidad_falsas_se_descartan(client_a):
    r = client_a.get("/admin/products", headers={"X-User-Role": "ADMIN", "X-User-Id": "admin",
                                                 "X-Caller-Id": "gateway", "X-Service-Token": "x"})
    assert r.status_code == 403


def test_V3_sommelier_solo_reservas(sommelier):
    assert sommelier.get("/admin/products").status_code == 403
    assert sommelier.get("/admin/orders").status_code == 403
    assert sommelier.get("/admin/tastings/reservations").status_code == 200


def test_V3_panel_ventas_solo_admin(client_a, admin):
    q = '{ panelVentas(desde:"2026-01-01", hasta:"2026-12-31") { totalVentas } }'
    r = gql(client_a, q).json()
    assert r["data"] is None and r["errors"][0]["extensions"]["code"] == "FORBIDDEN"
    assert gql(admin, q).json()["data"]["panelVentas"]["totalVentas"] >= 0


# ------------------------------------------------------------------ V4
@pytest.fixture(scope="module")
def order_of_a(client_a):
    r = create_order(client_a, [{"productoId": "pinot-rosado", "cantidad": 1}])
    assert r.status_code == 201
    return r.json()


def test_V4_dueno_consulta_su_pedido(client_a, order_of_a):
    r = gql(client_a, "query($id: ID!){ resumenPedido(id:$id){ id total entrega{ calle } } }", {"id": order_of_a["id"]})
    assert r.json()["data"]["resumenPedido"]["id"] == order_of_a["id"]


def test_V4_otro_cliente_no_ve_el_pedido(client_b, order_of_a):
    r = gql(client_b, "query($id: ID!){ resumenPedido(id:$id){ id total entrega{ calle } } }", {"id": order_of_a["id"]})
    body = r.json()
    assert body["data"]["resumenPedido"] is None and "Camila" not in r.text and "Providencia" not in r.text


def test_V4_otro_cliente_no_anula_ni_paga(client_b, order_of_a):
    assert client_b.post(f"/orders/{order_of_a['id']}/cancel").status_code == 404
    assert client_b.post("/payments", json={"pedidoId": order_of_a["id"]}).status_code == 404


def test_V4_mis_pedidos_solo_propios(client_b, order_of_a):
    items = gql(client_b, "{ misPedidos { items { id } } }").json()["data"]["misPedidos"]["items"]
    assert order_of_a["id"] not in [o["id"] for o in items]


def test_V4_campo_restringido_por_rol(client_a):
    r = gql(client_a, "{ misPedidos(tamano:1) { items { id clienteId } } }").json()
    assert r["errors"][0]["extensions"]["code"] == "FORBIDDEN_FIELD"
    assert all(o["clienteId"] is None for o in r["data"]["misPedidos"]["items"])


# ------------------------------------------------------------------ V5
@pytest.mark.parametrize("svc,method,path", [
    ("inventory", "GET", "/products"), ("orders", "GET", "/internal/orders"), ("auth", "POST", "/internal/introspect"),
    ("payments", "POST", "/payments/webhook"), ("graphql", "POST", "/graphql"), ("clients", "GET", "/admin/contact"),
])
def test_V5_acceso_directo_sin_identidad_de_servicio(svc, method, path):
    r = httpx.request(method, INTERNAL[svc] + path, verify=CA, json={"token": "x" * 20, "query": "{__typename}"},
                      headers={"X-User-Id": "x", "X-User-Role": "ADMIN"}, timeout=5)
    assert r.status_code == 401
    assert "INVALID_SERVICE_IDENTITY" in r.text


def test_V5_identidad_de_servicio_falsa():
    r = httpx.get(INTERNAL["inventory"] + "/admin/products", verify=CA, timeout=5,
                  headers={"X-Caller-Id": "gateway", "X-Service-Token": "adivinado", "X-User-Role": "ADMIN", "X-User-Id": "x"})
    assert r.status_code == 401


def _grpc_quote(cert_dir: Path | None):
    import sys
    sys.path.insert(0, str(ROOT / "backend" / "services" / "orders"))
    import inventory_pb2 as pb
    import inventory_pb2_grpc as pbg
    ca = Path(CA).read_bytes()
    if cert_dir:
        creds = grpc.ssl_channel_credentials(ca, (cert_dir / "tls.key").read_bytes(), (cert_dir / "tls.crt").read_bytes())
    else:
        creds = grpc.ssl_channel_credentials(ca)
    stub = pbg.InventoryReservationsStub(grpc.secure_channel(INVENTORY_GRPC, creds))
    return stub.QuoteItems(pb.QuoteRequest(items=[pb.ItemQuantity(product_id="kuyen-tinto", quantity=1)]), timeout=3)


def test_V5_grpc_sin_certificado_de_cliente_rechazado():
    with pytest.raises(grpc.RpcError) as err:
        _grpc_quote(None)
    assert err.value.code() == grpc.StatusCode.UNAVAILABLE  # el handshake mTLS falla


def test_V5_grpc_con_certificado_de_otro_componente_denegado():
    with pytest.raises(grpc.RpcError) as err:
        _grpc_quote(CERTS_DIR / "payments")
    assert err.value.code() == grpc.StatusCode.PERMISSION_DENIED


def test_V5_grpc_identidad_orders_permitida():
    assert _grpc_quote(CERTS_DIR / "orders").items[0].unit_price == 32000


# ------------------------------------------------------------------ V6
def test_V6_precio_o_total_del_navegador_se_rechaza(client_a):
    r = client_a.post("/orders", headers={"Idempotency-Key": str(uuid.uuid4())}, json={
        "items": [{"productoId": "almaviva-especial", "cantidad": 1}], "total": 1,
        "entrega": {"nombreReceptor": "X X", "calle": "Calle", "numero": "1", "comuna": "Providencia",
                    "region": "Metropolitana", "telefono": "+56911112222"}})
    assert r.status_code == 400


def test_V6_monto_de_pago_del_navegador_se_rechaza(client_a, order_of_a):
    r = client_a.post("/payments", json={"pedidoId": order_of_a["id"], "monto": 1})
    assert r.status_code == 400


def test_V6_webhook_sin_firma_valida_rechazado(anon, client_a, order_of_a):
    pay = client_a.post("/payments", json={"pedidoId": order_of_a["id"]}).json()
    token = pay["redirectUrl"].rsplit("/", 1)[1]
    forged = {"event_id": uuid.uuid4().hex, "token": token, "status": "AUTHORIZED", "amount": pay["monto"]}
    r = anon.post("/payments/webhook", json=forged, headers={"X-Provider-Signature": "sha256=" + "0" * 64,
                                                             "X-Provider-Timestamp": "1"})
    assert r.status_code == 401
    # El navegador tampoco puede "verificar" un pago que el proveedor no aprobó.
    v = client_a.post(f"/payments/{pay['pagoId']}/verify").json()
    assert v["estado"] == "INICIADO"
    estado = gql(client_a, "query($id: ID!){ resumenPedido(id:$id){ estado } }", {"id": order_of_a["id"]})
    assert estado.json()["data"]["resumenPedido"]["estado"] == "PENDIENTE_PAGO"


# ------------------------------------------------------------------ controles del gateway
def test_csrf_sin_cabecera_propia_rechazado(client_a):
    c = httpx.Client(base_url=API, verify=CA, cookies=client_a.cookies)
    r = c.post("/orders/quote", json={"items": [{"productoId": "kuyen-tinto", "cantidad": 1}]})
    assert r.status_code == 403 and r.json()["error"]["code"] == "CSRF_CHECK_FAILED"


def test_cookie_de_sesion_httponly_secure_samesite():
    c = new_client()
    r = c.post("/auth/login", json={"email": CLIENT, "password": CREDS[CLIENT]})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=strict" in cookie
    assert "accessToken" not in r.text  # el token no llega al JavaScript


def test_login_errores_no_revelan_si_existe_la_cuenta(anon):
    a = anon.post("/auth/login", json={"email": CLIENT, "password": "incorrecta1"})
    b = anon.post("/auth/login", json={"email": "nadie@correo.cl", "password": "incorrecta1"})
    assert a.status_code == b.status_code == 401 and a.json()["error"]["message"] == b.json()["error"]["message"]


def test_registro_menor_de_edad_y_password_debil(anon):
    base = {"nombre": "Menor Prueba", "email": f"m{uuid.uuid4().hex[:6]}@correo.cl", "password": "ClaveSegura123",
            "fechaNacimiento": "2012-01-01", "aceptaTerminos": True}
    r = anon.post("/auth/register", json=base)
    assert r.status_code == 422 and r.json()["error"]["code"] == "UNDERAGE"
    r = anon.post("/auth/register", json={**base, "fechaNacimiento": "1990-01-01", "password": "solo-letras"})
    assert r.status_code == 400


def test_registro_correo_duplicado(anon):
    r = anon.post("/auth/register", json={"nombre": "Dup", "email": CLIENT, "password": "ClaveSegura123",
                                          "fechaNacimiento": "1990-01-01", "aceptaTerminos": True})
    assert r.status_code == 409


def test_contrasenas_guardadas_con_argon2id():
    env = {k: v for k, v in (l.split("=", 1) for l in (ROOT / ".env").read_text().splitlines() if "=" in l)} \
        if (ROOT / ".env").exists() else {}
    if not env:
        pytest.skip("sin credenciales raíz de Mongo en este entorno")
    from pymongo import MongoClient
    db = MongoClient(f"mongodb://{env['MONGO_ROOT_USER']}:{env['MONGO_ROOT_PASSWORD']}@127.0.0.1:27017/?authSource=admin",
                     tls=True, tlsCAFile=CA)["vu_auth"]
    hashes = [c["passwordHash"] for c in db.credentials.find({"estado": "ACTIVO"}, {"passwordHash": 1})]
    assert hashes and all(h.startswith("$argon2id$") for h in hashes)
    # analytics no guarda datos personales
    ev = MongoClient(f"mongodb://{env['MONGO_ROOT_USER']}:{env['MONGO_ROOT_PASSWORD']}@127.0.0.1:27017/?authSource=admin",
                     tls=True, tlsCAFile=CA)["vu_analytics"].events.find_one()
    if ev:
        assert not {"clienteId", "email", "entrega", "contacto"} & set(ev["datos"])


def test_servicio_no_lee_base_de_otro_servicio():
    """Cada usuario de Mongo sólo tiene readWrite sobre su base (propiedad de datos)."""
    env = {k: v for k, v in (l.split("=", 1) for l in (ROOT / ".env").read_text().splitlines() if "=" in l)} \
        if (ROOT / ".env").exists() else {}
    if not env:
        pytest.skip("sin acceso a Vault/Mongo en este entorno")
    from pymongo import MongoClient
    from pymongo.errors import OperationFailure
    vault = httpx.get("https://127.0.0.1:8200/v1/secret/data/db/inventory", verify=CA,
                      headers={"X-Vault-Token": env["VAULT_ROOT_TOKEN"]}).json()["data"]["data"]
    inv = MongoClient(vault["uri"], tls=True, tlsCAFile=CA)
    assert inv["vu_inventory"].products.count_documents({}) > 0
    with pytest.raises(OperationFailure):
        inv["vu_auth"].credentials.find_one()


def test_cuerpo_demasiado_grande_413(anon):
    r = anon.post("/contact", content=b'{"x":"' + b"a" * 20000 + b'"}', headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_limite_de_solicitudes_contacto_429():
    c = new_client()
    codes = [c.post("/contact", json={"nombre": "Spam Bot", "email": "spam@correo.cl", "asunto": "Otro",
                                      "mensaje": f"mensaje {i}"}).status_code for i in range(7)]
    assert 429 in codes and codes.count(201) <= 5  # nunca más de 5 por minuto por IP


def test_vault_politica_minimo_privilegio():
    """El token de inventory no puede leer la llave JWT de auth ni la base de otro servicio."""
    token_file = ROOT / "runtime" / "tokens" / "inventory" / "vault-token"
    if not token_file.exists():
        pytest.skip("tokens no disponibles en este entorno")
    t = token_file.read_text().strip()
    ok = httpx.get("https://127.0.0.1:8200/v1/secret/data/db/inventory", verify=CA, headers={"X-Vault-Token": t})
    denied1 = httpx.get("https://127.0.0.1:8200/v1/secret/data/auth/jwt", verify=CA, headers={"X-Vault-Token": t})
    denied2 = httpx.get("https://127.0.0.1:8200/v1/secret/data/db/auth", verify=CA, headers={"X-Vault-Token": t})
    assert ok.status_code == 200 and denied1.status_code == 403 and denied2.status_code == 403


@pytest.mark.skipif(not (ROOT / "runtime" / "logs").exists(), reason="logs locales no disponibles")
def test_logs_sin_secretos_ni_datos_personales():
    """Los logs de los servicios propios no contienen contraseñas, tokens ni correos completos.
    (Se excluyen vault.log y mongo.log: son de la infraestructura; el modo dev de Vault imprime
    su token raíz, limitación documentada.)"""
    import re
    secrets_to_find = list(CREDS.values()) + [CLIENT, ADMIN]
    services = ["gateway", "auth", "clients", "inventory", "orders", "payments", "tastings", "analytics", "graphql", "sandbox"]
    for name in services:
        text = (ROOT / "runtime" / "logs" / f"{name}.log").read_text(errors="ignore")
        assert not any(s in text for s in secrets_to_find), name
        assert not re.search(r"eyJ[A-Za-z0-9_-]{10,}\.", text), name  # JWT
        assert "requestId" in text or "request_id" in text, name  # correlación presente
