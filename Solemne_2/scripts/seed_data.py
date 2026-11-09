"""Carga datos de prueba FICTICIOS (idempotente).

- Catálogo y paquetes: tomados de scripts/datos_frontend.json, extraído del
  frontend v1.0 (la entrega es sólo backend con datos del frontend).
- Usuarios: administrador, sommelier y un cliente demo. Las contraseñas vienen
  de .env (generadas al azar por setup.py) y se escriben en
  runtime/seed_credentials.txt, que no se sube al repositorio.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from argon2 import PasswordHasher
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parent.parent
hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
NOW = datetime.now(timezone.utc)

# Fuente: datos extraídos del frontend v1.0 (ver extraer_datos_frontend.py).
DATOS = json.loads((Path(__file__).resolve().parent / "datos_frontend.json").read_text(encoding="utf-8"))


def load_env():
    env = {}
    dotenv = ROOT / ".env"
    lines = dotenv.read_text(encoding="utf-8").splitlines() if dotenv.exists() else []
    for line in lines:
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return {**env, **os.environ}


def main():
    env = load_env()
    kw = {"tls": True, "tlsCAFile": env["MONGO_TLS_CA"]} if env.get("MONGO_TLS_CA") else {}
    client = MongoClient(f"mongodb://{env['MONGO_ROOT_USER']}:{env['MONGO_ROOT_PASSWORD']}@{env.get('MONGO_ADMIN_HOST', '127.0.0.1:27017')}/"
                         "?authSource=admin", serverSelectionTimeoutMS=20000, **kw)
    inv = client["vu_inventory"]
    for v in DATOS["vinos"]:
        inv.products.update_one({"_id": v["id"]}, {"$setOnInsert": {
            "nombre": v["nombre"], "tipo": v["tipo"], "vina": v["vina"], "volumenMl": v["volumenMl"],
            "gradoAlcohol": v["gradoAlcohol"], "precio": v["precio"], "imagen": v["imagen"], "recomendado": v["recomendado"],
            "activo": True, "stock": v["stockInicial"], "creadoEn": NOW, "actualizadoEn": NOW}}, upsert=True)
    tastings = client["vu_tastings"]
    for p in DATOS["paquetes"]:
        tastings.packages.update_one({"_id": p["id"]}, {"$setOnInsert": {
            "nombre": p["nombre"], "descripcion": p["descripcion"], "incluye": p["incluye"], "duracionMin": p["duracionMin"],
            "precioPorPersona": p["precioPorPersona"], "imagen": p["imagen"], "activo": True}}, upsert=True)

    users = [("admin@vinaurbana.cl", "ADMIN", env["SEED_ADMIN_PASSWORD"], None),
             ("sommelier@vinaurbana.cl", "SOMMELIER", env["SEED_SOMMELIER_PASSWORD"], None),
             ("cliente.demo@correo.cl", "CLIENTE", env["SEED_CLIENT_PASSWORD"], "Camila Demo")]
    auth, clients = client["vu_auth"], client["vu_clients"]
    for email, rol, pwd, nombre in users:
        existing = auth.credentials.find_one({"email": email})
        uid = existing["_id"] if existing else str(uuid.uuid4())
        if not existing:
            auth.credentials.insert_one({"_id": uid, "email": email, "passwordHash": hasher.hash(pwd), "rol": rol,
                                         "estado": "ACTIVO", "intentosFallidos": 0, "bloqueadoHasta": None, "creadoEn": NOW})
        if nombre:
            clients.profiles.update_one({"_id": uid}, {"$setOnInsert": {
                "nombre": nombre, "email": email, "telefono": "+56 9 1111 2222", "fechaNacimiento": "1995-04-12",
                "direccion": {"calle": "Av. Providencia", "numero": "1500", "depto": None, "comuna": "Providencia",
                              "region": "Metropolitana"}, "estado": "ACTIVO", "creadoEn": NOW}}, upsert=True)
    creds = Path(env.get("SEED_CREDENTIALS_FILE", ROOT / "runtime" / "seed_credentials.txt"))
    creds.write_text("".join(f"{rol:10} {email:28} {pwd}\n" for email, rol, pwd, _ in users), encoding="utf-8")
    print(f"✓ datos del frontend cargados: {len(DATOS['vinos'])} vinos, {len(DATOS['paquetes'])} paquetes; {len(users)} usuarios ficticios")
    print("  credenciales demo en runtime/seed_credentials.txt (no se suben al repositorio)")


if __name__ == "__main__":
    main()
