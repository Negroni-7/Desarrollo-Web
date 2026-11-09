# Evidencia de ejecución vía API — Viña Urbana
Generado por `tests/demo_api.py` el 08-11-2026 16:24. Todas las llamadas pasan por el API Gateway (https://localhost:8443). La entrega es sólo backend: se usan los datos del frontend v1.0 (`scripts/datos_frontend.json`) como datos y contratos; las cookies de sesión no se muestran.

## Resumen
**49 de 49 pasos con el resultado esperado.**
| # | Paso | Requisito | Servicio | Esperado | Obtenido | |
|---|---|---|---|---|---|---|
| 1 | Raíz informativa del gateway | — | — | 200 | 200 | ✅ |
| 2 | Catálogo completo (9 vinos del frontend) | R02 | S01 | 200 | 200 | ✅ |
| 3 | Filtro Tintos (botón del frontend) | R02 | S01 | 200 | 200 | ✅ |
| 4 | Recomendados (carrusel del frontend) | R03 | S01 | 200 | 200 | ✅ |
| 5 | Filtro inválido | R02 | S01 | 400 | 400 | ✅ |
| 6 | Cotizar carrito: 1 Kuyen + 2 Cipreses a Providencia | R04 R05 | S02 | 200 | 200 | ✅ |
| 7 | Cotizar a regiones (tarifa $6.990) | R05 | S02 | 200 | 200 | ✅ |
| 8 | Registro de cliente | R07 | S03 | 201 | 201 | ✅ |
| 9 | Registro de menor de edad (rechazado) | R01 | S03 | 422 | 422 | ✅ |
| 10 | Login con contraseña incorrecta | R07 | S04 | 401 | 401 | ✅ |
| 11 | Login correcto (sesión en cookie HttpOnly) | R07 | S04 | 200 | 200 | ✅ |
| 12 | Consultar sesión | R07 | S06 | 200 | 200 | ✅ |
| 13 | Guardar dirección en el perfil | R07 | S08 | 200 | 200 | ✅ |
| 14 | Pedido con total alterado por el cliente (rechazado) | R06 | S10 | 400 | 400 | ✅ |
| 15 | Crear pedido (stock reservado por gRPC) | R04 R05 | S10 | 201 | 201 | ✅ |
| 16 | Reintento con la misma Idempotency-Key (mismo pedido) | R06 | S10 | 200 | 200 | ✅ |
| 17 | Iniciar pago (monto lo fija orders) | R06 | S14 | 201 | 201 | ✅ |
| 18 | Verificar pago con el proveedor (boleta emitida) | R06 R12 | S15 | 200 | 200 | ✅ |
| 19 | Reenvío de la misma notificación del proveedor (sin efectos dobles) | R06 | S16 | 200 | 200 | ✅ |
| 20 | Intentar pagar de nuevo el mismo pedido | R06 | S14 | 409 | 409 | ✅ |
| 21 | Mis pedidos (una consulta, tres subsistemas) | R12 | S11 | 200 | 200 | ✅ |
| 22 | Campo restringido clienteId para un cliente | R12 | S11 | 200 | 200 | ✅ |
| 23 | Registro de un segundo cliente | R07 | S03 | 201 | 201 | ✅ |
| 24 | Login segundo cliente | R07 | S04 | 200 | 200 | ✅ |
| 25 | Otro cliente consulta el pedido de Ana (null, sin datos) | R12 | S12 | 200 | 200 | ✅ |
| 26 | Otro cliente intenta anular el pedido de Ana | R12 | S13 | 404 | 404 | ✅ |
| 27 | Acceso directo a orders sin identidad de servicio | — | interno | 401 | 401 | ✅ |
| 28 | Ruta interna por el gateway (no publicada) | — | gateway | 404 | 404 | ✅ |
| 29 | Paquetes del frontend | R08 | S17 | 200 | 200 | ✅ |
| 30 | Cupos por horario | R08 | S18 | 200 | 200 | ✅ |
| 31 | Reservar Maridaje Gourmet para 4 | R08 | S19 | 201 | 201 | ✅ |
| 32 | Mis reservas | R08 | S20 | 200 | 200 | ✅ |
| 33 | Mensaje del formulario de contacto | R09 | S22 | 201 | 201 | ✅ |
| 34 | Login administrador | R11 | S04 | 200 | 200 | ✅ |
| 35 | Cliente intenta administrar productos (denegado) | R11 | S23 | 403 | 403 | ✅ |
| 36 | Inventario con stock | R11 | S23 | 200 | 200 | ✅ |
| 37 | Ingreso de bodega +6 Almaviva | R11 | S26 | 200 | 200 | ✅ |
| 38 | Pedidos pagados | R11 | S28 | 200 | 200 | ✅ |
| 39 | Despacho → EN_PREPARACION | R11 R12 | S29 | 200 | 200 | ✅ |
| 40 | Despacho → DESPACHADO | R11 R12 | S29 | 200 | 200 | ✅ |
| 41 | Despacho → ENTREGADO | R11 R12 | S29 | 200 | 200 | ✅ |
| 42 | Transición inválida (ENTREGADO → EN_PREPARACION) | R11 | S29 | 409 | 409 | ✅ |
| 43 | Mensajes de contacto pendientes | R09 | S32 | 200 | 200 | ✅ |
| 44 | Panel de ventas GraphQL (analytics + inventory) | R13 | S34 | 200 | 200 | ✅ |
| 45 | Login sommelier | R08 | S04 | 200 | 200 | ✅ |
| 46 | Sommelier ve reservas con comentarios | R08 | S30 | 200 | 200 | ✅ |
| 47 | Sommelier intenta ver pedidos (denegado) | R11 | S28 | 403 | 403 | ✅ |
| 48 | Cerrar sesión | R07 | S05 | 200 | 200 | ✅ |
| 49 | Operación tras cerrar sesión | R07 | S07 | 401 | 401 | ✅ |


## 1. Catálogo con los datos del frontend

### 1. Raíz informativa del gateway

- Requisito: **—** · Servicio: **—** · Esperado: **200** · Obtenido: **200** → ✅

```http
GET /
```

```json
{
 "servicio": "Viña Urbana API",
 "version": "2.0",
 "base": "/api/v1",
 "documentacion": "docs/Informe_Evaluacion2_VinaUrbana.pdf (módulos 1 y 6)"
}
```

### 2. Catálogo completo (9 vinos del frontend)

- Requisito: **R02** · Servicio: **S01** · Esperado: **200** · Obtenido: **200** → ✅

```http
GET /api/v1/products
```

```json
{
 "items": [
  {
   "id": "almaviva-especial",
   "nombre": "Almaviva",
   "tipo": "especial",
   "vina": "Viña Almaviva",
   "volumenMl": 750,
   "gradoAlcohol": 15.0,
   "precio": 135000,
   "imagen": "images/vinos/almaviva-especial.jpg",
   "recomendado": true,
   "disponible": true
  },
  {
   "id": "chardonay-rosado",
   "nombre": "Chardonnay Reserva",
   "tipo": "rosado",
   "vina": "Viña Echeverría",
   "volumenMl": 750,
   "gradoAlcohol": 13.5,
   "precio": 18500,
   "imagen": "images/vinos/chardonay-rosado.jpg",
   "recomendado": true,
   "disponible": true
  },
  {
   "id": "cipreses-blanco",
   "nombre": "Cipreses Vineyard Sauvignon Blanc",
   "tipo": "blanco",
   "vina": "Viña Casa Marín",
   "volumenMl": 750,
   "gradoAlcohol": 13.5,
   "precio": 24900,
   "imagen": "images/vinos/cipreses-blanco.webp",
   "recomendado": true,
   "disponible": true
  },
  {
   "id": "clos-es
… (recortado)
```

### 3. Filtro Tintos (botón del frontend)

- Requisito: **R02** · Servicio: **S01** · Esperado: **200** · Obtenido: **200** → ✅

```http
GET /api/v1/products?tipo=tinto
```

```json
{
 "items": [
  {
   "id": "kuyen-tinto",
   "nombre": "Kuyen (blend tinto)",
   "tipo": "tinto",
   "vina": "Viña Antiyal",
   "volumenMl": 750,
   "gradoAlcohol": 14.5,
   "precio": 32000,
   "imagen": "images/vinos/kuyen-tinto.jpg",
   "recomendado": true,
   "disponible": true
  },
  {
   "id": "purafe-tinto",
   "nombre": "Pura Fe Carmenere",
   "tipo": "tinto",
   "vina": "Viña Antiyal",
   "volumenMl": 750,
   "gradoAlcohol": 14.0,
   "precio": 22900,
   "imagen": "images/vinos/purafe-tinto.jpg",
   "recomendado": true,
   "disponible": true
  }
 ],
 "total": 2,
 "pagina": 1,
 "tamano": 24
}
```

### 4. Recomendados (carrusel del frontend)

- Requisito: **R03** · Servicio: **S01** · Esperado: **200** · Obtenido: **200** → ✅

```http
GET /api/v1/products?recomendado=true
```

```json
{
 "items": [
  {
   "id": "almaviva-especial",
   "nombre": "Almaviva",
   "tipo": "especial",
   "vina": "Viña Almaviva",
   "volumenMl": 750,
   "gradoAlcohol": 15.0,
   "precio": 135000,
   "imagen": "images/vinos/almaviva-especial.jpg",
   "recomendado": true,
   "disponible": true
  },
  {
   "id": "chardonay-rosado",
   "nombre": "Chardonnay Reserva",
   "tipo": "rosado",
   "vina": "Viña Echeverría",
   "volumenMl": 750,
   "gradoAlcohol": 13.5,
   "precio": 18500,
   "imagen": "images/vinos/chardonay-rosado.jpg",
   "recomendado": true,
   "disponible": true
  },
  {
   "id": "cipreses-blanco",
   "nombre": "Cipreses Vineyard Sauvignon Blanc",
   "tipo": "blanco",
   "vina": "Viña Casa Marín",
   "volumenMl": 750,
   "gradoAlcohol": 13.5,
   "precio": 24900,
   "imagen": "images/vinos/cipreses-blanco.webp",
   "recomendado": true,
   "disponible": true
  },
  {
   "id": "clos-es
… (recortado)
```

### 5. Filtro inválido

- Requisito: **R02** · Servicio: **S01** · Esperado: **400** · Obtenido: **400** → ✅

```http
GET /api/v1/products?tipo=cerveza
```

```json
{
 "error": {
  "code": "VALIDATION_ERROR",
  "message": "Datos inválidos",
  "requestId": "db9fec9e-6a1c-460c-8d91-62c795451a46",
  "details": [
   {
    "campo": "tipo",
    "motivo": "Input should be 'tinto', 'blanco', 'rosado' or 'especial'"
   }
  ]
 }
}
```


## 2. Carrito y despacho (precios del servidor)

### 6. Cotizar carrito: 1 Kuyen + 2 Cipreses a Providencia

- Requisito: **R04 R05** · Servicio: **S02** · Esperado: **200** · Obtenido: **200** → ✅

```http
POST /api/v1/orders/quote

{
 "items": [
  {
   "productoId": "kuyen-tinto",
   "cantidad": 1
  },
  {
   "productoId": "cipreses-blanco",
   "cantidad": 2
  }
 ],
 "destino": {
  "comuna": "Providencia",
  "region": "Metropolitana"
 }
}
```

```json
{
 "items": [
  {
   "productoId": "kuyen-tinto",
   "nombre": "Kuyen (blend tinto)",
   "tipo": "tinto",
   "imagen": "images/vinos/kuyen-tinto.jpg",
   "precioUnitario": 32000,
   "cantidad": 1,
   "subtotal": 32000,
   "disponible": true
  },
  {
   "productoId": "cipreses-blanco",
   "nombre": "Cipreses Vineyard Sauvignon Blanc",
   "tipo": "blanco",
   "imagen": "images/vinos/cipreses-blanco.webp",
   "precioUnitario": 24900,
   "cantidad": 2,
   "subtotal": 49800,
   "disponible": true
  }
 ],
 "noDisponibles": [],
 "subtotal": 81800,
 "despacho": 0,
 "total": 81800,
 "envioGratisDesde": 50000
}
```

### 7. Cotizar a regiones (tarifa $6.990)

- Requisito: **R05** · Servicio: **S02** · Esperado: **200** · Obtenido: **200** → ✅

```http
POST /api/v1/orders/quote

{
 "items": [
  {
   "productoId": "pinot-rosado",
   "cantidad": 1
  }
 ],
 "destino": {
  "comuna": "Viña del Mar",
  "region": "Valparaíso"
 }
}
```

```json
{
 "items": [
  {
   "productoId": "pinot-rosado",
   "nombre": "Pinot Noir Rosé",
   "tipo": "rosado",
   "imagen": "images/vinos/pinot-rosado.jpg",
   "precioUnitario": 16900,
   "cantidad": 1,
   "subtotal": 16900,
   "disponible": true
  }
 ],
 "noDisponibles": [],
 "subtotal": 16900,
 "despacho": 6990,
 "total": 23890,
 "envioGratisDesde": 50000
}
```


## 3. Registro e inicio de sesión (formulario Mi Cuenta)

### 8. Registro de cliente

- Requisito: **R07** · Servicio: **S03** · Esperado: **201** · Obtenido: **201** → ✅

```http
POST /api/v1/auth/register

{
 "nombre": "Ana Pérez",
 "email": "ana.5dcd06@correo.cl",
 "password": "ClaveSegura2026",
 "telefono": "+56 9 5555 1234",
 "fechaNacimiento": "1998-03-10",
 "aceptaTerminos": true
}
```

```json
{
 "userId": "0cafafda-4af3-4afa-860b-3d203c792d78",
 "email": "ana.5dcd06@correo.cl",
 "nombre": "Ana Pérez"
}
```

### 9. Registro de menor de edad (rechazado)

- Requisito: **R01** · Servicio: **S03** · Esperado: **422** · Obtenido: **422** → ✅

```http
POST /api/v1/auth/register

{
 "nombre": "Ana Pérez",
 "email": "menor.ana.5dcd06@correo.cl",
 "password": "ClaveSegura2026",
 "telefono": "+56 9 5555 1234",
 "fechaNacimiento": "2012-06-01",
 "aceptaTerminos": true
}
```

```json
{
 "error": {
  "code": "UNDERAGE",
  "message": "Debes ser mayor de 18 años para registrarte",
  "requestId": "255e3846-081e-430c-8349-640510a63631"
 }
}
```

### 10. Login con contraseña incorrecta

- Requisito: **R07** · Servicio: **S04** · Esperado: **401** · Obtenido: **401** → ✅

```http
POST /api/v1/auth/login

{
 "email": "ana.5dcd06@correo.cl",
 "password": "otra123x"
}
```

```json
{
 "error": {
  "code": "INVALID_CREDENTIALS",
  "message": "Correo o contraseña incorrectos",
  "requestId": "61c54cfd-2290-458e-b38c-31edf8c0bb1c"
 }
}
```

### 11. Login correcto (sesión en cookie HttpOnly)

- Requisito: **R07** · Servicio: **S04** · Esperado: **200** · Obtenido: **200** → ✅

```http
POST /api/v1/auth/login

{
 "email": "ana.5dcd06@correo.cl",
 "password": "ClaveSegura2026"
}
```

```json
{
 "user": {
  "id": "0cafafda-4af3-4afa-860b-3d203c792d78",
  "email": "ana.5dcd06@correo.cl",
  "rol": "CLIENTE"
 },
 "expiresIn": 1800
}
```

### 12. Consultar sesión

- Requisito: **R07** · Servicio: **S06** · Esperado: **200** · Obtenido: **200** → ✅

```http
GET /api/v1/auth/session
```

```json
{
 "userId": "0cafafda-4af3-4afa-860b-3d203c792d78",
 "email": "ana.5dcd06@correo.cl",
 "rol": "CLIENTE"
}
```

### 13. Guardar dirección en el perfil

- Requisito: **R07** · Servicio: **S08** · Esperado: **200** · Obtenido: **200** → ✅

```http
PUT /api/v1/clients/me

{
 "nombre": "Ana Pérez",
 "telefono": "+56 9 5555 1234",
 "direccion": {
  "calle": "Av. Providencia",
  "numero": "1500",
  "comuna": "Providencia",
  "region": "Metropolitana"
 }
}
```

```json
{
 "nombre": "Ana Pérez",
 "email": "ana.5dcd06@correo.cl",
 "telefono": "+56 9 5555 1234",
 "fechaNacimiento": "1998-03-10",
 "direccion": {
  "calle": "Av. Providencia",
  "numero": "1500",
  "depto": null,
  "comuna": "Providencia",
  "region": "Metropolitana"
 }
}
```


## 4. Compra, pago y boleta

### 14. Pedido con total alterado por el cliente (rechazado)

- Requisito: **R06** · Servicio: **S10** · Esperado: **400** · Obtenido: **400** → ✅

```http
POST /api/v1/orders
Idempotency-Key: 21b3773b-e017-49c0-a238-e38bdfae1f28

{
 "items": [
  {
   "productoId": "kuyen-tinto",
   "cantidad": 1
  },
  {
   "productoId": "cipreses-blanco",
   "cantidad": 2
  }
 ],
 "entrega": {
  "nombreReceptor": "Ana Pérez",
  "calle": "Av. Providencia",
  "numero": "1500",
  "comuna": "Providencia",
  "region": "Metropolitana",
  "telefono": "+56955551234"
 },
 "total": 1
}
```

```json
{
 "error": {
  "code": "VALIDATION_ERROR",
  "message": "Datos inválidos",
  "requestId": "07b4f610-bf5d-4471-98bc-c7761e7f1d8d",
  "details": [
   {
    "campo": "total",
    "motivo": "Extra inputs are not permitted"
   }
  ]
 }
}
```

### 15. Crear pedido (stock reservado por gRPC)

- Requisito: **R04 R05** · Servicio: **S10** · Esperado: **201** · Obtenido: **201** → ✅

```http
POST /api/v1/orders
Idempotency-Key: eeff4a93-8a54-4010-8dcc-e45795670955

{
 "items": [
  {
   "productoId": "kuyen-tinto",
   "cantidad": 1
  },
  {
   "productoId": "cipreses-blanco",
   "cantidad": 2
  }
 ],
 "entrega": {
  "nombreReceptor": "Ana Pérez",
  "calle": "Av. Providencia",
  "numero": "1500",
  "comuna": "Providencia",
  "region": "Metropolitana",
  "telefono": "+56955551234"
 }
}
```

```json
{
 "id": "3b978c1d-acbc-4a24-a4d8-8ff38ce8a9fd",
 "numero": 1584,
 "estado": "PENDIENTE_PAGO",
 "items": [
  {
   "productoId": "kuyen-tinto",
   "nombre": "Kuyen (blend tinto)",
   "tipo": "tinto",
   "imagen": "images/vinos/kuyen-tinto.jpg",
   "precioUnitario": 32000,
   "cantidad": 1,
   "subtotal": 32000
  },
  {
   "productoId": "cipreses-blanco",
   "nombre": "Cipreses Vineyard Sauvignon Blanc",
   "tipo": "blanco",
   "imagen": "images/vinos/cipreses-blanco.webp",
   "precioUnitario": 24900,
   "cantidad": 2,
   "subtotal": 49800
  }
 ],
 "subtotal": 81800,
 "despacho": 0,
 "total": 81800,
 "entrega": {
  "comuna": "Providencia",
  "region": "Metropolitana",
  "nombreReceptor": "Ana Pérez",
  "calle": "Av. Providencia",
  "numero": "1500",
  "depto": null,
  "telefono": "+56955551234",
  "indicaciones": null
 },
 "creadoEn": "2026-11-08T19:24:37.664053+00:00",
 "venceEn": "2026-1
… (recortado)
```

### 16. Reintento con la misma Idempotency-Key (mismo pedido)

- Requisito: **R06** · Servicio: **S10** · Esperado: **200** · Obtenido: **200** → ✅

```http
POST /api/v1/orders
Idempotency-Key: eeff4a93-8a54-4010-8dcc-e45795670955

{
 "items": [
  {
   "productoId": "kuyen-tinto",
   "cantidad": 1
  },
  {
   "productoId": "cipreses-blanco",
   "cantidad": 2
  }
 ],
 "entrega": {
  "nombreReceptor": "Ana Pérez",
  "calle": "Av. Providencia",
  "numero": "1500",
  "comuna": "Providencia",
  "region": "Metropolitana",
  "telefono": "+56955551234"
 }
}
```

```json
{
 "id": "3b978c1d-acbc-4a24-a4d8-8ff38ce8a9fd",
 "numero": 1584,
 "estado": "PENDIENTE_PAGO",
 "items": [
  {
   "productoId": "kuyen-tinto",
   "nombre": "Kuyen (blend tinto)",
   "tipo": "tinto",
   "imagen": "images/vinos/kuyen-tinto.jpg",
   "precioUnitario": 32000,
   "cantidad": 1,
   "subtotal": 32000
  },
  {
   "productoId": "cipreses-blanco",
   "nombre": "Cipreses Vineyard Sauvignon Blanc",
   "tipo": "blanco",
   "imagen": "images/vinos/cipreses-blanco.webp",
   "precioUnitario": 24900,
   "cantidad": 2,
   "subtotal": 49800
  }
 ],
 "subtotal": 81800,
 "despacho": 0,
 "total": 81800,
 "entrega": {
  "comuna": "Providencia",
  "region": "Metropolitana",
  "nombreReceptor": "Ana Pérez",
  "calle": "Av. Providencia",
  "numero": "1500",
  "depto": null,
  "telefono": "+56955551234",
  "indicaciones": null
 },
 "creadoEn": "2026-11-08T19:24:37.664000",
 "venceEn": "2026-11-08T1
… (recortado)
```

### 17. Iniciar pago (monto lo fija orders)

- Requisito: **R06** · Servicio: **S14** · Esperado: **201** · Obtenido: **201** → ✅

```http
POST /api/v1/payments

{
 "pedidoId": "3b978c1d-acbc-4a24-a4d8-8ff38ce8a9fd"
}
```

```json
{
 "pagoId": "bbcf4a29-3a0a-451f-bc3c-07d4e1864d58",
 "pedidoId": "3b978c1d-acbc-4a24-a4d8-8ff38ce8a9fd",
 "estado": "INICIADO",
 "monto": 81800,
 "actualizadoEn": "2026-11-08T19:24:37.743547+00:00",
 "boleta": null,
 "redirectUrl": "https://localhost:8090/pay/5108c35b76724d06996185f1a0fa7bec"
}
```

> Comprador aprueba en la página del proveedor → redirección a https://localhost:8443/?pago=bbcf4a29-3a0a-451f-bc3c-07d4e1864d58

### 18. Verificar pago con el proveedor (boleta emitida)

- Requisito: **R06 R12** · Servicio: **S15** · Esperado: **200** · Obtenido: **200** → ✅

```http
POST /api/v1/payments/bbcf4a29-3a0a-451f-bc3c-07d4e1864d58/verify
```

```json
{
 "pagoId": "bbcf4a29-3a0a-451f-bc3c-07d4e1864d58",
 "pedidoId": "3b978c1d-acbc-4a24-a4d8-8ff38ce8a9fd",
 "estado": "APROBADO",
 "monto": 81800,
 "actualizadoEn": "2026-11-08T19:24:37.797000",
 "boleta": {
  "folio": 17,
  "neto": 68739,
  "iva": 13061,
  "total": 81800,
  "emitidaEn": "2026-11-08T19:24:37.799834+00:00"
 }
}
```

### 19. Reenvío de la misma notificación del proveedor (sin efectos dobles)

- Requisito: **R06** · Servicio: **S16** · Esperado: **200** · Obtenido: **200** → ✅

```http
POST https://localhost:8090/sandbox/transactions/5108c35b76724d06996185f1a0fa7bec/resend-webhook
```

```json
{
 "merchantStatus": 200
}
```

### 20. Intentar pagar de nuevo el mismo pedido

- Requisito: **R06** · Servicio: **S14** · Esperado: **409** · Obtenido: **409** → ✅

```http
POST /api/v1/payments

{
 "pedidoId": "3b978c1d-acbc-4a24-a4d8-8ff38ce8a9fd"
}
```

```json
{
 "error": {
  "code": "ORDER_NOT_PAYABLE",
  "message": "El pedido está PAGADO",
  "requestId": "59e36676-9843-4463-8791-264c9e2bef58"
 }
}
```


## 5. Agregación GraphQL (orders + inventory + payments)

### 21. Mis pedidos (una consulta, tres subsistemas)

- Requisito: **R12** · Servicio: **S11** · Esperado: **200** · Obtenido: **200** → ✅

```http
POST /api/v1/graphql

{
 "query": "{ misPedidos(tamano: 3) { total items { numero estado total despacho items { nombre cantidad producto { imagen disponible } } pago { estado boleta { folio neto iva total } } } } }"
}
```

```json
{
 "data": {
  "misPedidos": {
   "total": 1,
   "items": [
    {
     "numero": 1584,
     "estado": "PAGADO",
     "total": 81800,
     "despacho": 0,
     "items": [
      {
       "nombre": "Kuyen (blend tinto)",
       "cantidad": 1,
       "producto": {
        "imagen": "images/vinos/kuyen-tinto.jpg",
        "disponible": true
       }
      },
      {
       "nombre": "Cipreses Vineyard Sauvignon Blanc",
       "cantidad": 2,
       "producto": {
        "imagen": "images/vinos/cipreses-blanco.webp",
        "disponible": true
       }
      }
     ],
     "pago": {
      "estado": "APROBADO",
      "boleta": {
       "folio": 17,
       "neto": 68739,
       "iva": 13061,
       "total": 81800
      }
     }
    }
   ]
  }
 }
}
```

### 22. Campo restringido clienteId para un cliente

- Requisito: **R12** · Servicio: **S11** · Esperado: **200** · Obtenido: **200** → ✅

```http
POST /api/v1/graphql

{
 "query": "{ misPedidos(tamano:1) { items { numero clienteId } } }"
}
```

```json
{
 "errors": [
  {
   "message": "Campo restringido a administración",
   "path": [
    "misPedidos",
    "items",
    0,
    "clienteId"
   ],
   "extensions": {
    "code": "FORBIDDEN_FIELD"
   }
  }
 ],
 "data": {
  "misPedidos": {
   "items": [
    {
     "numero": 1584,
     "clienteId": null
    }
   ]
  }
 }
}
```

### 23. Registro de un segundo cliente

- Requisito: **R07** · Servicio: **S03** · Esperado: **201** · Obtenido: **201** → ✅

```http
POST /api/v1/auth/register

{
 "nombre": "Ana Pérez",
 "email": "otro.5e7a21@correo.cl",
 "password": "ClaveSegura2026",
 "telefono": "+56 9 5555 1234",
 "fechaNacimiento": "1998-03-10",
 "aceptaTerminos": true
}
```

```json
{
 "userId": "060fe13b-ea9f-4ff7-be1e-572b2c1f67ee",
 "email": "otro.5e7a21@correo.cl",
 "nombre": "Ana Pérez"
}
```

### 24. Login segundo cliente

- Requisito: **R07** · Servicio: **S04** · Esperado: **200** · Obtenido: **200** → ✅

```http
POST /api/v1/auth/login

{
 "email": "otro.5e7a21@correo.cl",
 "password": "ClaveSegura2026"
}
```

```json
{
 "user": {
  "id": "060fe13b-ea9f-4ff7-be1e-572b2c1f67ee",
  "email": "otro.5e7a21@correo.cl",
  "rol": "CLIENTE"
 },
 "expiresIn": 1800
}
```

### 25. Otro cliente consulta el pedido de Ana (null, sin datos)

- Requisito: **R12** · Servicio: **S12** · Esperado: **200** · Obtenido: **200** → ✅

```http
POST /api/v1/graphql

{
 "query": "query($id: ID!){ resumenPedido(id:$id){ numero total entrega { calle } } }",
 "variables": {
  "id": "3b978c1d-acbc-4a24-a4d8-8ff38ce8a9fd"
 }
}
```

```json
{
 "data": {
  "resumenPedido": null
 }
}
```

### 26. Otro cliente intenta anular el pedido de Ana

- Requisito: **R12** · Servicio: **S13** · Esperado: **404** · Obtenido: **404** → ✅

```http
POST /api/v1/orders/3b978c1d-acbc-4a24-a4d8-8ff38ce8a9fd/cancel
```

```json
{
 "error": {
  "code": "ORDER_NOT_FOUND",
  "message": "Pedido no encontrado",
  "requestId": "a8e2a6d3-1360-4349-8069-b8b2794d18f2"
 }
}
```

### 27. Acceso directo a orders sin identidad de servicio

- Requisito: **—** · Servicio: **interno** · Esperado: **401** · Obtenido: **401** → ✅

```http
GET https://127.0.0.1:9104/internal/orders
X-User-Id: x
X-User-Role: ADMIN
```

```json
{
 "error": {
  "code": "INVALID_SERVICE_IDENTITY",
  "message": "Identidad de servicio inválida",
  "requestId": "e5a92fff-8568-43a4-aeab-c81269d878ca"
 }
}
```

### 28. Ruta interna por el gateway (no publicada)

- Requisito: **—** · Servicio: **gateway** · Esperado: **404** · Obtenido: **404** → ✅

```http
GET /api/v1/internal/orders
```

```json
{
 "error": {
  "code": "NOT_FOUND",
  "message": "Ruta no publicada",
  "requestId": "0e5415ce-6eb0-46b1-99ec-0f43b40c6c9b"
 }
}
```


## 6. Degustaciones (formulario de reserva)

### 29. Paquetes del frontend

- Requisito: **R08** · Servicio: **S17** · Esperado: **200** · Obtenido: **200** → ✅

```http
GET /api/v1/tastings/packages
```

```json
{
 "items": [
  {
   "id": "iniciacion-cata",
   "nombre": "Iniciación a la cata",
   "descripcion": "Descubre el vino a tu ritmo, junto a un sommelier que te guía en cada copa.",
   "incluye": [
    "4 vinos seleccionados",
    "Duración: 1 hora",
    "Guía de cata incluida",
    "Tabla de quesos y pan artesanal"
   ],
   "duracionMin": 60,
   "precioPorPersona": 15000,
   "imagen": "images/paquete1.jpg"
  },
  {
   "id": "maridaje-gourmet",
   "nombre": "Maridaje Gourmet",
   "descripcion": "Una velada donde cada vino encuentra su bocado perfecto.",
   "incluye": [
    "5 vinos maridados",
    "Duración: 1,5 horas",
    "Ficha técnica de cada vino para llevar",
    "Asesoría de maridaje personalizada"
   ],
   "duracionMin": 90,
   "precioPorPersona": 28000,
   "imagen": "images/paquete2.jpg"
  },
  {
   "id": "edicion-limitada",
   "nombre": "Edición Limitada",
   "descripcion": "Un m
… (recortado)
```

### 30. Cupos por horario

- Requisito: **R08** · Servicio: **S18** · Esperado: **200** · Obtenido: **200** → ✅

```http
GET /api/v1/tastings/availability?fecha=2026-11-16
```

```json
{
 "fecha": "2026-11-16",
 "capacidad": 12,
 "horarios": [
  {
   "hora": "10:00",
   "cuposDisponibles": 12
  },
  {
   "hora": "12:00",
   "cuposDisponibles": 12
  },
  {
   "hora": "16:00",
   "cuposDisponibles": 12
  },
  {
   "hora": "18:00",
   "cuposDisponibles": 4
  },
  {
   "hora": "20:00",
   "cuposDisponibles": 12
  }
 ]
}
```

### 31. Reservar Maridaje Gourmet para 4

- Requisito: **R08** · Servicio: **S19** · Esperado: **201** · Obtenido: **201** → ✅

```http
POST /api/v1/tastings/reservations

{
 "paqueteId": "maridaje-gourmet",
 "fecha": "2026-11-16",
 "hora": "18:00",
 "personas": 4,
 "contacto": {
  "nombre": "Ana Pérez",
  "email": "ana.5dcd06@correo.cl",
  "telefono": "+56955551234"
 },
 "comentarios": "Uno de los asistentes es vegetariano"
}
```

```json
{
 "id": "c008ee3c-206b-4bea-8b4f-7d80bc36f17e",
 "paqueteId": "maridaje-gourmet",
 "paquete": "Maridaje Gourmet",
 "fecha": "2026-11-16",
 "hora": "18:00",
 "personas": 4,
 "total": 112000,
 "estado": "CONFIRMADA",
 "comentarios": "Uno de los asistentes es vegetariano",
 "creadaEn": "2026-11-08T19:24:38.256482+00:00"
}
```

### 32. Mis reservas

- Requisito: **R08** · Servicio: **S20** · Esperado: **200** · Obtenido: **200** → ✅

```http
GET /api/v1/tastings/reservations/me
```

```json
{
 "items": [
  {
   "id": "c008ee3c-206b-4bea-8b4f-7d80bc36f17e",
   "paqueteId": "maridaje-gourmet",
   "paquete": "Maridaje Gourmet",
   "fecha": "2026-11-16",
   "hora": "18:00",
   "personas": 4,
   "total": 112000,
   "estado": "CONFIRMADA",
   "comentarios": "Uno de los asistentes es vegetariano",
   "creadaEn": "2026-11-08T19:24:38.256000"
  }
 ]
}
```


## 7. Contacto

### 33. Mensaje del formulario de contacto

- Requisito: **R09** · Servicio: **S22** · Esperado: **201** · Obtenido: **201** → ✅

```http
POST /api/v1/contact

{
 "nombre": "Pedro Prueba",
 "email": "pedro@correo.cl",
 "asunto": "Pedido especial",
 "mensaje": "¿Tienen cajas de regalo para 6 botellas?"
}
```

```json
{
 "id": "aaff2f29-8a4b-43a0-bab3-03843a346386",
 "recibidoEn": "2026-11-08T19:24:38.282292+00:00",
 "estado": "PENDIENTE"
}
```


## 8. Administración, despacho y reportes

### 34. Login administrador

- Requisito: **R11** · Servicio: **S04** · Esperado: **200** · Obtenido: **200** → ✅

```http
POST /api/v1/auth/login

{
 "email": "admin@vinaurbana.cl",
 "password": "Admt8LSj9Hq-loq9"
}
```

```json
{
 "user": {
  "id": "ed9e86c7-7d2e-493b-86ad-d452d7b6e1ab",
  "email": "admin@vinaurbana.cl",
  "rol": "ADMIN"
 },
 "expiresIn": 1800
}
```

### 35. Cliente intenta administrar productos (denegado)

- Requisito: **R11** · Servicio: **S23** · Esperado: **403** · Obtenido: **403** → ✅

```http
GET /api/v1/admin/products
```

```json
{
 "error": {
  "code": "FORBIDDEN",
  "message": "Tu rol no permite esta operación",
  "requestId": "f35053e4-ec92-4017-a4a7-2b3020524bbe"
 }
}
```

### 36. Inventario con stock

- Requisito: **R11** · Servicio: **S23** · Esperado: **200** · Obtenido: **200** → ✅

```http
GET /api/v1/admin/products
```

```json
{
 "items": [
  {
   "id": "almaviva-especial",
   "nombre": "Almaviva",
   "tipo": "especial",
   "vina": "Viña Almaviva",
   "volumenMl": 750,
   "gradoAlcohol": 15.0,
   "precio": 135000,
   "imagen": "images/vinos/almaviva-especial.jpg",
   "recomendado": true,
   "disponible": true,
   "stock": 18,
   "activo": true,
   "actualizadoEn": "2026-11-08T19:00:35.318000"
  },
  {
   "id": "chardonay-rosado",
   "nombre": "Chardonnay Reserva",
   "tipo": "rosado",
   "vina": "Viña Echeverría",
   "volumenMl": 750,
   "gradoAlcohol": 13.5,
   "precio": 18500,
   "imagen": "images/vinos/chardonay-rosado.jpg",
   "recomendado": true,
   "disponible": true,
   "stock": 28,
   "activo": true,
   "actualizadoEn": "2026-11-08T18:59:50.336000"
  },
  {
   "id": "cipreses-blanco",
   "nombre": "Cipreses Vineyard Sauvignon Blanc",
   "tipo": "blanco",
   "vina": "Viña Casa Marín",
   "volumenMl": 75
… (recortado)
```

### 37. Ingreso de bodega +6 Almaviva

- Requisito: **R11** · Servicio: **S26** · Esperado: **200** · Obtenido: **200** → ✅

```http
PATCH /api/v1/admin/products/almaviva-especial/stock

{
 "delta": 6,
 "motivo": "INGRESO_BODEGA"
}
```

```json
{
 "id": "almaviva-especial",
 "nombre": "Almaviva",
 "tipo": "especial",
 "vina": "Viña Almaviva",
 "volumenMl": 750,
 "gradoAlcohol": 15.0,
 "precio": 135000,
 "imagen": "images/vinos/almaviva-especial.jpg",
 "recomendado": true,
 "disponible": true,
 "stock": 24,
 "activo": true,
 "actualizadoEn": "2026-11-08T19:24:38.370000"
}
```

### 38. Pedidos pagados

- Requisito: **R11** · Servicio: **S28** · Esperado: **200** · Obtenido: **200** → ✅

```http
GET /api/v1/admin/orders?estado=PAGADO&tamano=2
```

```json
{
 "items": [
  {
   "id": "3b978c1d-acbc-4a24-a4d8-8ff38ce8a9fd",
   "numero": 1584,
   "estado": "PAGADO",
   "items": [
    {
     "productoId": "kuyen-tinto",
     "nombre": "Kuyen (blend tinto)",
     "tipo": "tinto",
     "imagen": "images/vinos/kuyen-tinto.jpg",
     "precioUnitario": 32000,
     "cantidad": 1,
     "subtotal": 32000
    },
    {
     "productoId": "cipreses-blanco",
     "nombre": "Cipreses Vineyard Sauvignon Blanc",
     "tipo": "blanco",
     "imagen": "images/vinos/cipreses-blanco.webp",
     "precioUnitario": 24900,
     "cantidad": 2,
     "subtotal": 49800
    }
   ],
   "subtotal": 81800,
   "despacho": 0,
   "total": 81800,
   "entrega": {
    "comuna": "Providencia",
    "region": "Metropolitana",
    "nombreReceptor": "Ana Pérez",
    "calle": "Av. Providencia",
    "numero": "1500",
    "depto": null,
    "telefono": "+56955551234",
    "indicaciones":
… (recortado)
```

### 39. Despacho → EN_PREPARACION

- Requisito: **R11 R12** · Servicio: **S29** · Esperado: **200** · Obtenido: **200** → ✅

```http
PATCH /api/v1/admin/orders/3b978c1d-acbc-4a24-a4d8-8ff38ce8a9fd/status

{
 "estado": "EN_PREPARACION"
}
```

```json
{
 "id": "3b978c1d-acbc-4a24-a4d8-8ff38ce8a9fd",
 "numero": 1584,
 "estado": "EN_PREPARACION",
 "items": [
  {
   "productoId": "kuyen-tinto",
   "nombre": "Kuyen (blend tinto)",
   "tipo": "tinto",
   "imagen": "images/vinos/kuyen-tinto.jpg",
   "precioUnitario": 32000,
   "cantidad": 1,
   "subtotal": 32000
  },
  {
   "productoId": "cipreses-blanco",
   "nombre": "Cipreses Vineyard Sauvignon Blanc",
   "tipo": "blanco",
   "imagen": "images/vinos/cipreses-blanco.webp",
   "precioUnitario": 24900,
   "cantidad": 2,
   "subtotal": 49800
  }
 ],
 "subtotal": 81800,
 "despacho": 0,
 "total": 81800,
 "entrega": {
  "comuna": "Providencia",
  "region": "Metropolitana",
  "nombreReceptor": "Ana Pérez",
  "calle": "Av. Providencia",
  "numero": "1500",
  "depto": null,
  "telefono": "+56955551234",
  "indicaciones": null
 },
 "creadoEn": "2026-11-08T19:24:37.664000",
 "venceEn": null,
 "histo
… (recortado)
```

### 40. Despacho → DESPACHADO

- Requisito: **R11 R12** · Servicio: **S29** · Esperado: **200** · Obtenido: **200** → ✅

```http
PATCH /api/v1/admin/orders/3b978c1d-acbc-4a24-a4d8-8ff38ce8a9fd/status

{
 "estado": "DESPACHADO"
}
```

```json
{
 "id": "3b978c1d-acbc-4a24-a4d8-8ff38ce8a9fd",
 "numero": 1584,
 "estado": "DESPACHADO",
 "items": [
  {
   "productoId": "kuyen-tinto",
   "nombre": "Kuyen (blend tinto)",
   "tipo": "tinto",
   "imagen": "images/vinos/kuyen-tinto.jpg",
   "precioUnitario": 32000,
   "cantidad": 1,
   "subtotal": 32000
  },
  {
   "productoId": "cipreses-blanco",
   "nombre": "Cipreses Vineyard Sauvignon Blanc",
   "tipo": "blanco",
   "imagen": "images/vinos/cipreses-blanco.webp",
   "precioUnitario": 24900,
   "cantidad": 2,
   "subtotal": 49800
  }
 ],
 "subtotal": 81800,
 "despacho": 0,
 "total": 81800,
 "entrega": {
  "comuna": "Providencia",
  "region": "Metropolitana",
  "nombreReceptor": "Ana Pérez",
  "calle": "Av. Providencia",
  "numero": "1500",
  "depto": null,
  "telefono": "+56955551234",
  "indicaciones": null
 },
 "creadoEn": "2026-11-08T19:24:37.664000",
 "venceEn": null,
 "historial
… (recortado)
```

### 41. Despacho → ENTREGADO

- Requisito: **R11 R12** · Servicio: **S29** · Esperado: **200** · Obtenido: **200** → ✅

```http
PATCH /api/v1/admin/orders/3b978c1d-acbc-4a24-a4d8-8ff38ce8a9fd/status

{
 "estado": "ENTREGADO"
}
```

```json
{
 "id": "3b978c1d-acbc-4a24-a4d8-8ff38ce8a9fd",
 "numero": 1584,
 "estado": "ENTREGADO",
 "items": [
  {
   "productoId": "kuyen-tinto",
   "nombre": "Kuyen (blend tinto)",
   "tipo": "tinto",
   "imagen": "images/vinos/kuyen-tinto.jpg",
   "precioUnitario": 32000,
   "cantidad": 1,
   "subtotal": 32000
  },
  {
   "productoId": "cipreses-blanco",
   "nombre": "Cipreses Vineyard Sauvignon Blanc",
   "tipo": "blanco",
   "imagen": "images/vinos/cipreses-blanco.webp",
   "precioUnitario": 24900,
   "cantidad": 2,
   "subtotal": 49800
  }
 ],
 "subtotal": 81800,
 "despacho": 0,
 "total": 81800,
 "entrega": {
  "comuna": "Providencia",
  "region": "Metropolitana",
  "nombreReceptor": "Ana Pérez",
  "calle": "Av. Providencia",
  "numero": "1500",
  "depto": null,
  "telefono": "+56955551234",
  "indicaciones": null
 },
 "creadoEn": "2026-11-08T19:24:37.664000",
 "venceEn": null,
 "historial"
… (recortado)
```

### 42. Transición inválida (ENTREGADO → EN_PREPARACION)

- Requisito: **R11** · Servicio: **S29** · Esperado: **409** · Obtenido: **409** → ✅

```http
PATCH /api/v1/admin/orders/3b978c1d-acbc-4a24-a4d8-8ff38ce8a9fd/status

{
 "estado": "EN_PREPARACION"
}
```

```json
{
 "error": {
  "code": "INVALID_TRANSITION",
  "message": "No se puede pasar de ENTREGADO a EN_PREPARACION",
  "requestId": "3c314c28-c073-4b5a-b0ad-0d4399e9a4af"
 }
}
```

### 43. Mensajes de contacto pendientes

- Requisito: **R09** · Servicio: **S32** · Esperado: **200** · Obtenido: **200** → ✅

```http
GET /api/v1/admin/contact?estado=PENDIENTE&tamano=2
```

```json
{
 "items": [
  {
   "id": "aaff2f29-8a4b-43a0-bab3-03843a346386",
   "nombre": "Pedro Prueba",
   "email": "pedro@correo.cl",
   "asunto": "Pedido especial",
   "mensaje": "¿Tienen cajas de regalo para 6 botellas?",
   "estado": "PENDIENTE",
   "recibidoEn": "2026-11-08T19:24:38.282000"
  },
  {
   "id": "9b66ac8c-b2c3-401d-a243-b37f31ac5519",
   "nombre": "Spam Bot",
   "email": "spam@correo.cl",
   "asunto": "Otro",
   "mensaje": "mensaje 0",
   "estado": "PENDIENTE",
   "recibidoEn": "2026-11-08T19:03:40.669000"
  }
 ],
 "total": 11,
 "pagina": 1,
 "tamano": 2
}
```

### 44. Panel de ventas GraphQL (analytics + inventory)

- Requisito: **R13** · Servicio: **S34** · Esperado: **200** · Obtenido: **200** → ✅

```http
POST /api/v1/graphql

{
 "query": "query($d:String!){ panelVentas(desde:$d, hasta:$d){ totalVentas pedidosPagados ticketPromedio topProductos{ nombre unidades } reservasPorPaquete{ paquete personas } stockBajo{ nombre stock } } }",
 "variables": {
  "d": "2026-11-08"
 }
}
```

```json
{
 "data": {
  "panelVentas": {
   "totalVentas": 583500,
   "pedidosPagados": 15,
   "ticketPromedio": 38900,
   "topProductos": [
    {
     "nombre": "Cipreses Vineyard Sauvignon Blanc",
     "unidades": 8
    },
    {
     "nombre": "Pinot Noir Rosé",
     "unidades": 6
    },
    {
     "nombre": "Riesling Miramar Vineyard",
     "unidades": 4
    },
    {
     "nombre": "Kuyen (blend tinto)",
     "unidades": 3
    },
    {
     "nombre": "Chardonnay Reserva",
     "unidades": 2
    }
   ],
   "reservasPorPaquete": [
    {
     "paquete": "Iniciación a la cata",
     "personas": 26
    },
    {
     "paquete": "Maridaje Gourmet",
     "personas": 12
    }
   ],
   "stockBajo": [
    {
     "nombre": "Viñedo Chadwick",
     "stock": 4
    },
    {
     "nombre": "Clos Apalta",
     "stock": 5
    }
   ]
  }
 }
}
```

### 45. Login sommelier

- Requisito: **R08** · Servicio: **S04** · Esperado: **200** · Obtenido: **200** → ✅

```http
POST /api/v1/auth/login

{
 "email": "sommelier@vinaurbana.cl",
 "password": "SomaWCocLeKV0zX9"
}
```

```json
{
 "user": {
  "id": "e1e5f64c-d2c4-404b-ba32-493104ba10f4",
  "email": "sommelier@vinaurbana.cl",
  "rol": "SOMMELIER"
 },
 "expiresIn": 1800
}
```

### 46. Sommelier ve reservas con comentarios

- Requisito: **R08** · Servicio: **S30** · Esperado: **200** · Obtenido: **200** → ✅

```http
GET /api/v1/admin/tastings/reservations?fecha=2026-11-16
```

```json
{
 "items": [
  {
   "id": "0f2c1c44-38bd-4005-848d-61eeb41731c8",
   "paqueteId": "maridaje-gourmet",
   "paquete": "Maridaje Gourmet",
   "fecha": "2026-11-16",
   "hora": "18:00",
   "personas": 4,
   "total": 112000,
   "estado": "CONFIRMADA",
   "comentarios": "Uno de los asistentes es vegetariano",
   "creadaEn": "2026-11-08T18:59:55.956000",
   "contacto": {
    "nombre": "Ana Pérez",
    "email": "ana.ff8287@correo.cl",
    "telefono": "+56955551234"
   }
  },
  {
   "id": "192d80e8-b398-4211-aaa9-4e5d19bb90e7",
   "paqueteId": "maridaje-gourmet",
   "paquete": "Maridaje Gourmet",
   "fecha": "2026-11-16",
   "hora": "18:00",
   "personas": 4,
   "total": 112000,
   "estado": "CONFIRMADA",
   "comentarios": "Uno de los asistentes es vegetariano",
   "creadaEn": "2026-11-08T19:00:35.227000",
   "contacto": {
    "nombre": "Ana Pérez",
    "email": "ana.0ed1f6@correo.cl",
    "tele
… (recortado)
```

### 47. Sommelier intenta ver pedidos (denegado)

- Requisito: **R11** · Servicio: **S28** · Esperado: **403** · Obtenido: **403** → ✅

```http
GET /api/v1/admin/orders
```

```json
{
 "error": {
  "code": "FORBIDDEN",
  "message": "Tu rol no permite esta operación",
  "requestId": "4493dd0b-7e50-4ccb-b096-7297150fc738"
 }
}
```


## 9. Cierre de sesión

### 48. Cerrar sesión

- Requisito: **R07** · Servicio: **S05** · Esperado: **200** · Obtenido: **200** → ✅

```http
POST /api/v1/auth/logout
```

```json
{
 "sesionCerrada": true
}
```

### 49. Operación tras cerrar sesión

- Requisito: **R07** · Servicio: **S07** · Esperado: **401** · Obtenido: **401** → ✅

```http
GET /api/v1/clients/me
```

```json
{
 "error": {
  "code": "UNAUTHENTICATED",
  "message": "Debes iniciar sesión",
  "requestId": "dd5a1673-3246-45f2-8d06-202605ff0202"
 }
}
```
