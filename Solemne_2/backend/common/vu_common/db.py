"""Acceso a la base de datos PROPIA del servicio.

La URI (usuario y contraseña de MongoDB con permisos sólo sobre su base) se
obtiene de Vault en secret/db/<servicio>. Ningún servicio conoce las
credenciales de la base de otro servicio.
"""
from pymongo import MongoClient
from pymongo.database import Database

from . import settings
from .vault import vault

_client: MongoClient | None = None
_db: Database | None = None


def get_db() -> Database:
    global _client, _db
    if _db is None:
        secret = vault.read(f"db/{settings.SERVICE_NAME}")
        kwargs = {"serverSelectionTimeoutMS": 3000, "connectTimeoutMS": 3000}
        if settings.TLS_ENABLED:
            kwargs.update(tls=True, tlsCAFile=settings.TLS_CA_FILE)
        _client = MongoClient(secret["uri"], **kwargs)
        _db = _client[secret["database"]]
    return _db
