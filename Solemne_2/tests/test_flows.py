"""Pruebas de integración de flujos y reglas críticas de negocio (módulos 3 y 10)."""
import concurrent.futures as cf
import time
import uuid

import httpx

from conftest import (CA, SANDBOX, create_order, gql, login, new_client, next_weekday, provider_decide,
                      register_and_login, stock_of)

Q_PEDIDO = """query($id: ID!){ resumenPedido(id:$id){ estado total items{ nombre producto{ disponible } }
             pago{ estado boleta{ folio neto iva total } } } }"""


def _pagar(client, order_id, decision="approve"):
    pay = client.post("/payments", json={"pedidoId": order_id})
    assert pay.status_code == 201, pay.text
    pay = pay.json()
    token = provider_decide(pay["redirectUrl"], decision)
    verify = client.post(f"/payments/{pay['pagoId']}/verify")
    assert verify.status_code == 200
    return pay, token, verify.json()


def test_F01_compra_completa_pago_boleta_y_stock(client_a, admin):
    before = stock_of(admin, "riesling-blanco")
    order = create_order(client_a, [{"productoId": "riesling-blanco", "cantidad": 2}])
    assert order.status_code == 201
    o = order.json()
    assert o["estado"] == "PENDIENTE_PAGO" and o["total"] == 55000 + 0  # Providencia y > $50.000
    assert stock_of(admin, "riesling-blanco") == before - 2  # stock reservado
    _, _, result = _pagar(client_a, o["id"])
    assert result["estado"] == "APROBADO"
    b = result["boleta"]
    assert b["total"] == 55000 and b["neto"] + b["iva"] == 55000 and b["neto"] == round(55000 / 1.19)
    resumen = gql(client_a, Q_PEDIDO, {"id": o["id"]}).json()["data"]["resumenPedido"]
    assert resumen["estado"] == "PAGADO" and resumen["pago"]["boleta"]["folio"] == b["folio"]


def test_F02_creacion_idempotente(client_a, admin):
    key = str(uuid.uuid4())
    before = stock_of(admin, "purafe-tinto")
    a = create_order(client_a, [{"productoId": "purafe-tinto", "cantidad": 1}], key)
    b = create_order(client_a, [{"productoId": "purafe-tinto", "cantidad": 1}], key)
    assert a.status_code == 201 and b.status_code == 200 and a.json()["id"] == b.json()["id"]
    assert stock_of(admin, "purafe-tinto") == before - 1
    client_a.post(f"/orders/{a.json()['id']}/cancel")


def test_F03_notificacion_duplicada_no_duplica_efectos(client_a, admin):
    o = create_order(client_a, [{"productoId": "cipreses-blanco", "cantidad": 1}]).json()
    pay, token, result = _pagar(client_a, o["id"])
    stock_after = stock_of(admin, "cipreses-blanco")
    # El proveedor reenvía exactamente la misma notificación firmada (mismo event_id).
    r = httpx.post(f"{SANDBOX}/sandbox/transactions/{token}/resend-webhook", verify=CA)
    assert r.status_code == 200 and r.json()["merchantStatus"] == 200
    again = client_a.post(f"/payments/{pay['pagoId']}/verify").json()
    assert again["estado"] == "APROBADO" and again["boleta"]["folio"] == result["boleta"]["folio"]
    assert stock_of(admin, "cipreses-blanco") == stock_after


def test_F04_segundo_pago_del_mismo_pedido_rechazado(client_a):
    o = create_order(client_a, [{"productoId": "pinot-rosado", "cantidad": 1}]).json()
    _pagar(client_a, o["id"])
    r = client_a.post("/payments", json={"pedidoId": o["id"]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "ORDER_NOT_PAYABLE"


def test_F05_pago_rechazado_permite_reintentar(client_a):
    o = create_order(client_a, [{"productoId": "pinot-rosado", "cantidad": 1}]).json()
    _, _, rejected = _pagar(client_a, o["id"], "reject")
    assert rejected["estado"] == "RECHAZADO" and rejected["boleta"] is None
    assert gql(client_a, Q_PEDIDO, {"id": o["id"]}).json()["data"]["resumenPedido"]["estado"] == "PENDIENTE_PAGO"
    _, _, ok = _pagar(client_a, o["id"])
    assert ok["estado"] == "APROBADO"


def test_F06_anulacion_recupera_stock(client_a, admin):
    before = stock_of(admin, "kuyen-tinto")
    o = create_order(client_a, [{"productoId": "kuyen-tinto", "cantidad": 3}]).json()
    assert stock_of(admin, "kuyen-tinto") == before - 3
    r = client_a.post(f"/orders/{o['id']}/cancel")
    assert r.status_code == 200 and r.json()["estado"] == "CANCELADO"
    assert stock_of(admin, "kuyen-tinto") == before
    again = client_a.post(f"/orders/{o['id']}/cancel")
    assert again.status_code == 409  # anular no borra: queda en el historial


def test_F07_stock_insuficiente_y_concurrencia(admin):
    pid = f"prueba-{uuid.uuid4().hex[:6]}"
    r = admin.post("/admin/products", json={"id": pid, "nombre": "Vino Prueba Concurrencia", "tipo": "tinto", "vina": "Test",
                                            "volumenMl": 750, "gradoAlcohol": 13, "precio": 10000,
                                            "imagen": "images/vinos/kuyen-tinto.jpg", "stock": 3})
    assert r.status_code == 201
    buyers = [login("cliente.demo@correo.cl") for _ in range(1)][0]
    too_many = create_order(buyers, [{"productoId": pid, "cantidad": 4}])
    assert too_many.status_code == 409 and too_many.json()["error"]["code"] == "PRODUCTS_UNAVAILABLE"
    with cf.ThreadPoolExecutor(8) as ex:
        results = list(ex.map(lambda _: create_order(buyers, [{"productoId": pid, "cantidad": 1}]).status_code, range(8)))
    assert results.count(201) == 3 and results.count(409) == 5  # nunca se vende más de lo que hay
    assert stock_of(admin, pid) == 0
    assert admin.delete(f"/admin/products/{pid}").status_code == 200  # eliminación lógica


def test_F08_transiciones_de_despacho(client_a, admin):
    o = create_order(client_a, [{"productoId": "pinot-rosado", "cantidad": 1}]).json()
    _pagar(client_a, o["id"])
    bad = admin.patch(f"/admin/orders/{o['id']}/status", json={"estado": "ENTREGADO"})
    assert bad.status_code == 409 and bad.json()["error"]["code"] == "INVALID_TRANSITION"
    for estado in ("EN_PREPARACION", "DESPACHADO", "ENTREGADO"):
        r = admin.patch(f"/admin/orders/{o['id']}/status", json={"estado": estado})
        assert r.status_code == 200 and r.json()["estado"] == estado
    hist = [h["estado"] for h in r.json()["historial"]]
    assert hist == ["PENDIENTE_PAGO", "PAGADO", "EN_PREPARACION", "DESPACHADO", "ENTREGADO"]


def _free_slot(anon_client, start_days=30):
    for days in range(start_days, start_days + 50):
        fecha = next_weekday(days)
        for h in anon_client.get("/tastings/availability", params={"fecha": fecha}).json()["horarios"]:
            if h["cuposDisponibles"] == 12:
                return fecha, h["hora"]
    raise AssertionError("sin sesiones libres")


def test_F09_reservas_capacidad_y_cancelacion(anon, client_a, client_b, sommelier):
    fecha, hora = _free_slot(anon)
    base = {"paqueteId": "iniciacion-cata", "fecha": fecha, "hora": hora,
            "contacto": {"nombre": "Camila Demo", "email": "cliente.demo@correo.cl", "telefono": "+56911112222"},
            "comentarios": "Alergia a frutos secos"}
    a = client_a.post("/tastings/reservations", json={**base, "personas": 10})
    assert a.status_code == 201 and a.json()["total"] == 150000
    full = client_b.post("/tastings/reservations", json={**base, "personas": 3})
    assert full.status_code == 409 and full.json()["error"]["code"] == "NO_CAPACITY"
    assert client_b.post(f"/tastings/reservations/{a.json()['id']}/cancel").status_code == 404  # no es suya
    assert client_a.post(f"/tastings/reservations/{a.json()['id']}/cancel").status_code == 200
    b = client_b.post("/tastings/reservations", json={**base, "personas": 3})
    assert b.status_code == 201  # cupo recuperado
    staff = sommelier.get("/admin/tastings/reservations", params={"fecha": fecha}).json()["items"]
    assert any(x["comentarios"] == "Alergia a frutos secos" for x in staff)
    r = sommelier.patch(f"/admin/tastings/reservations/{b.json()['id']}/status", json={"estado": "ASISTIDA"})
    assert r.status_code == 200


def test_F10_precio_de_reserva_lo_fija_el_servidor(client_a):
    r = client_a.post("/tastings/reservations", json={
        "paqueteId": "edicion-limitada", "fecha": next_weekday(41), "hora": "20:00", "personas": 2, "total": 1,
        "contacto": {"nombre": "Camila", "email": "c@correo.cl", "telefono": "+56911112222"}})
    assert r.status_code == 400  # campo 'total' no permitido


def test_F11_perfil_contacto_y_baja_de_cuenta(admin):
    c, data = register_and_login("baja")
    put = c.put("/clients/me", json={"nombre": "Nombre Nuevo", "telefono": "+56 9 8888 7777",
                                     "direccion": {"calle": "Los Leones", "numero": "100", "comuna": "Providencia",
                                                   "region": "Metropolitana"}})
    assert put.status_code == 200 and put.json()["direccion"]["comuna"] == "Providencia"
    o = create_order(c, [{"productoId": "pinot-rosado", "cantidad": 1}]).json()
    blocked = c.delete("/clients/me")
    assert blocked.status_code == 409  # pedido en curso
    c.post(f"/orders/{o['id']}/cancel")
    assert c.delete("/clients/me").status_code == 200
    relog = new_client().post("/auth/login", json={"email": data["email"], "password": data["password"]})
    assert relog.status_code == 401


def test_F12_mensaje_de_contacto_gestionado_por_admin(anon, admin):
    msg = anon.post("/contact", json={"nombre": "Ana Consulta", "email": "ana@correo.cl", "asunto": "Consulta sobre vinos",
                                      "mensaje": "¿Tienen Carmenere orgánico?"})
    assert msg.status_code == 201
    pend = admin.get("/admin/contact", params={"estado": "PENDIENTE"}).json()["items"]
    assert any(m["id"] == msg.json()["id"] for m in pend)
    assert admin.patch(f"/admin/contact/{msg.json()['id']}", json={"estado": "ATENDIDO"}).status_code == 200


def test_F13_analitica_recibe_ventas_sin_datos_personales(client_a, admin):
    q = 'query($d:String!){ panelVentas(desde:$d, hasta:$d){ totalVentas pedidosPagados topProductos{ productoId } stockBajo{ id } } }'
    hoy = time.strftime("%Y-%m-%d", time.gmtime())
    time.sleep(3)  # deja que el outbox entregue eventos de pruebas anteriores
    before = gql(admin, q, {"d": hoy}).json()["data"]["panelVentas"]
    o = create_order(client_a, [{"productoId": "chardonay-rosado", "cantidad": 1}]).json()
    _pagar(client_a, o["id"])
    for _ in range(20):  # retraso aceptado: el outbox entrega cada 2 s
        after = gql(admin, q, {"d": hoy}).json()["data"]["panelVentas"]
        if after["pedidosPagados"] >= before["pedidosPagados"] + 1:
            break
        time.sleep(0.5)
    assert after["pedidosPagados"] == before["pedidosPagados"] + 1
    assert after["totalVentas"] == before["totalVentas"] + o["total"]
    assert isinstance(after["stockBajo"], list)  # segundo subsistema agregado (inventory)


def test_F14_vencimiento_de_pago_recupera_stock_y_pago_tardio_se_revierte(client_a, admin):
    """Requiere el perfil de pruebas (plazo de pago = 25 s)."""
    before = stock_of(admin, "almaviva-especial")
    o = create_order(client_a, [{"productoId": "almaviva-especial", "cantidad": 1}]).json()
    vence = o["venceEn"]
    pay = client_a.post("/payments", json={"pedidoId": o["id"]}).json()
    import datetime as dt
    wait = (dt.datetime.fromisoformat(vence) - dt.datetime.now(dt.timezone.utc)).total_seconds()
    if wait > 60:
        import pytest
        pytest.skip("el plazo de pago configurado es largo (usa --test-profile)")
    time.sleep(max(0, wait) + 5)
    estado = gql(client_a, Q_PEDIDO, {"id": o["id"]}).json()["data"]["resumenPedido"]["estado"]
    assert estado == "CANCELADO" and stock_of(admin, "almaviva-especial") == before
    provider_decide(pay["redirectUrl"], "approve")  # el comprador paga tarde
    late = client_a.post(f"/payments/{pay['pagoId']}/verify").json()
    assert late["estado"] == "REQUIERE_REVERSA" and late["boleta"] is None
    assert stock_of(admin, "almaviva-especial") == before
