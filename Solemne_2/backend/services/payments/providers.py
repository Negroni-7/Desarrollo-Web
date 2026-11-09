"""Adaptadores de proveedor de pago.

SandboxProvider: proveedor de prueba propio (backend/services/sandbox) que
replica el contrato de una pasarela tipo Webpay: crear transacción ->
redirigir al comprador -> el comercio confirma el resultado consultando al
proveedor (servidor a servidor) y además recibe una notificación firmada.

TransbankProvider: adaptador para el ambiente de integración de Webpay Plus.
Se activa con PAYMENT_PROVIDER=transbank. No se ejecutó en las pruebas de esta
entrega porque el entorno de pruebas no tiene salida a Internet (ver informe).
"""
import os

import httpx

from vu_common import settings
from vu_common.errors import DependencyError
from vu_common.vault import vault


class SandboxProvider:
    name = "sandbox"

    def __init__(self):
        self.base = os.getenv("PROVIDER_API_URL", "https://sandbox:8000").rstrip("/")

    def _headers(self):
        s = vault.read("payments/provider")
        return {"Api-Key-Id": s["api_key_id"], "Api-Key-Secret": s["api_key_secret"]}

    def create(self, buy_order: str, session_id: str, amount: int, return_url: str) -> dict:
        try:
            r = httpx.post(f"{self.base}/api/v1/transactions", headers=self._headers(), timeout=5.0,
                           verify=settings.verify_param(),
                           json={"buy_order": buy_order, "session_id": session_id, "amount": amount, "return_url": return_url})
        except httpx.HTTPError:
            raise DependencyError("proveedor de pagos")
        if r.status_code != 201:
            raise DependencyError("proveedor de pagos")
        data = r.json()
        return {"token": data["token"], "redirect_url": data["url"]}

    def status(self, token: str) -> dict:
        try:
            r = httpx.get(f"{self.base}/api/v1/transactions/{token}", headers=self._headers(), timeout=5.0,
                          verify=settings.verify_param())
        except httpx.HTTPError:
            raise DependencyError("proveedor de pagos")
        if r.status_code != 200:
            raise DependencyError("proveedor de pagos")
        data = r.json()
        mapping = {"AUTHORIZED": "APROBADO", "REJECTED": "RECHAZADO", "PENDING": "INICIADO"}
        return {"resultado": mapping.get(data["status"], "INICIADO"), "monto": data["amount"]}


class TransbankProvider:
    """Webpay Plus REST v1.2 (ambiente de integración)."""
    name = "transbank"

    def __init__(self):
        self.base = os.getenv("TRANSBANK_API_URL",
                              "https://webpay3gint.transbank.cl/rswebpaytransaction/api/webpay/v1.2").rstrip("/")

    def _headers(self):
        s = vault.read("payments/transbank")
        return {"Tbk-Api-Key-Id": s["commerce_code"], "Tbk-Api-Key-Secret": s["api_key"]}

    def create(self, buy_order, session_id, amount, return_url):
        try:
            r = httpx.post(f"{self.base}/transactions", headers=self._headers(), timeout=8.0,
                           json={"buy_order": buy_order, "session_id": session_id, "amount": amount, "return_url": return_url})
            r.raise_for_status()
        except httpx.HTTPError:
            raise DependencyError("Transbank")
        data = r.json()
        return {"token": data["token"], "redirect_url": f"{data['url']}?token_ws={data['token']}"}

    def status(self, token):
        try:
            r = httpx.put(f"{self.base}/transactions/{token}", headers=self._headers(), timeout=8.0)
            r.raise_for_status()
        except httpx.HTTPError:
            raise DependencyError("Transbank")
        data = r.json()
        ok = data.get("status") == "AUTHORIZED" and data.get("response_code") == 0
        return {"resultado": "APROBADO" if ok else "RECHAZADO", "monto": int(data.get("amount", 0))}


def get_provider():
    return TransbankProvider() if os.getenv("PAYMENT_PROVIDER", "sandbox") == "transbank" else SandboxProvider()
