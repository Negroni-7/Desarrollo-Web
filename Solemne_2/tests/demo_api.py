"""Demostración de los flujos principales VÍA API (sin frontend).

Ejecuta, contra el sistema levantado, los flujos del caso a través del API
Gateway, igual que lo haría el frontend, y guarda cada solicitud y respuesta en
docs/evidencias/demo_api/flujos.md (evidencia trazable de requisito, servicio y
resultado). Las cookies y tokens se omiten del registro.

Uso:  python tests/demo_api.py
"""
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from conftest import API, CA, CREDS, GATEWAY, H, INTERNAL, SANDBOX, next_weekday  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "evidencias" / "demo_api"
OUT.mkdir(parents=True, exist_ok=True)
DATOS = json.loads((ROOT / "scripts" / "datos_frontend.json").read_text(encoding="utf-8"))

md: list[str] = []
resumen: list[dict] = []
paso = 0


def short(obj, limit=900):
    text = json.dumps(obj, ensure_ascii=False, indent=1) if not isinstance(obj, str) else obj
    return text if len(text) <= limit else text[:limit] + "\n… (recortado)"


def call(titulo, req, sid, client, method, path, esperado, body=None, headers=None, base=API, params=None):
    global paso
    paso += 1
    r = client.request(method, base + path, json=body, headers=headers, params=params)
    try:
        data = r.json()
    except ValueError:
        data = r.text
    ok = r.status_code == esperado
    shown_headers = {k: v for k, v in (headers or {}).items() if k.lower() not in ("authorization", "cookie")}
    md.append(f"### {paso}. {titulo}\n")
    md.append(f"- Requisito: **{req}** · Servicio: **{sid}** · Esperado: **{esperado}** · Obtenido: **{r.status_code}** "
              f"→ {'✅' if ok else '❌'}\n")
    shown_path = "/api/v1" + path if base == API else (path if base == GATEWAY else base + path)
    md.append(f"```http\n{method} {shown_path}{'?' + str(httpx.QueryParams(params)) if params else ''}\n"
              + "".join(f"{k}: {v}\n" for k, v in shown_headers.items())
              + (f"\n{short(body, 500)}\n" if body is not None else "") + "```\n")
    md.append(f"```json\n{short(data)}\n```\n")
    resumen.append({"paso": paso, "titulo": titulo, "requisito": req, "servicio": sid, "esperado": esperado,
                    "obtenido": r.status_code, "ok": ok})
    print(f"{'OK ' if ok else 'ERR'} {paso:2d} {sid:8s} {r.status_code} {titulo}")
    return data


def seccion(t):
    md.append(f"\n## {t}\n")


def main():
    anon = httpx.Client(verify=CA, timeout=20, headers=H)
    ana = httpx.Client(verify=CA, timeout=20, headers=H)
    otro = httpx.Client(verify=CA, timeout=20, headers=H)
    admin = httpx.Client(verify=CA, timeout=20, headers=H)
    somm = httpx.Client(verify=CA, timeout=20, headers=H)

    md.append("# Evidencia de ejecución vía API — Viña Urbana\n")
    md.append(f"Generado por `tests/demo_api.py` el {datetime.now():%d-%m-%Y %H:%M}. Todas las llamadas pasan por el API "
              f"Gateway ({GATEWAY}). La entrega es sólo backend: se usan los datos del frontend v1.0 "
              "(`scripts/datos_frontend.json`) como datos y contratos; las cookies de sesión no se muestran.\n")

    seccion("1. Catálogo con los datos del frontend")
    call("Raíz informativa del gateway", "—", "—", anon, "GET", "/", 200, base=GATEWAY)
    cat = call("Catálogo completo (9 vinos del frontend)", "R02", "S01", anon, "GET", "/products", 200)
    assert {v["id"] for v in DATOS["vinos"]} <= {p["id"] for p in cat["items"]}
    call("Filtro Tintos (botón del frontend)", "R02", "S01", anon, "GET", "/products", 200, params={"tipo": "tinto"})
    call("Recomendados (carrusel del frontend)", "R03", "S01", anon, "GET", "/products", 200, params={"recomendado": "true"})
    call("Filtro inválido", "R02", "S01", anon, "GET", "/products", 400, params={"tipo": "cerveza"})

    seccion("2. Carrito y despacho (precios del servidor)")
    call("Cotizar carrito: 1 Kuyen + 2 Cipreses a Providencia", "R04 R05", "S02", anon, "POST", "/orders/quote", 200,
         {"items": [{"productoId": "kuyen-tinto", "cantidad": 1}, {"productoId": "cipreses-blanco", "cantidad": 2}],
          "destino": {"comuna": "Providencia", "region": "Metropolitana"}})
    call("Cotizar a regiones (tarifa $6.990)", "R05", "S02", anon, "POST", "/orders/quote", 200,
         {"items": [{"productoId": "pinot-rosado", "cantidad": 1}], "destino": {"comuna": "Viña del Mar", "region": "Valparaíso"}})

    seccion("3. Registro e inicio de sesión (formulario Mi Cuenta)")
    email = f"ana.{uuid.uuid4().hex[:6]}@correo.cl"
    reg = {"nombre": "Ana Pérez", "email": email, "password": "ClaveSegura2026", "telefono": "+56 9 5555 1234",
           "fechaNacimiento": "1998-03-10", "aceptaTerminos": True}
    call("Registro de cliente", "R07", "S03", anon, "POST", "/auth/register", 201, reg)
    call("Registro de menor de edad (rechazado)", "R01", "S03", anon, "POST", "/auth/register", 422,
         {**reg, "email": "menor." + email, "fechaNacimiento": "2012-06-01"})
    call("Login con contraseña incorrecta", "R07", "S04", anon, "POST", "/auth/login", 401, {"email": email, "password": "otra123x"})
    call("Login correcto (sesión en cookie HttpOnly)", "R07", "S04", ana, "POST", "/auth/login", 200,
         {"email": email, "password": reg["password"]})
    call("Consultar sesión", "R07", "S06", ana, "GET", "/auth/session", 200)
    call("Guardar dirección en el perfil", "R07", "S08", ana, "PUT", "/clients/me", 200,
         {"nombre": "Ana Pérez", "telefono": "+56 9 5555 1234",
          "direccion": {"calle": "Av. Providencia", "numero": "1500", "comuna": "Providencia", "region": "Metropolitana"}})

    seccion("4. Compra, pago y boleta")
    entrega = {"nombreReceptor": "Ana Pérez", "calle": "Av. Providencia", "numero": "1500", "comuna": "Providencia",
               "region": "Metropolitana", "telefono": "+56955551234"}
    items = [{"productoId": "kuyen-tinto", "cantidad": 1}, {"productoId": "cipreses-blanco", "cantidad": 2}]
    call("Pedido con total alterado por el cliente (rechazado)", "R06", "S10", ana, "POST", "/orders", 400,
         {"items": items, "entrega": entrega, "total": 1}, {"Idempotency-Key": str(uuid.uuid4())})
    key = str(uuid.uuid4())
    pedido = call("Crear pedido (stock reservado por gRPC)", "R04 R05", "S10", ana, "POST", "/orders", 201,
                  {"items": items, "entrega": entrega}, {"Idempotency-Key": key})
    call("Reintento con la misma Idempotency-Key (mismo pedido)", "R06", "S10", ana, "POST", "/orders", 200,
         {"items": items, "entrega": entrega}, {"Idempotency-Key": key})
    pago = call("Iniciar pago (monto lo fija orders)", "R06", "S14", ana, "POST", "/payments", 201, {"pedidoId": pedido["id"]})
    token = pago["redirectUrl"].rsplit("/", 1)[1]
    r = httpx.post(f"{SANDBOX}/pay/{token}/decision", data={"decision": "approve"}, verify=CA, follow_redirects=False)
    paso_txt = f"Comprador aprueba en la página del proveedor → redirección a {r.headers.get('location')}"
    md.append(f"> {paso_txt}\n")
    call("Verificar pago con el proveedor (boleta emitida)", "R06 R12", "S15", ana, "POST", f"/payments/{pago['pagoId']}/verify", 200)
    call("Reenvío de la misma notificación del proveedor (sin efectos dobles)", "R06", "S16", anon, "POST",
         f"/sandbox/transactions/{token}/resend-webhook", 200, base=SANDBOX)
    call("Intentar pagar de nuevo el mismo pedido", "R06", "S14", ana, "POST", "/payments", 409, {"pedidoId": pedido["id"]})

    seccion("5. Agregación GraphQL (orders + inventory + payments)")
    q = ("{ misPedidos(tamano: 3) { total items { numero estado total despacho items { nombre cantidad "
         "producto { imagen disponible } } pago { estado boleta { folio neto iva total } } } } }")
    call("Mis pedidos (una consulta, tres subsistemas)", "R12", "S11", ana, "POST", "/graphql", 200, {"query": q})
    call("Campo restringido clienteId para un cliente", "R12", "S11", ana, "POST", "/graphql", 200,
         {"query": "{ misPedidos(tamano:1) { items { numero clienteId } } }"})
    otro_email = f"otro.{uuid.uuid4().hex[:6]}@correo.cl"
    call("Registro de un segundo cliente", "R07", "S03", anon, "POST", "/auth/register", 201, {**reg, "email": otro_email})
    call("Login segundo cliente", "R07", "S04", otro, "POST", "/auth/login", 200, {"email": otro_email, "password": reg["password"]})
    call("Otro cliente consulta el pedido de Ana (null, sin datos)", "R12", "S12", otro, "POST", "/graphql", 200,
         {"query": "query($id: ID!){ resumenPedido(id:$id){ numero total entrega { calle } } }", "variables": {"id": pedido["id"]}})
    call("Otro cliente intenta anular el pedido de Ana", "R12", "S13", otro, "POST", f"/orders/{pedido['id']}/cancel", 404)
    call("Acceso directo a orders sin identidad de servicio", "—", "interno", anon, "GET", "/internal/orders", 401,
         base=INTERNAL["orders"], headers={"X-User-Id": "x", "X-User-Role": "ADMIN"})
    call("Ruta interna por el gateway (no publicada)", "—", "gateway", anon, "GET", "/internal/orders", 404)

    seccion("6. Degustaciones (formulario de reserva)")
    call("Paquetes del frontend", "R08", "S17", anon, "GET", "/tastings/packages", 200)
    fecha = next_weekday(7)
    call("Cupos por horario", "R08", "S18", anon, "GET", "/tastings/availability", 200, params={"fecha": fecha})
    call("Reservar Maridaje Gourmet para 4", "R08", "S19", ana, "POST", "/tastings/reservations", 201,
         {"paqueteId": "maridaje-gourmet", "fecha": fecha, "hora": "18:00", "personas": 4,
          "contacto": {"nombre": "Ana Pérez", "email": email, "telefono": "+56955551234"},
          "comentarios": "Uno de los asistentes es vegetariano"})
    call("Mis reservas", "R08", "S20", ana, "GET", "/tastings/reservations/me", 200)

    seccion("7. Contacto")
    call("Mensaje del formulario de contacto", "R09", "S22", anon, "POST", "/contact", 201,
         {"nombre": "Pedro Prueba", "email": "pedro@correo.cl", "asunto": "Pedido especial",
          "mensaje": "¿Tienen cajas de regalo para 6 botellas?"})

    seccion("8. Administración, despacho y reportes")
    call("Login administrador", "R11", "S04", admin, "POST", "/auth/login", 200,
         {"email": "admin@vinaurbana.cl", "password": CREDS["admin@vinaurbana.cl"]})
    call("Cliente intenta administrar productos (denegado)", "R11", "S23", ana, "GET", "/admin/products", 403)
    call("Inventario con stock", "R11", "S23", admin, "GET", "/admin/products", 200)
    call("Ingreso de bodega +6 Almaviva", "R11", "S26", admin, "PATCH", "/admin/products/almaviva-especial/stock", 200,
         {"delta": 6, "motivo": "INGRESO_BODEGA"})
    call("Pedidos pagados", "R11", "S28", admin, "GET", "/admin/orders", 200, params={"estado": "PAGADO", "tamano": 2})
    for est in ("EN_PREPARACION", "DESPACHADO", "ENTREGADO"):
        call(f"Despacho → {est}", "R11 R12", "S29", admin, "PATCH", f"/admin/orders/{pedido['id']}/status", 200, {"estado": est})
    call("Transición inválida (ENTREGADO → EN_PREPARACION)", "R11", "S29", admin, "PATCH",
         f"/admin/orders/{pedido['id']}/status", 409, {"estado": "EN_PREPARACION"})
    call("Mensajes de contacto pendientes", "R09", "S32", admin, "GET", "/admin/contact", 200, params={"estado": "PENDIENTE", "tamano": 2})
    time.sleep(3)  # outbox → analytics (retraso aceptado)
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    call("Panel de ventas GraphQL (analytics + inventory)", "R13", "S34", admin, "POST", "/graphql", 200,
         {"query": "query($d:String!){ panelVentas(desde:$d, hasta:$d){ totalVentas pedidosPagados ticketPromedio "
                   "topProductos{ nombre unidades } reservasPorPaquete{ paquete personas } stockBajo{ nombre stock } } }",
          "variables": {"d": hoy}})
    call("Login sommelier", "R08", "S04", somm, "POST", "/auth/login", 200,
         {"email": "sommelier@vinaurbana.cl", "password": CREDS["sommelier@vinaurbana.cl"]})
    call("Sommelier ve reservas con comentarios", "R08", "S30", somm, "GET", "/admin/tastings/reservations", 200,
         params={"fecha": fecha})
    call("Sommelier intenta ver pedidos (denegado)", "R11", "S28", somm, "GET", "/admin/orders", 403)

    seccion("9. Cierre de sesión")
    call("Cerrar sesión", "R07", "S05", ana, "POST", "/auth/logout", 200)
    call("Operación tras cerrar sesión", "R07", "S07", ana, "GET", "/clients/me", 401)

    total, ok = len(resumen), sum(r["ok"] for r in resumen)
    head = [f"\n## Resumen\n", f"**{ok} de {total} pasos con el resultado esperado.**\n",
            "| # | Paso | Requisito | Servicio | Esperado | Obtenido | |\n|---|---|---|---|---|---|---|\n"]
    head += [f"| {r['paso']} | {r['titulo']} | {r['requisito']} | {r['servicio']} | {r['esperado']} | {r['obtenido']} | "
             f"{'✅' if r['ok'] else '❌'} |\n" for r in resumen]
    (OUT / "flujos.md").write_text("".join(md[:2]) + "".join(head) + "\n" + "\n".join(md[2:]), encoding="utf-8")
    (OUT / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{ok}/{total} pasos OK → {OUT / 'flujos.md'}")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
