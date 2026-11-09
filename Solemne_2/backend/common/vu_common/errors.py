"""Errores controlados: nunca se devuelven trazas ni datos internos."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .vault import SecretUnavailable

log = logging.getLogger("vu.errors")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: list | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details or []


class DependencyError(ApiError):
    """Otro servicio interno no respondió a tiempo o falló."""

    def __init__(self, service: str):
        super().__init__(503, "DEPENDENCY_UNAVAILABLE", f"Servicio {service} no disponible, intenta más tarde")


def _body(request: Request, code: str, message: str, details=None):
    body = {"error": {"code": code, "message": message, "requestId": getattr(request.state, "request_id", None)}}
    if details:
        body["error"]["details"] = details
    return body


def install_error_handlers(app: FastAPI):
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content=_body(request, exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        # Sólo se informa el campo y el motivo, sin repetir el valor recibido.
        details = [
            {"campo": ".".join(str(p) for p in err.get("loc", [])[1:]), "motivo": err.get("msg", "inválido")}
            for err in exc.errors()
        ]
        return JSONResponse(status_code=400, content=_body(request, "VALIDATION_ERROR", "Datos inválidos", details))

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        codes = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 401: "UNAUTHENTICATED", 403: "FORBIDDEN"}
        message = exc.detail if isinstance(exc.detail, str) else "Error"
        return JSONResponse(status_code=exc.status_code, content=_body(request, codes.get(exc.status_code, "HTTP_ERROR"), message))

    @app.exception_handler(SecretUnavailable)
    async def _secret(request: Request, exc: SecretUnavailable):
        return JSONResponse(status_code=503, content=_body(request, "SECRETS_UNAVAILABLE", "Servicio temporalmente no disponible"))

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        log.exception("unhandled_error request_id=%s", getattr(request.state, "request_id", None))
        return JSONResponse(status_code=500, content=_body(request, "INTERNAL_ERROR", "Error interno"))
