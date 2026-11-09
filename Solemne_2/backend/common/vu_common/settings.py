"""Configuración leída desde variables de entorno (sin valores secretos)."""
import os

SERVICE_NAME = os.getenv("SERVICE_NAME", "unknown")

# Vault: dirección, CA y archivo con el token propio del servicio.
VAULT_ADDR = os.getenv("VAULT_ADDR", "https://127.0.0.1:8200")
VAULT_TOKEN_FILE = os.getenv("VAULT_TOKEN_FILE", "")
VAULT_CACERT = os.getenv("VAULT_CACERT", "")

# TLS del propio servicio y CA de la red interna.
TLS_ENABLED = os.getenv("TLS_ENABLED", "true").lower() == "true"
TLS_CA_FILE = os.getenv("TLS_CA_FILE", "")
TLS_CERT_FILE = os.getenv("TLS_CERT_FILE", "")
TLS_KEY_FILE = os.getenv("TLS_KEY_FILE", "")

PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")

# Tiempo máximo que se reutiliza un secreto leído de Vault antes de volver a leerlo.
SECRET_CACHE_SECONDS = int(os.getenv("SECRET_CACHE_SECONDS", "60"))


def service_url(name: str) -> str:
    """URL base de otro servicio interno, p. ej. INVENTORY_URL."""
    value = os.getenv(f"{name.upper()}_URL")
    if not value:
        raise RuntimeError(f"Falta la variable {name.upper()}_URL")
    return value.rstrip("/")


def verify_param():
    """Parámetro 'verify' para httpx: CA interna si existe."""
    return TLS_CA_FILE if TLS_CA_FILE else True
