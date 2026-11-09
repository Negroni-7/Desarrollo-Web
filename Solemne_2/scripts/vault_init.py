"""vault-init: prepara secretos, políticas, tokens de servicio y usuarios de MongoDB.

Se ejecuta en cada arranque (contenedor 'vault-init' o run_local.py):
  - Genera los secretos que falten con valores aleatorios (nunca valores fijos).
  - Crea un usuario de MongoDB por servicio con permiso readWrite SOLO sobre su
    base, y guarda su URI en Vault (secret/db/<servicio>).
  - Escribe una política por servicio con permisos mínimos de lectura.
  - Emite un token de Vault por servicio (TTL 30 días) y lo deja en
    runtime/tokens/<servicio>/vault-token; revoca el token anterior.
  --rotate <ruta>  regenera un secreto concreto (p. ej. internal/inventory/gateway).
"""
import os
import secrets
import sys
import time
from pathlib import Path

import httpx
from pymongo import MongoClient

VAULT_ADDR = os.environ["VAULT_ADDR"].rstrip("/")
ROOT_TOKEN = os.environ["VAULT_ROOT_TOKEN"]
CA = os.getenv("VAULT_CACERT") or True
TOKENS_DIR = Path(os.getenv("TOKENS_DIR", "runtime/tokens"))
MONGO_ADMIN_HOST = os.getenv("MONGO_ADMIN_HOST", "127.0.0.1:27017")      # desde donde corre este script
MONGO_SERVICE_HOST = os.getenv("MONGO_SERVICE_HOST", "127.0.0.1:27017")  # desde donde se conectan los servicios
MONGO_TLS_CA = os.getenv("MONGO_TLS_CA", "")

DB_OWNERS = ["auth", "clients", "inventory", "orders", "payments", "tastings", "analytics", "sandbox"]
# destino <- llamadores permitidos (una credencial distinta por tramo)
PAIRS = {
    "auth": ["gateway", "clients"],
    "clients": ["gateway", "auth"],
    "inventory": ["gateway", "graphql", "orders"],  # orders: sólo se usa si gRPC corre sin TLS
    "orders": ["gateway", "graphql", "payments", "clients"],
    "payments": ["gateway", "graphql"],
    "tastings": ["gateway", "clients"],
    "analytics": ["orders", "tastings", "graphql"],
    "graphql": ["gateway"],
}
EXTRA_POLICIES = {
    "auth": ['path "secret/data/auth/jwt" { capabilities = ["read"] }'],
    "payments": ['path "secret/data/payments/provider" { capabilities = ["read"] }',
                 'path "secret/data/payments/transbank" { capabilities = ["read"] }'],
    "sandbox": ['path "secret/data/sandbox/merchant" { capabilities = ["read"] }'],
}
HOLDERS = ["gateway", "auth", "clients", "inventory", "orders", "payments", "tastings", "analytics", "graphql", "sandbox"]

H = {"X-Vault-Token": ROOT_TOKEN}


def vault(method, path, **kw):
    r = httpx.request(method, f"{VAULT_ADDR}/v1/{path}", headers=H, verify=CA, timeout=5.0, **kw)
    if r.status_code >= 400 and r.status_code != 404:
        raise SystemExit(f"Vault {method} {path} -> {r.status_code}")
    return r


def read_secret(path):
    r = vault("GET", f"secret/data/{path}")
    return r.json()["data"]["data"] if r.status_code == 200 else None


def put_secret(path, data):
    vault("POST", f"secret/data/{path}", json={"data": data})


def ensure(path, factory, rotate=False):
    current = read_secret(path)
    if current and not rotate:
        return current
    data = factory(current)
    put_secret(path, data)
    print(f"  secreto {'rotado' if current else 'creado'}: secret/{path}")
    return data


def wait_vault():
    for _ in range(60):
        try:
            if httpx.get(f"{VAULT_ADDR}/v1/sys/health", verify=CA, timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise SystemExit("Vault no respondió")


def mongo_users():
    kw = {"tls": True, "tlsCAFile": MONGO_TLS_CA} if MONGO_TLS_CA else {}
    client = MongoClient(f"mongodb://{os.environ['MONGO_ROOT_USER']}:{os.environ['MONGO_ROOT_PASSWORD']}@{MONGO_ADMIN_HOST}/"
                         f"?authSource=admin", serverSelectionTimeoutMS=20000, **kw)
    for svc in DB_OWNERS:
        db_name, user = f"vu_{svc}", f"svc_{svc}"
        existing = read_secret(f"db/{svc}")
        password = existing["password"] if existing else secrets.token_urlsafe(24)
        db = client[db_name]
        if db.command("usersInfo", user)["users"]:
            db.command("updateUser", user, pwd=password, roles=[{"role": "readWrite", "db": db_name}])
        else:
            db.command("createUser", user, pwd=password, roles=[{"role": "readWrite", "db": db_name}])
        tls = "&tls=true" if MONGO_TLS_CA else ""
        put_secret(f"db/{svc}", {"uri": f"mongodb://{user}:{password}@{MONGO_SERVICE_HOST}/{db_name}?authSource={db_name}{tls}",
                                 "database": db_name, "password": password})
    print(f"  {len(DB_OWNERS)} usuarios de MongoDB con permisos sólo sobre su base")


def policy_for(svc):
    rules = []
    if svc in PAIRS:  # credenciales para verificar a quienes lo llaman
        rules.append(f'path "secret/data/internal/{svc}/*" {{ capabilities = ["read"] }}')
    for target, callers in PAIRS.items():  # credenciales para llamar a otros
        if svc in callers:
            rules.append(f'path "secret/data/internal/{target}/{svc}" {{ capabilities = ["read"] }}')
    if svc in DB_OWNERS:
        rules.append(f'path "secret/data/db/{svc}" {{ capabilities = ["read"] }}')
    rules += EXTRA_POLICIES.get(svc, [])
    return "\n".join(rules)


def issue_tokens():
    for svc in HOLDERS:
        vault("PUT", f"sys/policies/acl/vu-{svc}", json={"policy": policy_for(svc)})
        folder = TOKENS_DIR / svc
        folder.mkdir(parents=True, exist_ok=True)
        token_file = folder / "vault-token"
        if token_file.exists():  # revocación del token anterior
            old = token_file.read_text().strip()
            if old:  # si Vault se reinició (modo dev) el token ya no existe: se ignora el error
                httpx.post(f"{VAULT_ADDR}/v1/auth/token/revoke", headers=H, verify=CA, timeout=5.0, json={"token": old})
        r = vault("POST", "auth/token/create", json={"policies": [f"vu-{svc}"], "ttl": "720h", "renewable": True,
                                                     "display_name": svc, "no_default_policy": False})
        token_file.write_text(r.json()["auth"]["client_token"])
        os.chmod(token_file, 0o644)  # el contenedor del servicio corre con otro usuario
    print(f"  {len(HOLDERS)} tokens de servicio emitidos con políticas de mínimo privilegio")


def main():
    wait_vault()
    rotate = sys.argv[sys.argv.index("--rotate") + 1] if "--rotate" in sys.argv else None
    if rotate:
        if rotate.startswith("internal/"):
            ensure(rotate, lambda _: {"token": secrets.token_urlsafe(32)}, rotate=True)
        elif rotate == "auth/jwt":
            ensure(rotate, lambda cur: {"signing_key": secrets.token_urlsafe(48), "kid": f"k{int(time.time())}",
                                        "previous_key": cur["signing_key"] if cur else ""}, rotate=True)
        else:
            raise SystemExit("Rotación soportada: internal/<destino>/<llamador> o auth/jwt")
        return
    print("vault-init:")
    ensure("auth/jwt", lambda _: {"signing_key": secrets.token_urlsafe(48), "kid": f"k{int(time.time())}", "previous_key": ""})
    for target, callers in PAIRS.items():
        for caller in callers:
            ensure(f"internal/{target}/{caller}", lambda _: {"token": secrets.token_urlsafe(32)})
    merchant = ensure("payments/provider", lambda _: {"api_key_id": "vu-" + secrets.token_hex(6),
                                                      "api_key_secret": secrets.token_urlsafe(32),
                                                      "webhook_secret": secrets.token_urlsafe(32)})
    put_secret("sandbox/merchant", merchant)  # el proveedor (sandbox) guarda su propia copia
    if os.getenv("TRANSBANK_COMMERCE_CODE") and os.getenv("TRANSBANK_API_KEY"):
        put_secret("payments/transbank", {"commerce_code": os.environ["TRANSBANK_COMMERCE_CODE"],
                                          "api_key": os.environ["TRANSBANK_API_KEY"]})
    mongo_users()
    issue_tokens()
    print("vault-init: OK")


if __name__ == "__main__":
    main()
