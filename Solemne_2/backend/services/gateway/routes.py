"""Lista EXPLÍCITA de rutas publicadas por el API Gateway (RouteDefinition).

Todo lo que no está aquí responde 404: no existe un reenvío genérico.
Cada ruta indica: servicio (ID del módulo 1), verbo, ruta externa, política
de acceso, roles, sistema destino, ruta interna, parámetros de consulta
permitidos, cabeceras extra permitidas y clase de límite de solicitudes.
"""
import re
from dataclasses import dataclass, field

ANON, AUTH, PROVIDER = "anonimo", "autenticado", "proveedor"


@dataclass
class RouteDefinition:
    sid: str
    method: str
    external: str
    access: str
    target: str
    internal: str
    roles: frozenset = frozenset()
    query: tuple = ()
    headers: tuple = ()
    rate: str = "public"
    timeout: float = 8.0
    max_body: int = 16 * 1024
    regex: re.Pattern = field(init=False, repr=False)

    def __post_init__(self):
        pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[A-Za-z0-9\\-]{1,64})", self.external)
        self.regex = re.compile(f"^{pattern}$")


C, A, S = frozenset({"CLIENTE"}), frozenset({"ADMIN"}), frozenset({"ADMIN", "SOMMELIER"})
ALL_ROLES = frozenset({"CLIENTE", "ADMIN", "SOMMELIER"})

ROUTES = [
    # --- catálogo y carrito (público)
    RouteDefinition("S01", "GET", "/api/v1/products", ANON, "inventory", "/products",
                    query=("tipo", "recomendado", "pagina", "tamano")),
    RouteDefinition("S02", "POST", "/api/v1/orders/quote", ANON, "orders", "/orders/quote"),
    # --- cuenta
    RouteDefinition("S03", "POST", "/api/v1/auth/register", ANON, "auth", "/register", rate="register"),
    RouteDefinition("S04", "POST", "/api/v1/auth/login", ANON, "auth", "/login", rate="login"),
    RouteDefinition("S05", "POST", "/api/v1/auth/logout", AUTH, "auth", "(especial)", roles=ALL_ROLES, rate="user"),
    RouteDefinition("S06", "GET", "/api/v1/auth/session", AUTH, "auth", "/session", roles=ALL_ROLES, rate="user"),
    RouteDefinition("S07", "GET", "/api/v1/clients/me", AUTH, "clients", "/clients/me", roles=C, rate="user"),
    RouteDefinition("S08", "PUT", "/api/v1/clients/me", AUTH, "clients", "/clients/me", roles=C, rate="user"),
    RouteDefinition("S09", "DELETE", "/api/v1/clients/me", AUTH, "clients", "/clients/me", roles=C, rate="user"),
    # --- pedidos y pagos
    RouteDefinition("S10", "POST", "/api/v1/orders", AUTH, "orders", "/orders", roles=C,
                    headers=("idempotency-key",), rate="user"),
    RouteDefinition("S13", "POST", "/api/v1/orders/{id}/cancel", AUTH, "orders", "/orders/{id}/cancel", roles=C, rate="user"),
    RouteDefinition("S14", "POST", "/api/v1/payments", AUTH, "payments", "/payments", roles=C, rate="user", timeout=12.0),
    RouteDefinition("S15", "POST", "/api/v1/payments/{id}/verify", AUTH, "payments", "/payments/{id}/verify", roles=C,
                    rate="user", timeout=12.0),
    RouteDefinition("S16", "POST", "/api/v1/payments/webhook", PROVIDER, "payments", "/payments/webhook",
                    headers=("x-provider-timestamp", "x-provider-signature"), rate="webhook"),
    # --- degustaciones
    RouteDefinition("S17", "GET", "/api/v1/tastings/packages", ANON, "tastings", "/tastings/packages"),
    RouteDefinition("S18", "GET", "/api/v1/tastings/availability", ANON, "tastings", "/tastings/availability", query=("fecha",)),
    RouteDefinition("S19", "POST", "/api/v1/tastings/reservations", AUTH, "tastings", "/tastings/reservations", roles=C, rate="user"),
    RouteDefinition("S20", "GET", "/api/v1/tastings/reservations/me", AUTH, "tastings", "/tastings/reservations/me", roles=C, rate="user"),
    RouteDefinition("S21", "POST", "/api/v1/tastings/reservations/{id}/cancel", AUTH, "tastings",
                    "/tastings/reservations/{id}/cancel", roles=C, rate="user"),
    # --- contacto (mensajería)
    RouteDefinition("S22", "POST", "/api/v1/contact", ANON, "clients", "/contact", rate="contact"),
    # --- administración
    RouteDefinition("S23", "GET", "/api/v1/admin/products", AUTH, "inventory", "/admin/products", roles=A, rate="user"),
    RouteDefinition("S24", "POST", "/api/v1/admin/products", AUTH, "inventory", "/admin/products", roles=A, rate="user"),
    RouteDefinition("S25", "PUT", "/api/v1/admin/products/{id}", AUTH, "inventory", "/admin/products/{id}", roles=A, rate="user"),
    RouteDefinition("S26", "PATCH", "/api/v1/admin/products/{id}/stock", AUTH, "inventory", "/admin/products/{id}/stock",
                    roles=A, rate="user"),
    RouteDefinition("S27", "DELETE", "/api/v1/admin/products/{id}", AUTH, "inventory", "/admin/products/{id}", roles=A, rate="user"),
    RouteDefinition("S28", "GET", "/api/v1/admin/orders", AUTH, "orders", "/admin/orders", roles=A,
                    query=("estado", "pagina", "tamano"), rate="user"),
    RouteDefinition("S29", "PATCH", "/api/v1/admin/orders/{id}/status", AUTH, "orders", "/admin/orders/{id}/status",
                    roles=A, rate="user"),
    RouteDefinition("S30", "GET", "/api/v1/admin/tastings/reservations", AUTH, "tastings", "/admin/tastings/reservations",
                    roles=S, query=("fecha",), rate="user"),
    RouteDefinition("S31", "PATCH", "/api/v1/admin/tastings/reservations/{id}/status", AUTH, "tastings",
                    "/admin/tastings/reservations/{id}/status", roles=S, rate="user"),
    RouteDefinition("S32", "GET", "/api/v1/admin/contact", AUTH, "clients", "/admin/contact", roles=A,
                    query=("estado", "pagina", "tamano"), rate="user"),
    RouteDefinition("S33", "PATCH", "/api/v1/admin/contact/{id}", AUTH, "clients", "/admin/contact/{id}", roles=A, rate="user"),
    # --- agregaciones (S11, S12, S34): cada operación GraphQL se autoriza dentro del GraphQL Gateway
    RouteDefinition("G01", "POST", "/api/v1/graphql", AUTH, "graphql", "/graphql", roles=ALL_ROLES, rate="graphql",
                    timeout=10.0, max_body=8 * 1024),
]

# Límites por ventana de 60 s: (cantidad, clave = ip | usuario)
RATE_LIMITS = {
    "public": (120, "ip"), "login": (20, "ip"), "register": (10, "ip"), "contact": (5, "ip"),
    "webhook": (60, "ip"), "user": (120, "user"), "graphql": (60, "user"),
}


def match(method: str, path: str):
    """Devuelve (ruta, parámetros) o (None, métodos_permitidos_para_esa_ruta)."""
    allowed = []
    for r in ROUTES:
        m = r.regex.match(path)
        if m:
            if r.method == method:
                return r, m.groupdict()
            allowed.append(r.method)
    return None, allowed
