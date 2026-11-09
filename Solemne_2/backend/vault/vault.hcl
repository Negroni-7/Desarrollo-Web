# Listener TLS de Vault (el modo dev agrega un listener HTTP sólo en 127.0.0.1 del contenedor)
listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_cert_file = "/certs/tls.crt"
  tls_key_file  = "/certs/tls.key"
}
disable_mlock = true
