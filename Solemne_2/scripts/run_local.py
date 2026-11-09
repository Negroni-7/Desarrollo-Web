"""Arranque local SIN Docker (alternativa reproducible a docker compose).

Requisitos: Python 3.12+, Node 20+, MongoDB 7/8 (mongod) y Vault (vault) en el
PATH o indicados con MONGOD_BIN / VAULT_BIN. Antes: python scripts/setup.py

  python scripts/run_local.py               # levanta todo
  python scripts/run_local.py --test-profile  # plazo de pago corto para pruebas de vencimiento
  python scripts/stop_local.py              # detiene todo

Todos los servicios escuchan en 127.0.0.1 con TLS; el único punto de entrada
público es https://localhost:8443/api/v1 (API Gateway).
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
from pymongo import MongoClient
from pymongo.errors import OperationFailure

ROOT = Path(__file__).resolve().parent.parent
RT = ROOT / "runtime"
CERTS = RT / "certs"
CA = str(CERTS / "ca.crt")
LOGS = RT / "logs"
PIDS = RT / "pids.json"
MONGOD = os.getenv("MONGOD_BIN") or shutil.which("mongod") or "mongod"
VAULT = os.getenv("VAULT_BIN") or shutil.which("vault") or "vault"
TEST_PROFILE = "--test-profile" in sys.argv

PORTS = {"gateway": 8443, "auth": 9101, "clients": 9102, "inventory": 9103, "orders": 9104, "payments": 9105,
         "tastings": 9106, "analytics": 9107, "graphql": 4000, "sandbox": 8090}
URLS = {f"{n.upper()}_URL": f"https://127.0.0.1:{p}" for n, p in PORTS.items()}


def load_env() -> dict:
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


ENV = load_env()
pids: dict[str, int] = json.loads(PIDS.read_text()) if PIDS.exists() else {}


def spawn(name: str, cmd: list[str], env: dict | None = None, cwd: Path = ROOT):
    log = open(LOGS / f"{name}.log", "ab")
    proc = subprocess.Popen(cmd, cwd=cwd, env={**os.environ, **(env or {})}, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)
    pids[name] = proc.pid
    PIDS.write_text(json.dumps(pids))


def wait_http(url: str, name: str, timeout: int = 40):
    for _ in range(timeout * 4):
        try:
            if httpx.get(url, verify=CA, timeout=1).status_code == 200:
                print(f"  ✓ {name}")
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    raise SystemExit(f"{name} no respondió; revisa runtime/logs/{name}.log")


def start_mongo():
    data = RT / "mongo-data"
    data.mkdir(exist_ok=True)
    spawn("mongo", [MONGOD, "--dbpath", str(data), "--port", "27017", "--bind_ip", "127.0.0.1", "--auth",
                    "--tlsMode", "requireTLS", "--tlsCertificateKeyFile", str(CERTS / "mongo" / "mongo.pem"),
                    "--tlsCAFile", CA, "--tlsAllowConnectionsWithoutCertificates"])
    root = (ENV["MONGO_ROOT_USER"], ENV["MONGO_ROOT_PASSWORD"])
    for _ in range(60):
        try:
            c = MongoClient(f"mongodb://{root[0]}:{root[1]}@127.0.0.1:27017/?authSource=admin", tls=True, tlsCAFile=CA,
                            serverSelectionTimeoutMS=1000)
            c.admin.command("ping")
            print("  ✓ mongo")
            return
        except OperationFailure:
            # Primera ejecución: excepción de localhost para crear el usuario raíz.
            c = MongoClient("mongodb://127.0.0.1:27017/", tls=True, tlsCAFile=CA, serverSelectionTimeoutMS=1000)
            c.admin.command("createUser", root[0], pwd=root[1], roles=["root"])
        except Exception:
            time.sleep(0.5)
    raise SystemExit("MongoDB no arrancó")


def start_vault():
    hcl = RT / "vault-local.hcl"
    hcl.write_text(f'listener "tcp" {{\n  address = "127.0.0.1:8200"\n  tls_cert_file = "{CERTS / "vault" / "tls.crt"}"\n'
                   f'  tls_key_file = "{CERTS / "vault" / "tls.key"}"\n}}\ndisable_mlock = true\n')
    spawn("vault", [VAULT, "server", "-dev", f"-dev-root-token-id={ENV['VAULT_ROOT_TOKEN']}",
                    "-dev-listen-address=127.0.0.1:8201", f"-config={hcl}"])
    wait_http("https://127.0.0.1:8200/v1/sys/health", "vault")


def run_script(script: str, extra: dict):
    env = {**os.environ, **ENV, **extra}
    subprocess.run([sys.executable, str(ROOT / "scripts" / script)], cwd=ROOT, env=env, check=True)


def service_env(name: str) -> dict:
    env = {
        "SERVICE_NAME": name, "HOST": "127.0.0.1", "PORT": str(PORTS[name]),
        "VAULT_ADDR": "https://127.0.0.1:8200", "VAULT_CACERT": CA,
        "VAULT_TOKEN_FILE": str(RT / "tokens" / name / "vault-token"),
        "TLS_ENABLED": "true", "TLS_CA_FILE": CA,
        "TLS_CERT_FILE": str(CERTS / name / "tls.crt"), "TLS_KEY_FILE": str(CERTS / name / "tls.key"),
        "PYTHONPATH": os.pathsep.join([str(ROOT / "backend" / "common"), str(ROOT / "backend" / "services" / name)]),
        "PYTHONUNBUFFERED": "1", **URLS,
        # Perfil de pruebas: caché de secretos más corta para verificar la rotación en segundos.
        "SECRET_CACHE_SECONDS": "10" if TEST_PROFILE else "60",
    }
    extras = {
        "inventory": {"GRPC_PORT": "50051"},
        "orders": {"INVENTORY_GRPC": "127.0.0.1:50051",
                   "PAYMENT_WINDOW_SECONDS": "25" if TEST_PROFILE else "900",
                   "SWEEP_INTERVAL_SECONDS": "2" if TEST_PROFILE else "10"},
        "payments": {"PROVIDER_API_URL": "https://127.0.0.1:8090", "PAYMENT_RETURN_URL": "https://localhost:8443/"},
        "sandbox": {"SANDBOX_PUBLIC_URL": "https://localhost:8090",
                    "MERCHANT_WEBHOOK_URL": "https://127.0.0.1:8443/api/v1/payments/webhook"},
        "gateway": {"RATE_LIMIT_MULTIPLIER": os.getenv("RATE_LIMIT_MULTIPLIER", "1")},
        "graphql": {"NODE_EXTRA_CA_CERTS": CA},
    }
    env.update(extras.get(name, {}))
    return env


def main():
    if not CA or not Path(CA).exists():
        raise SystemExit("Primero ejecuta: python scripts/setup.py")
    LOGS.mkdir(exist_ok=True)
    print("Iniciando infraestructura:")
    start_mongo()
    start_vault()
    common = {"VAULT_ADDR": "https://127.0.0.1:8200", "VAULT_CACERT": CA, "TOKENS_DIR": str(RT / "tokens"),
              "MONGO_ADMIN_HOST": "127.0.0.1:27017", "MONGO_SERVICE_HOST": "127.0.0.1:27017", "MONGO_TLS_CA": CA}
    run_script("vault_init.py", common)
    run_script("seed_data.py", common)
    print("Iniciando servicios:")
    for name in ["auth", "clients", "inventory", "orders", "payments", "tastings", "analytics", "sandbox", "gateway"]:
        spawn(name, [sys.executable, str(ROOT / "backend" / "services" / name / "app.py")], service_env(name))
    spawn("graphql", ["node", "src/server.js"], service_env("graphql"), cwd=ROOT / "backend" / "gql-gateway")
    for name, port in PORTS.items():
        wait_http(f"https://127.0.0.1:{port}/health", name)
    print("\nListo: API en https://localhost:8443/api/v1  (credenciales demo en runtime/seed_credentials.txt)")


if __name__ == "__main__":
    main()
