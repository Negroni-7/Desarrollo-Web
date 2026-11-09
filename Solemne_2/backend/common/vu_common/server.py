"""Arranque estándar de un servicio FastAPI con TLS y health check."""
import uvicorn
from fastapi import FastAPI

from . import settings
from .errors import install_error_handlers
from .logs import install_request_logging, setup_logging


def create_app(title: str, health_check=None, trust_request_id: bool = True) -> FastAPI:
    setup_logging()
    app = FastAPI(title=title, docs_url=None, redoc_url=None, openapi_url=None)
    install_error_handlers(app)
    install_request_logging(app, trust_request_id)

    @app.get("/health")
    def health():
        status = {"status": "ok", "service": settings.SERVICE_NAME}
        if health_check:
            try:
                health_check()
                status["dependencies"] = "ok"
            except Exception:
                status["status"] = "degraded"
                status["dependencies"] = "error"
        return status

    return app


def serve(app: FastAPI):
    kwargs = {"host": settings.HOST, "port": settings.PORT, "log_config": None, "access_log": False}
    if settings.TLS_ENABLED:
        kwargs.update(ssl_certfile=settings.TLS_CERT_FILE, ssl_keyfile=settings.TLS_KEY_FILE)
    uvicorn.run(app, **kwargs)
