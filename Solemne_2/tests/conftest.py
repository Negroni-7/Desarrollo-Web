"""Configuración común de las pruebas automatizadas.

Las pruebas se ejecutan contra el sistema REAL levantado (local o Docker):
  local:   python scripts/run_local.py --test-profile ; pytest tests
  docker:  docker compose --profile test run --rm tests
"""
import json
import os
import signal
import sys
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
GATEWAY = os.getenv("GATEWAY_URL", "https://localhost:8443").rstrip("/")
API = GATEWAY + "/api/v1"
SANDBOX = os.getenv("SANDBOX_URL", "https://localhost:8090").rstrip("/")
CA = os.getenv("CA_FILE", str(ROOT / "runtime" / "certs" / "ca.crt"))
CERTS_DIR = Path(os.getenv("CERTS_DIR", str(ROOT / "runtime" / "certs")))
CREDS_FILE = Path(os.getenv("SEED_CREDENTIALS_FILE", str(ROOT / "runtime" / "seed_credentials.txt")))
INTERNAL = dict(kv.split("=", 1) for kv in os.getenv(
    "INTERNAL_URLS",
    "inventory=https://127.0.0.1:9103,orders=https://127.0.0.1:9104,auth=https://127.0.0.1:9101,"
    "payments=https://127.0.0.1:9105,graphql=https://127.0.0.1:4000,clients=https://127.0.0.1:9102").split(","))
INVENTORY_GRPC = os.getenv("INVENTORY_GRPC", "127.0.0.1:50051")
H = {"X-Requested-With": "XMLHttpRequest"}
LOCAL_MODE = (ROOT / "runtime" / "pids.json").exists()

CREDS = {line.split()[1]: line.split()[2] for line in CREDS_FILE.read_text().splitlines() if line.strip()}
ADMIN, SOMMELIER, CLIENT = "admin@vinaurbana.cl", "sommelier@vinaurbana.cl", "cliente.demo@correo.cl"


def new_client() -> httpx.Client:
    return httpx.Client(base_url=API, verify=CA, timeout=20, headers=H)


def login(email: str, password: str | None = None) -> httpx.Client:
    c = new_client()
    r = c.post("/auth/login", json={"email": email, "password": password or CREDS[email]})
    assert r.status_code == 200, r.text
    return c


def register_and_login(prefix: str = "test") -> tuple[httpx.Client, dict]:
    email = f"{prefix}.{uuid.uuid4().hex[:8]}@correo.cl"
    data = {"nombre": "Usuario Prueba", "email": email, "password": "ClaveSegura123",
            "telefono": "+56 9 5555 1234", "fechaNacimiento": "1990-05-20", "aceptaTerminos": True}
    anon = new_client()
    r = anon.post("/auth/register", json=data)
    assert r.status_code == 201, r.text
    return login(email, data["password"]), data


@pytest.fixture(scope="session")
def anon():
    return new_client()


@pytest.fixture(scope="session")
def client_a():
    return login(CLIENT)


@pytest.fixture(scope="session")
def client_b():
    c, _ = register_and_login("clienteb")
    return c


@pytest.fixture(scope="session")
def admin():
    return login(ADMIN)


@pytest.fixture(scope="session")
def sommelier():
    return login(SOMMELIER)


ENTREGA = {"nombreReceptor": "Camila Demo", "calle": "Av. Providencia", "numero": "1500", "comuna": "Providencia",
           "region": "Metropolitana", "telefono": "+56911112222"}


def create_order(c: httpx.Client, items, key: str | None = None) -> httpx.Response:
    return c.post("/orders", json={"items": items, "entrega": ENTREGA},
                  headers={"Idempotency-Key": key or str(uuid.uuid4())})


def provider_decide(redirect_url: str, decision: str = "approve") -> str:
    """Simula al comprador en la página del proveedor. Devuelve el token del proveedor."""
    token = redirect_url.rstrip("/").rsplit("/", 1)[1]
    r = httpx.post(f"{SANDBOX}/pay/{token}/decision", data={"decision": decision}, verify=CA, follow_redirects=False)
    assert r.status_code == 303, r.text
    return token


def stock_of(admin_client: httpx.Client, pid: str) -> int:
    items = admin_client.get("/admin/products").json()["items"]
    return next(p["stock"] for p in items if p["id"] == pid)


def gql(c: httpx.Client, query: str, variables: dict | None = None) -> httpx.Response:
    return c.post("/graphql", json={"query": query, "variables": variables or {}})


def next_weekday(days_ahead: int) -> str:
    d = date.today() + timedelta(days=days_ahead)
    while d.weekday() == 6:
        d += timedelta(days=1)
    return d.isoformat()


# ---------------------------------------------------------------- control de procesos (modo local)
def _pids():
    return json.loads((ROOT / "runtime" / "pids.json").read_text())


def signal_service(name: str, sig):
    os.killpg(_pids()[name], sig)


def restart_service(name: str):
    """Detiene y vuelve a lanzar un servicio en modo local."""
    sys.path.insert(0, str(ROOT / "scripts"))
    saved = sys.argv
    sys.argv = ["run_local.py", "--test-profile"]
    import run_local  # noqa: E402
    sys.argv = saved
    try:
        os.killpg(_pids()[name], signal.SIGTERM)
    except ProcessLookupError:
        pass
    time.sleep(1)
    if name == "graphql":
        run_local.spawn(name, ["node", "src/server.js"], run_local.service_env(name), cwd=ROOT / "backend" / "gql-gateway")
    else:
        run_local.spawn(name, [sys.executable, str(ROOT / "backend" / "services" / name / "app.py")], run_local.service_env(name))
    run_local.wait_http(f"https://127.0.0.1:{run_local.PORTS[name]}/health", name)


local_only = pytest.mark.skipif(not LOCAL_MODE, reason="requiere control de procesos (modo local)")
