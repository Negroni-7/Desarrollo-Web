"""Pruebas de fallos de dependencias, rotación de secretos y gRPC (módulos 6, 8, 9, 10).

Las que detienen procesos sólo corren en modo local (run_local.py); en Docker
el equivalente es `docker compose stop <servicio>` (ver README).
"""
import os
import signal
import subprocess
import sys
import time
import uuid

import grpc
import httpx
import pytest

from conftest import (CA, CERTS_DIR, INVENTORY_GRPC, ROOT, create_order, gql, local_only, restart_service,
                      signal_service, stock_of)


@local_only
def test_R01_payments_caido_graphql_entrega_datos_parciales(client_a):
    create_order(client_a, [{"productoId": "pinot-rosado", "cantidad": 1}])
    signal_service("payments", signal.SIGSTOP)  # simula un servicio que no responde
    try:
        t0 = time.time()
        r = gql(client_a, "{ misPedidos(tamano: 2) { items { numero estado pago { estado } } } }").json()
        elapsed = time.time() - t0
    finally:
        signal_service("payments", signal.SIGCONT)
    assert r["data"]["misPedidos"]["items"][0]["estado"]  # orders respondió
    assert r["data"]["misPedidos"]["items"][0]["pago"] is None
    assert r["errors"][0]["extensions"]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert elapsed < 6  # plazo máximo por llamada (3 s) respetado


@local_only
def test_R02_inventory_caido_respuesta_controlada(client_a, anon):
    signal_service("inventory", signal.SIGSTOP)
    try:
        q = anon.post("/orders/quote", json={"items": [{"productoId": "kuyen-tinto", "cantidad": 1}]})
        o = create_order(client_a, [{"productoId": "kuyen-tinto", "cantidad": 1}])
    finally:
        signal_service("inventory", signal.SIGCONT)
    assert q.status_code == 503 and q.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert o.status_code == 503  # no se crea un pedido sin reserva de stock confirmada


@local_only
def test_R03_vault_sin_respuesta_servicios_usan_secretos_en_cache(anon):
    assert anon.get("/products").status_code == 200  # carga caché
    signal_service("vault", signal.SIGSTOP)
    try:
        r = anon.get("/products")
    finally:
        signal_service("vault", signal.SIGCONT)
    assert r.status_code == 200


@local_only
def test_R04_rotacion_de_credencial_entre_servicios(anon):
    """Se rota secret/internal/inventory/gateway sin reiniciar servicios."""
    env = dict(l.split("=", 1) for l in (ROOT / ".env").read_text().splitlines() if "=" in l)
    run_env = {**os.environ, **env, "VAULT_ADDR": "https://127.0.0.1:8200", "VAULT_CACERT": CA}
    before = httpx.get("https://127.0.0.1:8200/v1/secret/data/internal/inventory/gateway", verify=CA,
                       headers={"X-Vault-Token": env["VAULT_ROOT_TOKEN"]}).json()["data"]["data"]["token"]
    subprocess.run([sys.executable, str(ROOT / "scripts" / "vault_init.py"), "--rotate", "internal/inventory/gateway"],
                   env=run_env, check=True, capture_output=True)
    after = httpx.get("https://127.0.0.1:8200/v1/secret/data/internal/inventory/gateway", verify=CA,
                      headers={"X-Vault-Token": env["VAULT_ROOT_TOKEN"]}).json()["data"]["data"]["token"]
    assert before != after
    # La credencial nueva funciona de inmediato (inventory relee Vault ante un token desconocido).
    new = httpx.get("https://127.0.0.1:9103/products", verify=CA, headers={"X-Caller-Id": "gateway", "X-Service-Token": after})
    assert new.status_code == 200
    # Durante el cambio el gateway sigue operando sin reinicio (si recibe 401 relee y reintenta).
    for _ in range(3):
        assert anon.get("/products").status_code == 200
    # Pasado el tiempo de caché (perfil de pruebas: 10 s) la credencial anterior queda inválida.
    time.sleep(11)
    old = httpx.get("https://127.0.0.1:9103/products", verify=CA, headers={"X-Caller-Id": "gateway", "X-Service-Token": before})
    assert old.status_code == 401
    assert anon.get("/products").status_code == 200


def _stub(cert="orders"):
    sys.path.insert(0, str(ROOT / "backend" / "services" / "orders"))
    import inventory_pb2 as pb
    import inventory_pb2_grpc as pbg
    d = CERTS_DIR / cert
    creds = grpc.ssl_channel_credentials(open(CA, "rb").read(), (d / "tls.key").read_bytes(), (d / "tls.crt").read_bytes())
    return pb, pbg.InventoryReservationsStub(grpc.secure_channel(INVENTORY_GRPC, creds))


def test_R05_grpc_reserva_idempotente_y_liberacion(admin):
    pb, stub = _stub()
    rid = f"test-{uuid.uuid4()}"
    before = stock_of(admin, "purafe-tinto")
    req = pb.ReserveRequest(reservation_id=rid, items=[pb.ItemQuantity(product_id="purafe-tinto", quantity=2)])
    assert stub.ReserveStock(req, timeout=2).status == "HELD"
    assert stub.ReserveStock(req, timeout=2).status == "HELD"  # repetir no descuenta de nuevo
    assert stock_of(admin, "purafe-tinto") == before - 2
    ref = pb.ReservationRef(reservation_id=rid, reason="prueba")
    assert stub.ReleaseReservation(ref, timeout=2).status == "RELEASED"
    assert stub.ReleaseReservation(ref, timeout=2).status == "RELEASED"  # idempotente
    assert stock_of(admin, "purafe-tinto") == before
    with pytest.raises(grpc.RpcError) as err:
        stub.CommitReservation(ref, timeout=2)  # no se confirma una reserva liberada
    assert err.value.code() == grpc.StatusCode.FAILED_PRECONDITION


def test_R06_grpc_validacion_y_plazo():
    pb, stub = _stub()
    with pytest.raises(grpc.RpcError) as err:
        stub.QuoteItems(pb.QuoteRequest(items=[pb.ItemQuantity(product_id="kuyen-tinto", quantity=999)]), timeout=1)
    assert err.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    with pytest.raises(grpc.RpcError) as err:
        stub.QuoteItems(pb.QuoteRequest(items=[pb.ItemQuantity(product_id="kuyen-tinto", quantity=1)]), timeout=0.001)
    assert err.value.code() == grpc.StatusCode.DEADLINE_EXCEEDED


@local_only
def test_R07_reinicio_de_inventory_grpc_se_reconecta(client_a):
    restart_service("inventory")
    for _ in range(20):
        r = create_order(client_a, [{"productoId": "pinot-rosado", "cantidad": 1}])
        if r.status_code == 201:
            break
        time.sleep(0.5)
    assert r.status_code == 201
    client_a.post(f"/orders/{r.json()['id']}/cancel")
