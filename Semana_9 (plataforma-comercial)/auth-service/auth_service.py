import os
import secrets
import httpx
from fastapi import FastAPI, Header, HTTPException

app = FastAPI(
    title="Auth Service (outservice)",
    description="Valida si un Bearer token sigue activo consultando Vault",
)

VAULT_ADDR = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
VAULT_TOKEN = os.getenv("VAULT_TOKEN")

if not VAULT_TOKEN:
    raise RuntimeError("VAULT_TOKEN no configurado")


async def get_client_token() -> str:
    url = f"{VAULT_ADDR}/v1/secret/data/gateway"
    headers = {"X-Vault-Token": VAULT_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers=headers)
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Vault no disponible")

    if response.status_code != 200:
        raise HTTPException(
            status_code=500, detail="No fue posible acceder a Vault"
        )
    return response.json()["data"]["data"]["client_token"]


@app.get("/health")
def health():
    return {"status": "OK", "service": "Auth Service"}


@app.post("/validate")
async def validate(authorization: str = Header(default="")):
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return {"active": False, "client_id": None}

    expected = await get_client_token()
    active = secrets.compare_digest(
        token.encode("utf-8"), expected.encode("utf-8")
    )
    return {
        "active": active,
        "client_id": "student-client" if active else None,
    }