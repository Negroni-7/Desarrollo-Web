"""Pruebas del GraphQL Gateway privado (módulo 8): agregación, autorización y límites."""
import httpx

from conftest import CA, INTERNAL, create_order, gql


def test_G01_agregacion_tres_subsistemas(client_a):
    create_order(client_a, [{"productoId": "clos-especial", "cantidad": 1}])
    r = gql(client_a, """{ misPedidos(tamano: 5) { total items {
        numero estado total items { nombre producto { id imagen disponible precioActual } } pago { estado } } } }""")
    body = r.json()
    assert r.status_code == 200 and "errors" not in body
    page = body["data"]["misPedidos"]
    assert page["total"] >= 1
    item = page["items"][0]["items"][0]
    assert item["producto"]["imagen"].startswith("images/")  # dato que viene de inventory


def test_G02_profundidad_y_ciclos_de_fragmentos(client_a):
    deep = "{ misPedidos { items { items { producto { id } } } } }"  # profundidad máxima real del schema
    assert "errors" not in gql(client_a, deep).json()
    # Ciclo de fragmentos (vector clásico de denegación de servicio) → rechazado al validar.
    q = """{ misPedidos { items { ...A } } }
           fragment A on ResumenPedido { id ...B }
           fragment B on ResumenPedido { numero ...A }"""
    r = gql(client_a, q)
    assert r.status_code == 400 and "errors" in r.json()


def test_G03_limite_de_costo_con_alias(client_a):
    sel = "items { numero items { nombre producto { id nombre tipo imagen } } pago { estado boleta { folio } } }"
    q = "{ " + " ".join(f"a{i}: misPedidos(tamano: 10) {{ {sel} }}" for i in range(5)) + " }"
    r = gql(client_a, q)
    assert r.status_code == 400 and "costosa" in r.text


def test_G04_paginacion_acotada(client_a):
    r = gql(client_a, "{ misPedidos(tamano: 500) { total } }").json()
    assert r["errors"][0]["extensions"]["code"] == "BAD_USER_INPUT"


def test_G05_introspeccion_deshabilitada(client_a):
    r = gql(client_a, "{ __schema { types { name } } }")
    assert r.status_code == 400 and "introspection" in r.text.lower()


def test_G06_batching_de_operaciones_deshabilitado(client_a):
    r = client_a.post("/graphql", json=[{"query": "{ misPedidos { total } }"}, {"query": "{ misPedidos { total } }"}])
    assert r.status_code == 400


def test_G07_graphql_privado_no_accesible_directamente():
    r = httpx.post(INTERNAL["graphql"] + "/graphql", json={"query": "{ misPedidos { total } }"}, verify=CA,
                   headers={"X-User-Id": "x", "X-User-Role": "ADMIN"})
    assert r.status_code == 401


def test_G08_pedido_inexistente_devuelve_null(client_a):
    r = gql(client_a, '{ resumenPedido(id: "no-existe-123") { id } }').json()
    assert r["data"]["resumenPedido"] is None
