"""API Gateway de Viña Urbana: único punto de entrada público.

Responsabilidades (lo que valida el gateway):
  - Publicar sólo las rutas declaradas en routes.py (lista explícita).
  - Autenticar: token de sesión (cookie HttpOnly o Bearer) validado contra
    Auth Service por introspección (detecta sesiones revocadas).
  - Autorizar por ruta y rol (primera barrera, no la única).
  - Descartar cabeceras de identidad interna que envíe el navegador y
    propagar sólo identidad verificada (X-User-Id / X-User-Role).
  - Presentar a cada servicio la credencial propia del tramo (Vault).
  - Límites de solicitudes, tamaño de cuerpo, tiempos de espera, protección
    CSRF, cabeceras de seguridad y errores controlados.
  - Por indicación del docente la entrega es sólo backend: el gateway no sirve
    el frontend; expone la API que el frontend (v1.0) consumiría.
Lo que valida cada servicio: identidad del llamador, rol de nuevo, propiedad
del recurso, reglas de negocio y transiciones de estado.
"""
import logging
import os
import time
from collections import defaultdict, deque

import anyio
import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, Response

from routes import AUTH, PROVIDER, RATE_LIMITS, match
from vu_common import settings
from vu_common.server import create_app, serve
from vu_common.vault import SecretUnavailable, vault

log = logging.getLogger("vu.gateway")
# En el borde no se confía en X-Request-Id externo: el gateway genera el identificador.
app = create_app("Viña Urbana - API Gateway", trust_request_id=False)

COOKIE = "vu_session"
SECURE_COOKIE = settings.TLS_ENABLED
TARGETS = {name: settings.service_url(name) for name in
           ("auth", "clients", "inventory", "orders", "payments", "tastings", "graphql")}
STRIPPED = {"x-user-id", "x-user-role", "x-caller-id", "x-service-token", "x-forwarded-for", "x-real-ip"}

_http = httpx.AsyncClient(verify=settings.verify_param(), timeout=8.0,
                          limits=httpx.Limits(max_connections=200, max_keepalive_connections=50))
_windows: dict[str, deque] = defaultdict(deque)


def error(status: int, code: str, message: str, request: Request, headers: dict | None = None):
    return JSONResponse(status_code=status, headers=headers,
                        content={"error": {"code": code, "message": message, "requestId": request.state.request_id}})


async def secret(path: str, force: bool = False) -> dict:
    return await anyio.to_thread.run_sync(vault.read, path, force)


# Sólo para pruebas de carga controladas desde una única IP (ver tests/load_test.py). Por defecto 1.
RATE_MULTIPLIER = max(1, int(os.getenv("RATE_LIMIT_MULTIPLIER", "1")))


def rate_limited(rate: str, request: Request, user: str | None) -> bool:
    limit, scope = RATE_LIMITS[rate]
    limit *= RATE_MULTIPLIER
    who = user if scope == "user" and user else (request.client.host if request.client else "?")
    key = f"{rate}:{who}"
    now = time.monotonic()
    window = _windows[key]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= limit:
        return True
    window.append(now)
    return False


async def service_headers(target: str, request: Request, identity: dict | None, force: bool = False) -> dict:
    token = (await secret(f"internal/{target}/gateway", force))["token"]
    headers = {"X-Caller-Id": "gateway", "X-Service-Token": token, "X-Request-Id": request.state.request_id}
    if identity:
        headers["X-User-Id"] = identity["sub"]
        headers["X-User-Role"] = identity["role"]
    return headers


async def introspect(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE)
    auth_header = request.headers.get("authorization", "")
    if not token and auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    if not token or len(token) > 4096:
        return None
    resp = await _http.post(f"{TARGETS['auth']}/internal/introspect", json={"token": token},
                            headers=await service_headers("auth", request, None), timeout=3.0)
    if resp.status_code != 200:
        raise httpx.HTTPError("introspect failed")
    data = resp.json()
    return data if data.get("active") else None


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # La API sólo entrega JSON: no se permite cargar ningún recurso desde sus respuestas.
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if SECURE_COOKIE:
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def gateway(request: Request, rest: str):
    route, params = match(request.method, request.url.path)
    if route is None:
        if params:
            return error(405, "METHOD_NOT_ALLOWED", "Verbo no permitido en esta ruta", request,
                         headers={"Allow": ", ".join(sorted(set(params)))})
        return error(404, "NOT_FOUND", "Ruta no publicada", request)

    # --- CSRF: toda operación que cambia estado desde el navegador debe traer una cabecera propia
    # que un sitio ajeno no puede añadir sin CORS (y este gateway no habilita CORS).
    if request.method != "GET" and route.access != PROVIDER:
        if request.headers.get("x-requested-with") != "XMLHttpRequest":
            return error(403, "CSRF_CHECK_FAILED", "Solicitud rechazada", request)

    # --- tamaño de cuerpo
    body = await request.body()
    if len(body) > route.max_body:
        return error(413, "PAYLOAD_TOO_LARGE", "Cuerpo demasiado grande", request)
    if body and request.method in ("POST", "PUT", "PATCH") and "application/json" not in request.headers.get("content-type", ""):
        return error(415, "UNSUPPORTED_MEDIA_TYPE", "Se espera application/json", request)

    # --- autenticación
    identity = None
    try:
        if route.access == AUTH:
            identity = await introspect(request)
            if not identity:
                resp = error(401, "UNAUTHENTICATED", "Debes iniciar sesión", request)
                resp.delete_cookie(COOKIE, path="/api")
                return resp
            if identity["role"] not in route.roles:
                log.warning("route_forbidden sid=%s role=%s", route.sid, identity["role"])
                return error(403, "FORBIDDEN", "Tu rol no permite esta operación", request)
    except (httpx.HTTPError, SecretUnavailable):
        return error(503, "AUTH_UNAVAILABLE", "Autenticación no disponible, intenta más tarde", request)

    if rate_limited(route.rate, request, identity["sub"] if identity else None):
        return error(429, "RATE_LIMITED", "Demasiadas solicitudes, espera un momento", request, headers={"Retry-After": "60"})

    if route.sid == "S05":
        return await logout(request, identity)

    # --- construcción de la llamada interna (sólo datos permitidos)
    internal_path = route.internal.format(**params)
    query = {k: v for k, v in request.query_params.items() if k in route.query}
    try:
        headers = await service_headers(route.target, request, identity)
    except SecretUnavailable:
        return error(503, "SECRETS_UNAVAILABLE", "Servicio temporalmente no disponible", request)
    for h in route.headers:
        if h in request.headers and h not in STRIPPED:
            headers[h] = request.headers[h]
    if body:
        headers["Content-Type"] = "application/json"
    try:
        upstream = await _http.request(request.method, f"{TARGETS[route.target]}{internal_path}", params=query,
                                       content=body, headers=headers, timeout=route.timeout)
        if upstream.status_code == 401 and b"INVALID_SERVICE_IDENTITY" in upstream.content:
            # La credencial del tramo pudo rotar: se relee desde Vault y se reintenta una vez.
            headers.update(await service_headers(route.target, request, identity, force=True))
            upstream = await _http.request(request.method, f"{TARGETS[route.target]}{internal_path}", params=query,
                                           content=body, headers=headers, timeout=route.timeout)
    except httpx.TimeoutException:
        return error(504, "UPSTREAM_TIMEOUT", "El servicio tardó demasiado en responder", request)
    except httpx.HTTPError:
        return error(503, "DEPENDENCY_UNAVAILABLE", "Servicio no disponible, intenta más tarde", request)

    if route.sid == "S04" and upstream.status_code == 200:
        return login_response(request, upstream)
    response = Response(content=upstream.content, status_code=upstream.status_code,
                        media_type=upstream.headers.get("content-type", "application/json"))
    if route.sid == "S09" and upstream.status_code == 200:
        response.delete_cookie(COOKIE, path="/api")
    return response


def login_response(request: Request, upstream: httpx.Response) -> Response:
    """El token de sesión sólo viaja en una cookie HttpOnly: JavaScript no puede leerlo."""
    data = upstream.json()
    resp = JSONResponse(status_code=200, content={"user": data["user"], "expiresIn": data["expiresIn"]})
    resp.set_cookie(COOKIE, data["accessToken"], max_age=data["expiresIn"], httponly=True, secure=SECURE_COOKIE,
                    samesite="strict", path="/api")
    return resp


async def logout(request: Request, identity: dict) -> Response:
    try:
        await _http.post(f"{TARGETS['auth']}/internal/sessions/{identity['jti']}/revoke",
                         headers=await service_headers("auth", request, identity), timeout=3.0)
    except httpx.HTTPError:
        return error(503, "AUTH_UNAVAILABLE", "No fue posible cerrar la sesión", request)
    resp = JSONResponse({"sesionCerrada": True})
    resp.delete_cookie(COOKIE, path="/api")
    return resp


@app.get("/")
def index(request: Request):
    """Punto de entrada informativo (público, sin datos). También es la URL de retorno del
    proveedor de pagos: el cliente recibe ?pago=<id> y debe llamar a POST /api/v1/payments/{id}/verify."""
    pago = request.query_params.get("pago")
    body = {"servicio": "Viña Urbana API", "version": "2.0", "base": "/api/v1",
            "documentacion": "docs/Informe_Evaluacion2_VinaUrbana.pdf (módulos 1 y 6)"}
    if pago and pago.replace("-", "").isalnum() and len(pago) <= 64:
        body["retornoPago"] = {"pagoId": pago, "siguientePaso": f"POST /api/v1/payments/{pago}/verify"}
    return body


if __name__ == "__main__":
    serve(app)
