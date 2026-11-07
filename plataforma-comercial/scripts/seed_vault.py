"""Carga los secretos de desarrollo en Vault (KV v2, mount 'secret').
El Vault en modo dev guarda todo en memoria: hay que volver a ejecutar
este script cada vez que se reinicia 'vault server -dev'.
"""
import os
import sys
import httpx

VAULT_ADDR = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
VAULT_TOKEN = os.getenv("VAULT_TOKEN", "root")

payload = {
    "data": {
        "client_token": "token-cliente-demo-123",
        "backend_shared_secret": "secreto-interno-demo-456",
    }
}

try:
    r = httpx.post(
        f"{VAULT_ADDR}/v1/secret/data/gateway",
        headers={"X-Vault-Token": VAULT_TOKEN},
        json=payload,
        timeout=5.0,
    )
except httpx.RequestError as e:
    print(f"ERROR: no se pudo conectar a Vault en {VAULT_ADDR}: {e}")
    sys.exit(1)

if r.status_code in (200, 204):
    print("OK: secretos guardados en secret/gateway")
    sys.exit(0)

print(f"ERROR {r.status_code}: {r.text}")
sys.exit(1)
