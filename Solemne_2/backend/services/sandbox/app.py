"""PagoSeguro Sandbox: adaptador de prueba que simula un proveedor externo.

No es parte del backend de Viña Urbana: representa al proveedor de pagos.
Preserva el contrato de una pasarela real:
  - API autenticada con credenciales del comercio (Api-Key-Id / Api-Key-Secret).
  - Página de pago propia (el comercio NUNCA ve datos de tarjeta).
  - Notificación al comercio firmada con HMAC-SHA256 y marca de tiempo.
  - Consulta de estado servidor a servidor.
No pide ni guarda números de tarjeta: se aprueba o rechaza con botones.
"""
import hashlib
import hmac
import html
import json
import logging
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from fastapi import Form, Header, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from vu_common import settings
from vu_common.db import get_db
from vu_common.errors import ApiError
from vu_common.server import create_app, serve
from vu_common.vault import vault

log = logging.getLogger("vu.sandbox")
app = create_app("PagoSeguro Sandbox (proveedor externo simulado)", health_check=lambda: get_db().command("ping"))

PUBLIC_URL = os.getenv("SANDBOX_PUBLIC_URL", "https://localhost:8090").rstrip("/")
WEBHOOK_URL = os.getenv("MERCHANT_WEBHOOK_URL", "https://gateway:8443/api/v1/payments/webhook")
ALLOWED_RETURN_HOSTS = {h.strip() for h in os.getenv("ALLOWED_RETURN_HOSTS", "localhost,127.0.0.1").split(",")}


def _merchant():
    return vault.read("sandbox/merchant")


def _check_merchant(key_id: str, key_secret: str):
    m = _merchant()
    if not (secrets.compare_digest(key_id, m["api_key_id"]) and secrets.compare_digest(key_secret, m["api_key_secret"])):
        raise ApiError(401, "INVALID_MERCHANT", "Credenciales de comercio inválidas")


class TxIn(BaseModel):
    buy_order: str = Field(min_length=1, max_length=26)
    session_id: str = Field(min_length=1, max_length=61)
    amount: int = Field(ge=50, le=10_000_000)
    return_url: str = Field(max_length=256)


@app.post("/api/v1/transactions", status_code=201)
def create_tx(body: TxIn, api_key_id: str = Header(default=""), api_key_secret: str = Header(default="")):
    _check_merchant(api_key_id, api_key_secret)
    parsed = urlparse(body.return_url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ALLOWED_RETURN_HOSTS:
        raise ApiError(400, "INVALID_RETURN_URL", "URL de retorno no registrada para el comercio")
    token = uuid.uuid4().hex
    get_db().transactions.insert_one({"_id": token, **body.model_dump(), "status": "PENDING",
                                      "createdAt": datetime.now(timezone.utc)})
    return {"token": token, "url": f"{PUBLIC_URL}/pay/{token}"}


@app.get("/api/v1/transactions/{token}")
def get_tx(token: str, api_key_id: str = Header(default=""), api_key_secret: str = Header(default="")):
    _check_merchant(api_key_id, api_key_secret)
    tx = get_db().transactions.find_one({"_id": token})
    if not tx:
        raise ApiError(404, "NOT_FOUND", "Transacción inexistente")
    return {"token": token, "status": tx["status"], "amount": tx["amount"], "buy_order": tx["buy_order"],
            "authorization_code": tx.get("authorization_code")}


@app.get("/pay/{token}", response_class=HTMLResponse)
def pay_page(token: str):
    tx = get_db().transactions.find_one({"_id": token})
    if not tx:
        return HTMLResponse("<h1>Transacción inexistente</h1>", status_code=404)
    amount = f"${tx['amount']:,}".replace(",", ".")
    done = tx["status"] != "PENDING"
    buttons = "" if done else f"""
      <form method="post" action="/pay/{token}/decision">
        <button name="decision" value="approve" class="ok">Pagar con tarjeta de prueba (aprobar)</button>
        <button name="decision" value="reject" class="no">Simular rechazo</button>
      </form>"""
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>PagoSeguro Sandbox</title>
<style>body{{font-family:system-ui,sans-serif;background:#f1f3f5;display:flex;justify-content:center;padding:40px 16px}}
.card{{background:#fff;border-radius:12px;padding:28px;max-width:420px;width:100%;box-shadow:0 4px 20px #0001}}
button{{display:block;width:100%;padding:12px;margin-top:12px;border:0;border-radius:8px;font-size:16px;cursor:pointer}}
.ok{{background:#1b7f3b;color:#fff}}.no{{background:#e9ecef}} small{{color:#666}}</style></head>
<body><div class="card"><h2>PagoSeguro <small>(sandbox)</small></h2>
<p>Comercio: <b>Viña Urbana</b><br>Orden: <b>{html.escape(tx['buy_order'])}</b><br>Monto: <b>{amount} CLP</b></p>
<p><small>Ambiente de pruebas. No ingreses datos reales de tarjeta.</small></p>
{buttons}{"<p>Estado: <b>" + tx["status"] + "</b></p>" if done else ""}</div></body></html>"""


def _send_webhook(tx: dict, event_id: str | None = None):
    body = json.dumps({"event_id": event_id or uuid.uuid4().hex, "token": tx["_id"], "status": tx["status"],
                       "amount": tx["amount"], "buy_order": tx["buy_order"]}).encode()
    ts = str(int(time.time()))
    sig = "sha256=" + hmac.new(_merchant()["webhook_secret"].encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    try:
        r = httpx.post(WEBHOOK_URL, content=body, timeout=5.0, verify=settings.verify_param(),
                       headers={"Content-Type": "application/json", "X-Provider-Timestamp": ts, "X-Provider-Signature": sig})
        log.info("webhook_sent status=%s", r.status_code)
        return r.status_code
    except httpx.HTTPError as exc:
        log.warning("webhook_failed err=%s", type(exc).__name__)
        return None


@app.post("/pay/{token}/decision")
def decision(token: str, decision: str = Form(...)):
    db = get_db()
    status = "AUTHORIZED" if decision == "approve" else "REJECTED"
    tx = db.transactions.find_one_and_update(
        {"_id": token, "status": "PENDING"},
        {"$set": {"status": status, "authorization_code": secrets.token_hex(3) if status == "AUTHORIZED" else None,
                  "decidedAt": datetime.now(timezone.utc)}}, return_document=True)
    if not tx:
        tx = db.transactions.find_one({"_id": token})
        if not tx:
            return HTMLResponse("<h1>Transacción inexistente</h1>", status_code=404)
    else:
        event_id = uuid.uuid4().hex
        db.transactions.update_one({"_id": token}, {"$set": {"lastEventId": event_id}})
        _send_webhook(tx, event_id)
    return RedirectResponse(tx["return_url"], status_code=303)


@app.post("/sandbox/transactions/{token}/resend-webhook")
def resend(token: str):
    """Herramienta de prueba del proveedor simulado: reenvía la MISMA notificación
    firmada (mismo event_id) para comprobar que el comercio no procesa dos veces un
    pago. No expone datos: sólo devuelve el código HTTP que respondió el comercio."""
    tx = get_db().transactions.find_one({"_id": token})
    if not tx or tx["status"] == "PENDING":
        raise ApiError(404, "NOT_FOUND", "Sin notificación previa")
    return {"merchantStatus": _send_webhook(tx, tx.get("lastEventId"))}


if __name__ == "__main__":
    serve(app)
