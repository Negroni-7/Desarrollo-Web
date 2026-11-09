"""Patrón outbox: los eventos se guardan en la base del servicio junto con el
cambio de estado y un hilo los entrega a analytics con reintentos.
Analytics descarta duplicados por eventId, así que reenviar es seguro."""
import logging
import threading
import time
import uuid
from datetime import datetime, timezone

from .internal import ServiceClient

log = logging.getLogger("vu.outbox")


def new_event(tipo: str, datos: dict) -> dict:
    return {
        "_id": str(uuid.uuid4()),
        "tipo": tipo,
        "ocurridoEn": datetime.now(timezone.utc).isoformat(),
        "datos": datos,
        "enviado": False,
        "intentos": 0,
    }


def start_dispatcher(get_db, interval: float = 2.0):
    client = ServiceClient("analytics", timeout=3.0)

    def loop():
        while True:
            try:
                db = get_db()
                for ev in db.outbox.find({"enviado": False}).sort("ocurridoEn", 1).limit(50):
                    payload = {"eventId": ev["_id"], "tipo": ev["tipo"], "ocurridoEn": ev["ocurridoEn"], "datos": ev["datos"]}
                    try:
                        resp = client.request("POST", "/internal/events", json=payload)
                        ok = resp.status_code in (200, 201)
                    except Exception:
                        ok = False
                    if ok:
                        db.outbox.update_one({"_id": ev["_id"]}, {"$set": {"enviado": True}})
                    else:
                        db.outbox.update_one({"_id": ev["_id"]}, {"$inc": {"intentos": 1}})
                        break  # analytics no disponible: se reintenta en el próximo ciclo
            except Exception as exc:
                log.warning("outbox_cycle_error err=%s", type(exc).__name__)
            time.sleep(interval)

    threading.Thread(target=loop, daemon=True, name="outbox").start()
