"""Trazabilidad con los DATOS del frontend v1.0 (la entrega es sólo backend).

Comprueba que lo que expone la API coincide con lo que muestra el frontend:
vinos, precios, recomendados, paquetes, horarios, asuntos y reglas publicadas.
"""
import json
from pathlib import Path

import pytest

from conftest import ROOT, next_weekday

DATOS = json.loads((ROOT / "scripts" / "datos_frontend.json").read_text(encoding="utf-8"))
CAMPOS_PUBLICOS = ("id", "nombre", "tipo", "vina", "volumenMl", "gradoAlcohol", "precio", "imagen", "recomendado")


def test_D01_catalogo_igual_al_frontend(anon):
    api = {p["id"]: p for p in anon.get("/products").json()["items"]}
    assert len(DATOS["vinos"]) == 9
    for v in DATOS["vinos"]:
        assert v["id"] in api, v["id"]
        assert {k: api[v["id"]][k] for k in CAMPOS_PUBLICOS} == {k: v[k] for k in CAMPOS_PUBLICOS}


@pytest.mark.parametrize("tipo", ["tinto", "blanco", "rosado", "especial"])
def test_D02_filtros_del_frontend(anon, tipo):
    esperados = {v["id"] for v in DATOS["vinos"] if v["tipo"] == tipo}
    assert esperados <= {p["id"] for p in anon.get("/products", params={"tipo": tipo}).json()["items"]}


def test_D03_recomendados_del_carrusel(anon):
    esperados = {v["id"] for v in DATOS["vinos"] if v["recomendado"]}
    assert esperados <= {p["id"] for p in anon.get("/products", params={"recomendado": "true"}).json()["items"]}


def test_D04_paquetes_de_degustacion(anon):
    api = {p["id"]: p for p in anon.get("/tastings/packages").json()["items"]}
    for p in DATOS["paquetes"]:
        assert api[p["id"]]["nombre"] == p["nombre"] and api[p["id"]]["precioPorPersona"] == p["precioPorPersona"]
        assert api[p["id"]]["incluye"] == p["incluye"] and api[p["id"]]["duracionMin"] == p["duracionMin"]


def test_D05_horarios_del_formulario_de_reserva(anon):
    horas = [h["hora"] for h in anon.get("/tastings/availability", params={"fecha": next_weekday(6)}).json()["horarios"]]
    assert horas == DATOS["formularios"]["horasReserva"]


def test_D06_asuntos_del_formulario_de_contacto(anon):
    for asunto in DATOS["formularios"]["asuntosContacto"][:3]:  # el límite es 5/min por IP
        r = anon.post("/contact", json={"nombre": "Prueba Datos", "email": "datos@correo.cl", "asunto": asunto,
                                        "mensaje": "Mensaje de prueba de contrato"})
        assert r.status_code == 201, asunto


def test_D07_regla_de_despacho_publicada(anon):
    reglas = DATOS["reglas"]
    caro = next(v for v in DATOS["vinos"] if v["precio"] >= reglas["envioGratisDesde"])
    q = anon.post("/orders/quote", json={"items": [{"productoId": caro["id"], "cantidad": 1}],
                                         "destino": {"comuna": reglas["comunaEnvioGratis"], "region": "Metropolitana"}}).json()
    assert q["despacho"] == 0 and q["envioGratisDesde"] == reglas["envioGratisDesde"]
