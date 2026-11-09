"""Cliente mínimo de Vault (KV v2).

- El token de Vault del servicio se lee desde un archivo montado sólo en ese
  contenedor (nunca desde el código ni el repositorio).
- Cada token tiene una política que le permite leer únicamente sus rutas.
- Los secretos se cachean SECRET_CACHE_SECONDS para soportar rotación sin
  reiniciar. Si Vault no responde se usa el último valor conocido; si nunca
  se obtuvo, el servicio falla cerrado (no atiende la operación).
"""
import logging
import threading
import time

import httpx

from . import settings

log = logging.getLogger("vu.vault")


class SecretUnavailable(Exception):
    """Vault no respondió y no hay un valor previo en caché."""


class VaultClient:
    def __init__(self):
        self._cache: dict[str, tuple[float, dict]] = {}
        self._lock = threading.Lock()

    def _token(self) -> str:
        if not settings.VAULT_TOKEN_FILE:
            raise SecretUnavailable("VAULT_TOKEN_FILE no configurado")
        with open(settings.VAULT_TOKEN_FILE, encoding="utf-8") as fh:
            return fh.read().strip()

    def read(self, path: str, force: bool = False) -> dict:
        now = time.time()
        with self._lock:
            cached = self._cache.get(path)
        if cached and not force and now - cached[0] < settings.SECRET_CACHE_SECONDS:
            return cached[1]
        try:
            resp = httpx.get(
                f"{settings.VAULT_ADDR}/v1/secret/data/{path}",
                headers={"X-Vault-Token": self._token()},
                verify=settings.VAULT_CACERT or True,
                timeout=3.0,
            )
            if resp.status_code != 200:
                raise SecretUnavailable(f"Vault respondió {resp.status_code} para {path}")
            data = resp.json()["data"]["data"]
        except (httpx.HTTPError, OSError, SecretUnavailable, KeyError) as exc:
            if cached:
                # Degradación controlada: se mantiene el último secreto válido.
                log.warning("vault_unavailable_using_cached path=%s err=%s", path, type(exc).__name__)
                return cached[1]
            log.error("vault_unavailable path=%s err=%s", path, type(exc).__name__)
            raise SecretUnavailable(path) from exc
        with self._lock:
            self._cache[path] = (now, data)
        return data


vault = VaultClient()
