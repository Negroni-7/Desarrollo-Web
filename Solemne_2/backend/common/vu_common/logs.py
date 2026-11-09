"""Logs en JSON con identificador de correlación.

Nunca se registran cuerpos, tokens, contraseñas ni cabeceras de autorización.
Los correos se enmascaran con mask_email si alguna vez hay que mencionarlos.
"""
import json
import logging
import sys
import time
import uuid

from fastapi import FastAPI, Request

from . import settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "service": settings.SERVICE_NAME,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "method", "path", "status", "duration_ms", "caller", "user"):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        if record.exc_info:
            data["exc"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(data, ensure_ascii=False)


def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    # Los logs de acceso de uvicorn incluyen la query string: se desactivan y se
    # reemplazan por el middleware de abajo, que registra sólo la ruta.
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("httpx").setLevel(logging.WARNING)


def mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return "***"
    user, domain = email.split("@", 1)
    return f"{user[:1]}***@{domain}"


def install_request_logging(app: FastAPI, trust_incoming_request_id: bool = True):
    access = logging.getLogger("vu.access")

    @app.middleware("http")
    async def _log(request: Request, call_next):
        incoming = request.headers.get("x-request-id", "")
        valid = trust_incoming_request_id and 8 <= len(incoming) <= 64 and incoming.replace("-", "").isalnum()
        request.state.request_id = incoming if valid else str(uuid.uuid4())
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        access.info(
            "request",
            extra={
                "request_id": request.state.request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                "caller": request.headers.get("x-caller-id", "external"),
            },
        )
        return response
