# Evaluación 2 — Backend seguro completo · Viña Urbana

Backend completo y seguro de **Viña Urbana** (tienda de vinos boutique): cuentas de usuario, catálogo, carrito,
pedidos, pagos con boleta, reservas de degustación, contacto, administración y reportes.

> **Alcance (indicación del docente):** la entrega es el backend **con los datos del frontend**, no el frontend integrado.
> El frontend v1.0 (`../Entrega_Frontend`) no se modifica: `scripts/extraer_datos_frontend.py` toma de su `index.html`
> los vinos, precios, recomendados, paquetes, horarios, asuntos y reglas, y con eso se cargan la base y se definen los contratos.

- Informe de arquitectura (10 módulos): se entrega por separado en PDF.
- Esta guía explica cómo **instalar, ejecutar y probar** el sistema paso a paso.

---

## Índice

1. [Qué se va a levantar](#1-qué-se-va-a-levantar)
2. [Requisitos](#2-requisitos)
3. [Ejecutar con Docker (recomendado)](#3-ejecutar-con-docker-recomendado)
4. [Probar la API desde la terminal (curl)](#4-probar-la-api-desde-la-terminal-curl)
5. [Probar con Postman (recomendado para la presentación)](#5-probar-con-postman-recomendado-para-la-presentación)
6. [Ejecutar las pruebas automáticas](#6-ejecutar-las-pruebas-automáticas)
7. [Detener y reiniciar](#7-detener-y-reiniciar)
8. [Problemas frecuentes](#8-problemas-frecuentes)
9. [Ejecutar sin Docker (modo local)](#9-ejecutar-sin-docker-modo-local)
10. [Referencia técnica](#10-referencia-técnica)

---

## 1. Qué se va a levantar

Con un solo comando se inician 13 contenedores:

| Componente | Qué hace | ¿Accesible desde tu PC? |
|---|---|---|
| `gateway` | API Gateway: única puerta de entrada a la API | **Sí** → https://localhost:8443 |
| `sandbox` | Proveedor de pagos de prueba (simula un banco) | **Sí** → https://localhost:8090 |
| `auth`, `clients`, `inventory`, `orders`, `payments`, `tastings`, `analytics` | Microservicios del negocio | No (red interna) |
| `graphql` | GraphQL Gateway privado (junta datos de varios servicios) | No (red interna) |
| `mongo` | Base de datos MongoDB | No (red interna) |
| `vault` | Caja fuerte de secretos (HashiCorp Vault) | No (red interna) |
| `vault-init` | Se ejecuta una vez: crea secretos, usuarios de BD y carga los datos del frontend | — |

Todo lo que pruebes pasa por el gateway: `https://localhost:8443/api/v1/...`

## 2. Requisitos

| Necesitas | Para qué |
|---|---|
| **Docker** con Docker Compose v2 | Levantar todos los servicios |
| **Python 3.10 o superior** con el paquete `cryptography` | Ejecutar `scripts/setup.py` (genera contraseñas y certificados) |
| **Postman** (opcional) | Probar la API con una interfaz gráfica |

### Linux (Arch / CachyOS / Manjaro)

```bash
sudo pacman -S docker docker-compose docker-buildx python-cryptography
sudo systemctl enable --now docker
sudo usermod -aG docker $USER      # luego cierra sesión y vuelve a entrar
```

### Linux (Ubuntu / Debian / Mint)

```bash
sudo apt install docker.io docker-compose-v2 python3-cryptography
sudo systemctl enable --now docker
sudo usermod -aG docker $USER      # luego cierra sesión y vuelve a entrar
```

### Windows o macOS

1. Instala **Docker Desktop** (https://www.docker.com/products/docker-desktop) y ábrelo.
2. Instala **Python** (https://www.python.org; en Windows marca "Add Python to PATH").
3. En una terminal: `pip install cryptography`

Comprueba que todo está listo:

```bash
docker --version
docker compose version
python --version          # en algunos Linux es: python3 --version
```

## 3. Ejecutar con Docker (recomendado)

Abre una terminal **dentro de la carpeta `Solemne_2`** y ejecuta:

```bash
# Paso 1 (solo la primera vez): genera contraseñas aleatorias, certificados TLS y carpetas
python scripts/setup.py

# Paso 2: construye e inicia todo en segundo plano (la primera vez tarda entre 5 y 10 minutos)
docker compose up --build -d

# Paso 3: revisa el estado; espera hasta que "gateway" diga (healthy)
docker compose ps
```

Cuando el gateway esté `healthy`, abre en el navegador **https://localhost:8443/api/v1/products**.
El navegador mostrará una advertencia de certificado (es un certificado interno del proyecto): elige
"Avanzado → Continuar". Deberías ver el catálogo de 9 vinos en formato JSON.

### Usuarios de prueba

Las contraseñas se generan al azar en el paso 1. Para verlas:

```bash
cat runtime/seed-out/seed_credentials.txt        # Windows PowerShell: type runtime\seed-out\seed_credentials.txt
```

| Usuario | Rol | Puede |
|---|---|---|
| `cliente.demo@correo.cl` | CLIENTE | Comprar, pagar, reservar, ver sus pedidos |
| `admin@vinaurbana.cl` | ADMIN | Administrar catálogo, stock, despachos, mensajes y ver reportes |
| `sommelier@vinaurbana.cl` | SOMMELIER | Ver y gestionar las reservas de degustación |

También puedes crear tu propio cliente con el registro (paso 4.3 o carpeta 2 de Postman).

## 4. Probar la API desde la terminal (curl)

> Estos comandos funcionan en Linux, macOS y en Git Bash de Windows. En PowerShell es más cómodo usar Postman (sección 5).
> `-k` acepta el certificado interno. Las operaciones que no son GET deben llevar la cabecera
> `X-Requested-With: XMLHttpRequest` (protección CSRF).

### 4.1 Catálogo (público)

```bash
curl -k https://localhost:8443/api/v1/products
curl -k "https://localhost:8443/api/v1/products?tipo=tinto"
curl -k "https://localhost:8443/api/v1/products?recomendado=true"
```

### 4.2 Cotizar un carrito (el servidor calcula precios y despacho)

```bash
curl -k -X POST https://localhost:8443/api/v1/orders/quote \
  -H "Content-Type: application/json" -H "X-Requested-With: XMLHttpRequest" \
  -d '{"items":[{"productoId":"kuyen-tinto","cantidad":2}],"destino":{"comuna":"Providencia","region":"Metropolitana"}}'
```

Resultado esperado: subtotal 64.000 y despacho 0 (gratis sobre $50.000 en Providencia).

### 4.3 Crear una cuenta e iniciar sesión

```bash
# Registro (la fecha de nacimiento debe ser de un mayor de 18 años)
curl -k -X POST https://localhost:8443/api/v1/auth/register \
  -H "Content-Type: application/json" -H "X-Requested-With: XMLHttpRequest" \
  -d '{"nombre":"Ana Pérez","email":"ana@correo.cl","password":"ClaveSegura2026","fechaNacimiento":"1998-03-10","aceptaTerminos":true}'

# Login: la sesión queda guardada en el archivo sesion.txt
curl -k -c sesion.txt -X POST https://localhost:8443/api/v1/auth/login \
  -H "Content-Type: application/json" -H "X-Requested-With: XMLHttpRequest" \
  -d '{"email":"ana@correo.cl","password":"ClaveSegura2026"}'

# Ver mi perfil usando la sesión
curl -k -b sesion.txt https://localhost:8443/api/v1/clients/me
```

### 4.4 Comprar y pagar

```bash
# Crear el pedido (copia el "id" de la respuesta)
curl -k -b sesion.txt -X POST https://localhost:8443/api/v1/orders \
  -H "Content-Type: application/json" -H "X-Requested-With: XMLHttpRequest" \
  -H "Idempotency-Key: $(python -c 'import uuid;print(uuid.uuid4())')" \
  -d '{"items":[{"productoId":"kuyen-tinto","cantidad":1}],"entrega":{"nombreReceptor":"Ana Pérez","calle":"Av. Providencia","numero":"1500","comuna":"Providencia","region":"Metropolitana","telefono":"+56955551234"}}'

# Iniciar el pago (reemplaza ID_DEL_PEDIDO; copia "pagoId" y "redirectUrl")
curl -k -b sesion.txt -X POST https://localhost:8443/api/v1/payments \
  -H "Content-Type: application/json" -H "X-Requested-With: XMLHttpRequest" \
  -d '{"pedidoId":"ID_DEL_PEDIDO"}'
```

1. Abre el `redirectUrl` en el navegador (página del banco de prueba) y presiona **"Pagar con tarjeta de prueba"**.
2. Luego verifica el pago (reemplaza `ID_DEL_PAGO`):

```bash
curl -k -b sesion.txt -X POST https://localhost:8443/api/v1/payments/ID_DEL_PAGO/verify \
  -H "X-Requested-With: XMLHttpRequest"
```

Resultado esperado: `"estado": "APROBADO"` y una boleta con folio, neto e IVA.

### 4.5 Ver mis pedidos con GraphQL (orders + inventory + payments en una consulta)

```bash
curl -k -b sesion.txt -X POST https://localhost:8443/api/v1/graphql \
  -H "Content-Type: application/json" -H "X-Requested-With: XMLHttpRequest" \
  -d '{"query":"{ misPedidos { total items { numero estado total pago { estado boleta { folio total } } } } }"}'
```

### 4.6 Comprobar la seguridad

```bash
# Sin sesión → 401
curl -k https://localhost:8443/api/v1/clients/me

# Un cliente intentando administrar → 403
curl -k -b sesion.txt https://localhost:8443/api/v1/admin/products

# Intentar fijar el total desde el cliente → 400
curl -k -b sesion.txt -X POST https://localhost:8443/api/v1/orders \
  -H "Content-Type: application/json" -H "X-Requested-With: XMLHttpRequest" -H "Idempotency-Key: 11111111-2222-3333-4444-555555555555" \
  -d '{"items":[{"productoId":"kuyen-tinto","cantidad":1}],"total":1,"entrega":{"nombreReceptor":"X","calle":"X","numero":"1","comuna":"Providencia","region":"Metropolitana","telefono":"+56911112222"}}'
```

## 5. Probar con Postman (recomendado para la presentación)

1. Abre Postman → **Import** → elige `docs/postman/VinaUrbana.postman_collection.json`.
2. **Settings → General → SSL certificate verification: OFF** (el certificado es interno).
3. Abre la colección → pestaña **Variables** → en `passwordAdmin` pega la contraseña del admin (`runtime/seed-out/seed_credentials.txt`).
4. Ejecuta las carpetas **en orden**:

| Carpeta | Qué muestra |
|---|---|
| 1. Público | Catálogo, filtros, cotización, paquetes, cupos y contacto (sin sesión) |
| 2. Cuenta de cliente | Registro → Login (la cookie de sesión queda guardada sola) → perfil |
| 3. Compra y pago | Crear pedido → iniciar pago → **abre el `redirectUrl` en el navegador y paga** → verificar pago → GraphQL mis pedidos |
| 4. Degustaciones | Reservar y ver mis reservas |
| 5. Administración | Login admin → inventario, stock, pedidos, despacho, reservas, mensajes, panel de ventas → cerrar sesión |

Las variables `pedidoId` y `pagoId` se completan automáticamente al crear el pedido y el pago.

## 6. Ejecutar las pruebas automáticas

Con el sistema levantado:

```bash
docker compose --profile test run --rm tests
```

Ejecuta las pruebas de contratos, datos del frontend, seguridad (casos V1-V6), flujos de compra y pago, GraphQL y gRPC.
Algunas pruebas de fallos (detener servicios, rotar secretos) sólo corren en el modo local (sección 9) y en Docker
aparecen como *skipped*.

Resultados de la ejecución entregada (modo local): `docs/evidencias/pruebas/` (97/97 aprobadas),
`docs/evidencias/demo_api/flujos.md` (49/49 pasos) y `docs/evidencias/carga/` (prueba de carga).

## 7. Detener y reiniciar

```bash
docker compose stop              # detiene sin borrar nada
docker compose start             # vuelve a iniciar
docker compose down              # detiene y elimina los contenedores (los datos se conservan)
docker compose down -v           # además borra la base de datos (vuelve al estado inicial)
docker compose logs -f gateway   # ver los registros de un servicio en vivo
```

## 8. Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `permission denied ... docker.sock` | No cerraste sesión tras `usermod -aG docker`. Cierra sesión o usa `sudo docker compose ...` |
| `ModuleNotFoundError: cryptography` al ejecutar `setup.py` | Instala el paquete: `pip install cryptography` (Arch: `sudo pacman -S python-cryptography`) |
| `port is already allocated` (8443 u 8090) | Otro programa usa ese puerto. Ciérralo o cambia el puerto en `docker-compose.yml` (`ports`) |
| Un servicio no llega a `healthy` | `docker compose logs nombre_servicio` y revisa el error. Luego `docker compose up -d` |
| `vault-init` termina con error | Espera a que `mongo` y `vault` estén `healthy` y ejecuta `docker compose up -d` de nuevo |
| Respuesta `403 CSRF_CHECK_FAILED` | Falta la cabecera `X-Requested-With: XMLHttpRequest` en un POST/PUT/PATCH/DELETE |
| Respuesta `401` después de un rato | La sesión dura 30 minutos: vuelve a iniciar sesión |
| Respuesta `429` en contacto o login | Límite de solicitudes por minuto: espera 1 minuto |
| El pedido pasó a `CANCELADO` solo | No se pagó en 15 minutos: el sistema lo anula y devuelve el stock (comportamiento esperado) |
| Quiero empezar de cero | `docker compose down -v`, borra la carpeta `runtime/` y el archivo `.env`, y repite la sección 3 |

## 9. Ejecutar sin Docker (modo local)

Es el modo con el que se ejecutaron las pruebas entregadas. Requiere Python 3.12+, Node 20+, MongoDB 7/8 (`mongod`)
y HashiCorp Vault (`vault`) instalados (o sus rutas en las variables `MONGOD_BIN` y `VAULT_BIN`).

```bash
pip install -r backend/requirements.txt cryptography pytest psutil
(cd backend/gql-gateway && npm ci)
python scripts/setup.py
python scripts/run_local.py                 # o --test-profile (plazo de pago 25 s, caché de secretos 10 s)
pytest tests -v                             # 97 pruebas
python tests/demo_api.py                    # demostración de 49 pasos → docs/evidencias/demo_api/flujos.md
python scripts/stop_local.py                # detener
```

Entre `demo_api.py` y `pytest` espera 1 minuto (el contacto admite 5 solicitudes por minuto por IP).
Credenciales en modo local: `runtime/seed_credentials.txt`.

Prueba de carga: `RATE_LIMIT_MULTIPLIER=1000 python scripts/run_local.py --test-profile && python tests/load_test.py`.

---

## 10. Referencia técnica

### Estructura del proyecto

| Carpeta | Contenido |
|---|---|
| `scripts/datos_frontend.json` | Datos extraídos del frontend v1.0 (fuente del seed y de las pruebas D01-D07) |
| `backend/services/gateway` | API Gateway (FastAPI): único punto público, rutas explícitas, authN/authZ, CSRF, límites, TLS |
| `backend/services/auth` | Auth Service: registro, login, sesiones revocables, Argon2id |
| `backend/services/{clients,inventory,orders,payments,tastings,analytics}` | Microservicios privados, cada uno con su base MongoDB |
| `backend/services/inventory/grpc_server.py` + `backend/proto/inventory.proto` | gRPC (mTLS) orders → inventory |
| `backend/gql-gateway` | GraphQL Gateway privado (Node + Apollo) con agregaciones |
| `backend/services/sandbox` | Proveedor de pagos simulado (adaptador de prueba; representa a un tercero) |
| `scripts/` | `setup.py`, `extraer_datos_frontend.py`, `vault_init.py`, `seed_data.py`, `run_local.py`, `stop_local.py`, `generar_coleccion_postman.py` |
| `tests/` | Pruebas automatizadas (pytest), demostración vía API (`demo_api.py`) y prueba de carga (`load_test.py`) |
| `docs/` | Diagramas editables (`.drawio`, `.mmd`, `.png`), colección Postman y evidencias de ejecución |

### Rutas principales (todas bajo `https://localhost:8443/api/v1`)

| Método y ruta | Acceso | Para qué |
|---|---|---|
| `GET /products` | Público | Catálogo (filtros `tipo`, `recomendado`) |
| `POST /orders/quote` | Público | Cotizar carrito y despacho |
| `POST /auth/register`, `POST /auth/login`, `POST /auth/logout` | Público / sesión | Cuenta y sesión |
| `GET/PUT/DELETE /clients/me` | Cliente | Perfil propio |
| `POST /orders`, `POST /orders/{id}/cancel` | Cliente | Crear y anular pedidos |
| `POST /payments`, `POST /payments/{id}/verify` | Cliente | Pagar y verificar |
| `GET /tastings/packages`, `GET /tastings/availability`, `POST /tastings/reservations` | Público / cliente | Degustaciones |
| `POST /contact` | Público | Mensaje de contacto |
| `POST /graphql` | Sesión | `misPedidos`, `resumenPedido`, `panelVentas` |
| `/admin/...` | Admin / sommelier | Catálogo, stock, despachos, reservas, mensajes |

El catálogo completo de los 34 servicios con sus contratos está en el módulo 1 del informe.

### Secretos

- No hay secretos en el repositorio. `.env` y `runtime/` están en `.gitignore`; `.env.example` sólo tiene referencias.
- `vault-init` genera los secretos al azar, crea una política y un token de Vault por servicio, y un usuario de
  MongoDB por servicio (permiso sólo sobre su base).
- Rotar una credencial entre servicios sin reiniciar:
  `docker compose run --rm vault-init python /scripts/vault_init.py --rotate internal/inventory/gateway`
  (o `auth/jwt` para la llave de firma de sesiones; la anterior se acepta mientras vencen los tokens).
- Vault corre en **modo desarrollo** (memoria): al reiniciarlo, `vault-init` regenera todo. En producción se usaría
  almacenamiento persistente, unseal y auto-auth (AppRole/Kubernetes). El modo dev imprime su token raíz en su log.

### Health checks y logs

Cada servicio expone `GET /health` (incluye verificación de su base). Los logs son JSON con `request_id`
(correlación extremo a extremo vía `X-Request-Id`) y nunca incluyen cuerpos, tokens ni contraseñas.

### Pagos

Por defecto se usa el proveedor simulado (`PAYMENT_PROVIDER=sandbox`). Existe un adaptador para el ambiente de
integración de Transbank Webpay Plus (`PAYMENT_PROVIDER=transbank` + `TRANSBANK_COMMERCE_CODE` / `TRANSBANK_API_KEY`
en `.env`), no ejecutado en las pruebas por falta de salida a Internet en el entorno de pruebas.

### Nota sobre la verificación

Las pruebas entregadas se ejecutaron en modo local (mismos servicios, TLS y puertos, sin contenedores), porque el
entorno donde se construyó no tenía Docker disponible. `docker-compose.yml` fue validado con `docker compose config`.
