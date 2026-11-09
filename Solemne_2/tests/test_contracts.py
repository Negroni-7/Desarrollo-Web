"""Pruebas de contrato REST (módulo 1): forma de las respuestas, códigos y errores."""
from conftest import API, CA, GATEWAY, H, next_weekday
import httpx


def test_S01_catalogo_solo_campos_publicos(anon):
    r = anon.get("/products")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 9 and {"items", "total", "pagina", "tamano"} <= body.keys()
    allowed = {"id", "nombre", "tipo", "vina", "volumenMl", "gradoAlcohol", "precio", "imagen", "recomendado", "disponible"}
    for p in body["items"]:
        assert set(p) == allowed  # no expone stock exacto ni auditoría


def test_S01_filtro_por_tipo_y_validacion(anon):
    r = anon.get("/products", params={"tipo": "tinto"})
    assert r.status_code == 200 and all(p["tipo"] == "tinto" for p in r.json()["items"])
    bad = anon.get("/products", params={"tipo": "cerveza"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "VALIDATION_ERROR"


def test_S01_parametros_no_declarados_se_descartan(anon):
    # El gateway sólo reenvía tipo, recomendado, pagina y tamano.
    r = anon.get("/products", params={"activo": "false", "$where": "1"})
    assert r.status_code == 200


def test_S02_cotizacion_calculada_por_servidor(anon):
    r = anon.post("/orders/quote", json={"items": [{"productoId": "kuyen-tinto", "cantidad": 2}],
                                         "destino": {"comuna": "Providencia", "region": "Metropolitana"}})
    assert r.status_code == 200
    q = r.json()
    assert q["items"][0]["precioUnitario"] == 32000 and q["subtotal"] == 64000
    assert q["despacho"] == 0  # regla: gratis sobre $50.000 en Providencia


def test_S02_tarifas_de_despacho(anon):
    item = [{"productoId": "pinot-rosado", "cantidad": 1}]
    rm = anon.post("/orders/quote", json={"items": item, "destino": {"comuna": "Ñuñoa", "region": "Metropolitana"}}).json()
    reg = anon.post("/orders/quote", json={"items": item, "destino": {"comuna": "Viña del Mar", "region": "Valparaíso"}}).json()
    prov = anon.post("/orders/quote", json={"items": item, "destino": {"comuna": "Providencia", "region": "Metropolitana"}}).json()
    assert rm["despacho"] == 3990 and reg["despacho"] == 6990 and prov["despacho"] == 3990  # < $50.000


def test_S02_producto_inexistente_se_informa(anon):
    r = anon.post("/orders/quote", json={"items": [{"productoId": "no-existe", "cantidad": 1}]})
    assert r.status_code == 200 and r.json()["noDisponibles"] == ["no-existe"]


def test_S17_S18_paquetes_y_disponibilidad(anon):
    p = anon.get("/tastings/packages")
    assert p.status_code == 200 and len(p.json()["items"]) == 3
    a = anon.get("/tastings/availability", params={"fecha": next_weekday(5)})
    assert a.status_code == 200 and [h["hora"] for h in a.json()["horarios"]] == ["10:00", "12:00", "16:00", "18:00", "20:00"]


def test_S18_domingo_cerrado(anon):
    from datetime import date, timedelta
    d = date.today() + timedelta(days=1)
    while d.weekday() != 6:
        d += timedelta(days=1)
    r = anon.get("/tastings/availability", params={"fecha": d.isoformat()})
    assert r.status_code == 422 and r.json()["error"]["code"] == "CLOSED_DAY"


def test_ruta_no_publicada_404_y_verbo_405(anon):
    r = anon.get("/internal/orders")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
    r = anon.delete("/products")
    assert r.status_code == 405 and "GET" in r.headers["allow"]


def test_formato_de_error_controlado(anon):
    r = anon.post("/orders/quote", json={"items": []})
    err = r.json()["error"]
    assert r.status_code == 400 and err["requestId"] and "Traceback" not in r.text


def test_raiz_informativa_y_cabeceras_de_seguridad():
    r = httpx.get(GATEWAY + "/", verify=CA, params={"pago": "abc-123"})
    assert r.status_code == 200 and r.json()["base"] == "/api/v1"
    assert r.json()["retornoPago"]["siguientePaso"] == "POST /api/v1/payments/abc-123/verify"
    for h in ("content-security-policy", "x-content-type-options", "strict-transport-security", "x-frame-options"):
        assert h in r.headers
    assert r.headers["content-security-policy"].startswith("default-src 'none'")
    assert httpx.get(GATEWAY + "/index.html", verify=CA).status_code == 404  # no se sirve frontend
    api = httpx.get(API + "/products", verify=CA)
    assert api.headers["cache-control"] == "no-store" and api.headers["x-request-id"]
