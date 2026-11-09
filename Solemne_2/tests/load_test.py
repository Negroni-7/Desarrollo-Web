"""Prueba de carga reproducible (módulo 9).

Mide latencia p50/p95/p99, throughput, errores y consumo de CPU y memoria de
cada proceso, y compara con los objetivos declarados en el ADR.

Uso (modo local):
  RATE_LIMIT_MULTIPLIER=1000 python scripts/run_local.py --test-profile
  python tests/load_test.py            # ~2,5 minutos
El multiplicador sólo existe para que una única IP de prueba no sea frenada por
el límite de solicitudes (que se prueba por separado en test_security.py).
"""
import asyncio
import json
import os
import platform
import statistics
import sys
import threading
import time
import uuid
from pathlib import Path

import httpx
import psutil

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))
from conftest import API, CA, CERTS_DIR, CREDS, ENTREGA, H, INVENTORY_GRPC  # noqa: E402

OUT = ROOT / "docs" / "evidencias" / "carga"
OUT.mkdir(parents=True, exist_ok=True)
DURATION = int(os.getenv("LOAD_DURATION", "30"))

# Objetivos (p95 en ms, error máximo %) derivados de la carga proyectada (ver ADR-02).
SCENARIOS = [
    {"id": "C1", "name": "Catálogo público (S01) vía gateway", "concurrency": 20, "p95_ms": 300, "max_err": 1.0},
    {"id": "C2", "name": "Cotizar carrito (S02) → gRPC QuoteItems", "concurrency": 10, "p95_ms": 400, "max_err": 1.0},
    {"id": "C3", "name": "Crear y anular pedido (S10+S13) → gRPC Reserve/Release", "concurrency": 5, "p95_ms": 800, "max_err": 1.0},
    {"id": "C4", "name": "GraphQL misPedidos (S11) orders+inventory+payments", "concurrency": 5, "p95_ms": 800, "max_err": 1.0},
    {"id": "C5", "name": "gRPC QuoteItems directo (orders→inventory, mTLS)", "concurrency": 10, "p95_ms": 50, "max_err": 0.0},
]


class Sampler(threading.Thread):
    """Muestrea CPU (%) y memoria RSS (MB) de cada proceso del sistema cada 1 s."""

    def __init__(self):
        super().__init__(daemon=True)
        pids = json.loads((ROOT / "runtime" / "pids.json").read_text()) if (ROOT / "runtime" / "pids.json").exists() else {}
        self.procs = {}
        for name, pid in pids.items():
            try:
                p = psutil.Process(pid)
                p.cpu_percent()
                self.procs[name] = p
            except psutil.Error:
                pass
        self.samples = {n: {"cpu": [], "rss": []} for n in self.procs}
        self.running = True

    def run(self):
        while self.running:
            time.sleep(1)
            for n, p in self.procs.items():
                try:
                    self.samples[n]["cpu"].append(p.cpu_percent())
                    self.samples[n]["rss"].append(p.memory_info().rss / 1e6)
                except psutil.Error:
                    pass

    def summary(self):
        return {n: {"cpu_avg_pct": round(statistics.mean(s["cpu"]), 1) if s["cpu"] else 0,
                    "cpu_max_pct": round(max(s["cpu"]), 1) if s["cpu"] else 0,
                    "rss_max_mb": round(max(s["rss"]), 1) if s["rss"] else 0} for n, s in self.samples.items()}


def pct(values, q):
    values = sorted(values)
    return round(values[min(len(values) - 1, int(q / 100 * len(values)))], 1) if values else None


async def run_http(scenario, op):
    lat, errors, codes = [], 0, {}
    limits = httpx.Limits(max_connections=scenario["concurrency"] * 2)
    async with httpx.AsyncClient(base_url=API, verify=CA, timeout=10, headers=H, limits=limits) as c:
        if scenario["id"] in ("C3", "C4"):
            r = await c.post("/auth/login", json={"email": "cliente.demo@correo.cl", "password": CREDS["cliente.demo@correo.cl"]})
            assert r.status_code == 200
        end = time.monotonic() + DURATION

        async def worker():
            nonlocal errors
            while time.monotonic() < end:
                t0 = time.perf_counter()
                try:
                    ok, code = await op(c)
                except httpx.HTTPError:
                    ok, code = False, "exc"
                lat.append((time.perf_counter() - t0) * 1000)
                codes[code] = codes.get(code, 0) + 1
                if not ok:
                    errors += 1

        await asyncio.gather(*[worker() for _ in range(scenario["concurrency"])])
    return lat, errors, codes


async def op_catalog(c):
    r = await c.get("/products")
    return r.status_code == 200, r.status_code


async def op_quote(c):
    r = await c.post("/orders/quote", json={"items": [{"productoId": "kuyen-tinto", "cantidad": 1},
                                                      {"productoId": "cipreses-blanco", "cantidad": 2}],
                                            "destino": {"comuna": "Providencia", "region": "Metropolitana"}})
    return r.status_code == 200, r.status_code


async def op_order(c):
    r = await c.post("/orders", json={"items": [{"productoId": "pinot-rosado", "cantidad": 1}], "entrega": ENTREGA},
                     headers={"Idempotency-Key": str(uuid.uuid4())})
    if r.status_code != 201:
        return False, r.status_code
    x = await c.post(f"/orders/{r.json()['id']}/cancel")  # libera el stock (prueba de recuperación bajo carga)
    return x.status_code == 200, x.status_code


async def op_graphql(c):
    q = "{ misPedidos(tamano: 5) { total items { numero estado items { nombre producto { imagen } } pago { estado } } } }"
    r = await c.post("/graphql", json={"query": q})
    return r.status_code == 200 and "errors" not in r.json(), r.status_code


def run_grpc(scenario):
    import grpc
    sys.path.insert(0, str(ROOT / "backend" / "services" / "orders"))
    import inventory_pb2 as pb
    import inventory_pb2_grpc as pbg
    d = CERTS_DIR / "orders"
    creds = grpc.ssl_channel_credentials(Path(CA).read_bytes(), (d / "tls.key").read_bytes(), (d / "tls.crt").read_bytes())
    stub = pbg.InventoryReservationsStub(grpc.secure_channel(INVENTORY_GRPC, creds))
    req = pb.QuoteRequest(items=[pb.ItemQuantity(product_id="kuyen-tinto", quantity=1)])
    lat, errors, codes, lock = [], 0, {}, threading.Lock()
    end = time.monotonic() + DURATION

    def worker():
        nonlocal errors
        while time.monotonic() < end:
            t0 = time.perf_counter()
            try:
                stub.QuoteItems(req, timeout=1)
                code = "OK"
            except grpc.RpcError as e:
                code = e.code().name
            with lock:
                lat.append((time.perf_counter() - t0) * 1000)
                codes[code] = codes.get(code, 0) + 1
                errors += code != "OK"

    threads = [threading.Thread(target=worker) for _ in range(scenario["concurrency"])]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return lat, errors, codes


def main():
    ops = {"C1": op_catalog, "C2": op_quote, "C3": op_order, "C4": op_graphql}
    results = []
    for sc in SCENARIOS:
        print(f"→ {sc['id']} {sc['name']} (concurrencia {sc['concurrency']}, {DURATION} s)")
        sampler = Sampler()
        sampler.start()
        t0 = time.time()
        lat, errors, codes = run_grpc(sc) if sc["id"] == "C5" else asyncio.run(run_http(sc, ops[sc["id"]]))
        elapsed = time.time() - t0
        sampler.running = False
        sampler.join()
        n = len(lat)
        res = {**sc, "requests": n, "duration_s": round(elapsed, 1), "throughput_rps": round(n / elapsed, 1),
               "p50_ms": pct(lat, 50), "p95_ms_measured": pct(lat, 95), "p99_ms": pct(lat, 99),
               "max_ms": round(max(lat), 1) if lat else None, "errors": errors,
               "error_pct": round(100 * errors / n, 2) if n else 100.0, "status_codes": codes,
               "resources": sampler.summary()}
        res["meets_target"] = res["p95_ms_measured"] <= sc["p95_ms"] and res["error_pct"] <= sc["max_err"]
        results.append(res)
        print(f"   {n} sol. · {res['throughput_rps']} sol/s · p95 {res['p95_ms_measured']} ms · errores {res['error_pct']}% "
              f"→ {'CUMPLE' if res['meets_target'] else 'NO CUMPLE'}")
    env = {"python": platform.python_version(), "os": platform.platform(), "cpus": psutil.cpu_count(),
           "ram_gb": round(psutil.virtual_memory().total / 1e9, 1), "mode": "local (procesos, TLS en todos los tramos)",
           "fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "duracion_por_escenario_s": DURATION, "tipo": "medición"}
    (OUT / "resultados.json").write_text(json.dumps({"entorno": env, "escenarios": results}, indent=2, ensure_ascii=False))
    print(f"Resultados en {OUT / 'resultados.json'}")


if __name__ == "__main__":
    main()
