"""Preparación del entorno (se ejecuta UNA vez antes de levantar el sistema).

1. Crea .env con valores aleatorios (contraseña raíz de Mongo, token raíz de
   Vault en modo dev, contraseñas de usuarios demo). .env está en .gitignore.
2. Genera una CA interna y un certificado TLS por componente en runtime/certs.
   La llave privada de la CA queda en runtime/ca-private y NO se monta en
   ningún contenedor.
3. Crea runtime/tokens/<servicio>/ donde vault-init dejará el token de Vault
   de cada servicio (cada contenedor monta sólo su carpeta).

Uso:  python scripts/setup.py            (no sobrescribe lo existente)
      python scripts/setup.py --force    (regenera certificados y .env)
"""
import datetime as dt
import ipaddress
import secrets
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "runtime"
COMPONENTS = ["gateway", "auth", "clients", "inventory", "orders", "payments", "tastings", "analytics",
              "graphql", "sandbox", "vault", "mongo"]
TOKEN_HOLDERS = ["gateway", "auth", "clients", "inventory", "orders", "payments", "tastings", "analytics",
                 "graphql", "sandbox"]
FORCE = "--force" in sys.argv


def write_env():
    env = ROOT / ".env"
    if env.exists() and not FORCE:
        print("· .env ya existe (usa --force para regenerarlo)")
        return
    values = {
        "MONGO_ROOT_USER": "vu_root",
        "MONGO_ROOT_PASSWORD": secrets.token_urlsafe(24),
        "VAULT_ROOT_TOKEN": "dev-" + secrets.token_urlsafe(24),
        "SEED_ADMIN_PASSWORD": "Adm" + secrets.token_urlsafe(9) + "9",
        "SEED_SOMMELIER_PASSWORD": "Som" + secrets.token_urlsafe(9) + "9",
        "SEED_CLIENT_PASSWORD": "Cli" + secrets.token_urlsafe(9) + "9",
        "PUBLIC_GATEWAY_URL": "https://localhost:8443",
        "PUBLIC_SANDBOX_URL": "https://localhost:8090",
    }
    env.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")
    print("✓ .env generado con valores aleatorios (no se sube al repositorio)")


def _key():
    return ec.generate_private_key(ec.SECP256R1())


def _pem_key(key) -> bytes:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def write_certs():
    certs = RUNTIME / "certs"
    ca_dir = RUNTIME / "ca-private"
    if (certs / "ca.crt").exists() and not FORCE:
        print("· certificados ya existen (usa --force para regenerarlos)")
        return
    certs.mkdir(parents=True, exist_ok=True)
    ca_dir.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    ca_key = _key()
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Vina Urbana Internal CA")])
    ca_cert = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
               .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(minutes=5))
               .not_valid_after(now + dt.timedelta(days=825))
               .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
               .add_extension(x509.KeyUsage(True, False, False, False, False, True, True, False, False), critical=True)
               .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
               .sign(ca_key, hashes.SHA256()))
    aki = x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key())
    (ca_dir / "ca.key").write_bytes(_pem_key(ca_key))
    (certs / "ca.crt").write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))

    for name in COMPONENTS:
        key = _key()
        sans = [x509.DNSName(name), x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
        cert = (x509.CertificateBuilder()
                .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
                .issuer_name(ca_name).public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(days=90))
                .add_extension(x509.SubjectAlternativeName(sans), critical=False)
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(aki, critical=False)
                .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
                .add_extension(x509.KeyUsage(True, False, True, False, True, False, False, False, False), critical=True)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]),
                               critical=False)
                .sign(ca_key, hashes.SHA256()))
        d = certs / name
        d.mkdir(exist_ok=True)
        crt = cert.public_bytes(serialization.Encoding.PEM)
        (d / "tls.crt").write_bytes(crt)
        (d / "tls.key").write_bytes(_pem_key(key))
        (d / "ca.crt").write_bytes((certs / "ca.crt").read_bytes())
        if name == "mongo":
            (d / "mongo.pem").write_bytes(crt + _pem_key(key))
    print(f"✓ CA interna y {len(COMPONENTS)} certificados (90 días) en runtime/certs")


def write_dirs():
    for holder in TOKEN_HOLDERS:
        (RUNTIME / "tokens" / holder).mkdir(parents=True, exist_ok=True)
    (RUNTIME / "logs").mkdir(parents=True, exist_ok=True)
    (RUNTIME / "seed-out").mkdir(parents=True, exist_ok=True)
    print("✓ carpetas runtime/tokens/<servicio> creadas")


if __name__ == "__main__":
    RUNTIME.mkdir(exist_ok=True)
    write_env()
    write_certs()
    write_dirs()
    print("Listo. Siguiente paso: docker compose up --build   (o python scripts/run_local.py)")
