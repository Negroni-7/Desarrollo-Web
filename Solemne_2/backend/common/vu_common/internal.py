"""Identidad entre componentes (servicio a servicio).

Cada par (destino, llamador) tiene su propia credencial en Vault:
    secret/internal/<destino>/<llamador>  ->  {"token": "..."}
Así una credencial filtrada sólo sirve para ese tramo y puede revocarse sola.

El llamador envía:
    X-Caller-Id:      nombre del componente que llama
    X-Service-Token:  credencial del tramo
    X-User-Id / X-User-Role: identidad del usuario YA verificada por el gateway.
El servicio destino sólo confía en X-User-* si el llamador es un componente
autorizado para propagar identidad (gateway o graphql).
"""
import logging
import secrets
import time
from dataclasses import dataclass

import httpx
from fastapi import Header, Request

from . import settings
from .errors import ApiError, DependencyError
from .vault import vault

log = logging.getLogger("vu.internal")

IDENTITY_PROPAGATORS = {"gateway", "graphql"}
_last_forced_refresh: dict[str, float] = {}


@dataclass
class CallContext:
    caller: str
    user_id: str | None
    role: str | None
    request_id: str | None

    def require_user(self) -> str:
        if not self.user_id:
            raise ApiError(401, "UNAUTHENTICATED", "Se requiere sesión")
        return self.user_id

    def require_role(self, *roles: str):
        self.require_user()
        if self.role not in roles:
            raise ApiError(403, "FORBIDDEN", "Tu rol no permite esta operación")


def _expected_token(caller: str, force: bool = False) -> str:
    return vault.read(f"internal/{settings.SERVICE_NAME}/{caller}", force=force)["token"]


def verify_caller_token(caller: str, token: str) -> bool:
    if not caller or not token or not caller.replace("-", "").isalnum():
        return False
    expected = _expected_token(caller)
    if secrets.compare_digest(token.encode(), expected.encode()):
        return True
    # Posible rotación: se fuerza una relectura (como máximo 1 vez cada 5 s por llamador).
    now = time.time()
    if now - _last_forced_refresh.get(caller, 0) > 5:
        _last_forced_refresh[caller] = now
        expected = _expected_token(caller, force=True)
        return secrets.compare_digest(token.encode(), expected.encode())
    return False


def require_caller(*allowed: str):
    """Dependencia FastAPI: exige una identidad de servicio permitida para la ruta."""

    def dependency(
        request: Request,
        x_caller_id: str = Header(default=""),
        x_service_token: str = Header(default=""),
        x_user_id: str = Header(default=""),
        x_user_role: str = Header(default=""),
    ) -> CallContext:
        try:
            known = x_caller_id in _known_callers()
            valid = known and verify_caller_token(x_caller_id, x_service_token)
        except KeyError:
            valid = False
        if not valid:
            log.warning("caller_rejected caller=%s path=%s", x_caller_id or "-", request.url.path)
            raise ApiError(401, "INVALID_SERVICE_IDENTITY", "Identidad de servicio inválida")
        if x_caller_id not in allowed:
            log.warning("caller_forbidden caller=%s path=%s", x_caller_id, request.url.path)
            raise ApiError(403, "CALLER_NOT_ALLOWED", "Este componente no puede invocar esta operación")
        trusted = x_caller_id in IDENTITY_PROPAGATORS
        return CallContext(
            caller=x_caller_id,
            user_id=(x_user_id or None) if trusted else None,
            role=(x_user_role or None) if trusted else None,
            request_id=getattr(request.state, "request_id", None),
        )

    return dependency


def _known_callers() -> set[str]:
    # Lista declarativa de tramos permitidos (el detalle por ruta está en cada servicio).
    return {
        "auth": {"gateway", "clients"},
        "clients": {"gateway", "auth"},
        "inventory": {"gateway", "graphql"},
        "orders": {"gateway", "graphql", "payments", "clients"},
        "payments": {"gateway", "graphql"},
        "tastings": {"gateway", "clients"},
        "analytics": {"orders", "tastings", "graphql"},
    }.get(settings.SERVICE_NAME, set())


class ServiceClient:
    """Cliente HTTP hacia otro servicio interno usando la credencial del tramo."""

    def __init__(self, target: str, timeout: float = 4.0):
        self.target = target
        self.base_url = settings.service_url(target)
        self.timeout = timeout

    def _headers(self, ctx: CallContext | None, force: bool = False) -> dict:
        token = vault.read(f"internal/{self.target}/{settings.SERVICE_NAME}", force=force)["token"]
        headers = {"X-Caller-Id": settings.SERVICE_NAME, "X-Service-Token": token}
        if ctx and ctx.request_id:
            headers["X-Request-Id"] = ctx.request_id
        return headers

    def request(self, method: str, path: str, ctx: CallContext | None = None, **kwargs) -> httpx.Response:
        for attempt in (0, 1):
            try:
                resp = httpx.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=self._headers(ctx, force=attempt == 1),
                    verify=settings.verify_param(),
                    timeout=self.timeout,
                    **kwargs,
                )
            except httpx.HTTPError as exc:
                log.warning("dependency_error target=%s err=%s", self.target, type(exc).__name__)
                raise DependencyError(self.target) from exc
            # 401 por identidad: puede ser una rotación reciente; se reintenta 1 vez.
            if resp.status_code == 401 and attempt == 0:
                continue
            return resp
        return resp
