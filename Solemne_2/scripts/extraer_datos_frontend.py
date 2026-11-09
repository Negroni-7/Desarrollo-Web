"""Extrae los DATOS del frontend v1.0 (Entrega_Frontend/index.html) y genera
scripts/datos_frontend.json, que es la fuente de los datos iniciales del backend.

La entrega es sólo backend (indicación del docente): el frontend no se modifica
ni se integra; se usan sus datos (vinos, precios, paquetes, opciones de los
formularios) para poblar la base y definir los contratos.

Uso:  python scripts/extraer_datos_frontend.py [ruta/a/index.html]
"""
import json
import re
import sys
import unicodedata
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "Entrega_Frontend" / "index.html"
OUT = Path(__file__).resolve().parent / "datos_frontend.json"

# Datos que el frontend NO tiene y que define el backend (se declaran explícitamente).
STOCK_INICIAL = {"kuyen-tinto": 24, "pinot-rosado": 30, "purafe-tinto": 36, "chardonay-rosado": 30, "cipreses-blanco": 20,
                 "riesling-blanco": 18, "almaviva-especial": 6, "chadwick-especial": 4, "clos-especial": 5}
ID_PAQUETES = ["iniciacion-cata", "maridaje-gourmet", "edicion-limitada"]


def text(fragment: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def section(html: str, sid: str) -> str:
    m = re.search(rf'<section id="{sid}".*?</section>', html, re.S)
    if not m:
        raise SystemExit(f"No se encontró la sección #{sid}")
    return m.group(0)


def precio(s: str) -> int:
    return int(re.sub(r"[^\d]", "", s))


def minutos(s: str) -> int:
    m = re.search(r"([\d,\.]+)\s*hora", s)
    return int(round(float(m.group(1).replace(",", ".")) * 60))


def main():
    html = SRC.read_text(encoding="utf-8")

    # ---- catálogo (tarjetas del #catalogo)
    vinos = []
    for card in re.findall(r'<div class="col-lg-4 col-md-6 wine-card" data-tipo="(\w+)">(.*?)</button>', section(html, "catalogo"), re.S):
        tipo, body = card
        nombre = text(re.search(r'<h5 class="card-title">(.*?)</h5>', body, re.S).group(1))
        detalle = text(re.search(r'<p class="card-text text-muted">(.*?)</p>', body, re.S).group(1))
        vina, vol, grado = [x.strip() for x in detalle.split(" - ")]
        imagen = re.search(r'data-imagen="([^"]+)"', body).group(1)
        pid = Path(imagen).stem
        vinos.append({
            "id": pid, "nombre": nombre, "tipo": tipo, "vina": vina,
            "volumenMl": int(re.sub(r"\D", "", vol)), "gradoAlcohol": float(grado.replace("%", "").replace(",", ".")),
            "precio": int(re.search(r'data-precio="(\d+)"', body).group(1)), "imagen": imagen,
        })

    # ---- recomendados (#recomendados): se marcan por nombre
    recomendados = {text(t) for t in re.findall(r'<h5 class="card-title">(.*?)</h5>', section(html, "recomendados"), re.S)}
    for v in vinos:
        v["recomendado"] = v["nombre"] in recomendados
        v["stockInicial"] = STOCK_INICIAL[v["id"]]

    # ---- degustaciones (#degustaciones)
    deg = section(html, "degustaciones")
    paquetes = []
    for i, card in enumerate(re.findall(r'<div class="card h-100 text-center degustacion-card">(.*?)</button>', deg, re.S)):
        incluye = [text(li) for li in re.findall(r"<li[^>]*>(.*?)</li>", card, re.S)]
        paquetes.append({
            "id": ID_PAQUETES[i], "nombre": text(re.search(r'<h4 class="card-title">(.*?)</h4>', card, re.S).group(1)),
            "descripcion": text(re.search(r'<p class="text-muted mb-3">(.*?)</p>', card, re.S).group(1)),
            "incluye": [x.rstrip(".") for x in incluye],
            "duracionMin": minutos(next(x for x in incluye if "Duración" in x)),
            "precioPorPersona": precio(re.search(r'<p class="fw-bold fs-3[^>]*>(.*?)</p>', card, re.S).group(1)),
            "imagen": re.search(r'<img src="([^"]+)"', card).group(1),
        })

    # ---- opciones de formularios (definen enumeraciones de los contratos)
    form = re.search(r'id="formulario-reserva".*?</form>', deg, re.S).group(0)
    selects = re.findall(r"<select[^>]*>(.*?)</select>", form, re.S)
    opciones = lambda sel: [text(o) for o in re.findall(r"<option[^>]*>(.*?)</option>", sel, re.S) if text(o) != "Seleccionar..."]
    horas = opciones(selects[1])
    personas = opciones(selects[2])
    contacto = section(html, "contacto")
    asuntos = opciones(re.search(r"<select[^>]*>(.*?)</select>", contacto, re.S).group(1))

    # ---- reglas publicadas en "Información Importante"
    info = text(re.search(r"Información Importante</h2>(.*?)</section>", html, re.S).group(1))
    reglas = {
        "envioGratisDesde": precio(re.search(r"sobre \$([\d\.]+)", info).group(1)),
        "comunaEnvioGratis": re.search(r"\$[\d\.]+ en (\w+)", info).group(1),
        "diasEntrega": re.search(r"(\d+-\d+) días hábiles", info).group(1),
        "edadMinima": int(re.search(r"mayores de (\d+)", info).group(1)),
        "mediosDePago": re.search(r"Aceptamos ([^,]+, [^ ]+ y \w+)", info).group(1),
    }
    nombres_formulario = {
        "registro": ["Nombre", "Teléfono", "Email", "Contraseña"],
        "login": ["Email", "Contraseña"],
        "reserva": ["Nombre completo", "Email", "Teléfono", "Paquete", "Fecha preferida", "Hora preferida",
                    "Cantidad de personas", "Comentarios adicionales"],
        "contacto": ["Nombre", "Email", "Asunto", "Mensaje"],
    }

    data = {
        "_origen": "Extraído automáticamente de Entrega_Frontend/index.html (frontend v1.0) por scripts/extraer_datos_frontend.py",
        "_nota": "stockInicial no existe en el frontend: lo define el backend. 'recomendado' sale del carrusel #recomendados.",
        "vinos": vinos, "paquetes": paquetes,
        "formularios": {"horasReserva": horas, "personasReserva": personas, "asuntosContacto": asuntos,
                        "campos": nombres_formulario},
        "reglas": reglas,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {len(vinos)} vinos, {len(paquetes)} paquetes, {len(horas)} horarios, {len(asuntos)} asuntos → {OUT.name}")


if __name__ == "__main__":
    main()
