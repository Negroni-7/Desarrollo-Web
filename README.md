# Plataforma Comercial — GraphQL Gateway + MongoDB y Modelo C4

Entrega final: capa de agregación GraphQL conectada a MongoDB, junto con la documentación de arquitectura usando el Modelo C4 (niveles C1 y C2).

El código de esta entrega está en la carpeta [plataforma-comercial/](plataforma-comercial/).

## 1. Descripción del sistema

La Plataforma Comercial permite a visitantes, clientes y operadores consultar productos, pedidos y clientes. El acceso a los datos privados está protegido por dos puertas de entrada:

- API Gateway (REST): valida un Bearer token contra Vault y reenvía la petición al backend privado agregando el secreto interno X-Gateway-Secret.
- GraphQL Gateway (agregador): valida el token con el Servicio de Autenticación, obtiene el secreto interno desde Vault, consulta los microservicios privados, consolida la información en un resumen y guarda los reportes en MongoDB. Ningún secreto sale hacia el cliente.

## 2. Diagrama de Contexto (C1 — System Context)

flowchart TB
    visitante["Visitante
    [Persona]
    Navega información pública"]:::person

    cliente["Cliente
    [Persona]
    Consulta productos y hace pedidos"]:::person

    operador["Operador
    [Persona]
    Administra las operaciones"]:::person

    plataforma["Plataforma Comercial
    [Sistema de software]
    Catálogo, pedidos, clientes y reportes"]:::system

    pagos["Procesador de pagos
    [Sistema externo]
    Transbank / Flow / Stripe"]:::ext

    visitante -->|"Consulta información pública
    [HTTPS]"| plataforma
    cliente -->|"Consulta productos y
    realiza pedidos [HTTPS]"| plataforma
    operador -->|"Administra operaciones y
    genera reportes [HTTPS]"| plataforma
    plataforma -->|"Solicita y confirma pagos
    [HTTPS / API]"| pagos

    classDef person fill:#08427b,stroke:#052e56,color:#ffffff
    classDef system fill:#1168bd,stroke:#0b4884,color:#ffffff
    classDef ext fill:#8a8a8a,stroke:#6b6b6b,color:#ffffff


## 3. Diagrama de Contenedores (C2 — Containers)

flowchart TB
    visitante["Visitante
    [Persona]"]:::person

    cliente["Cliente
    [Persona]"]:::person

    operador["Operador
    [Persona]"]:::person

    pagos["Procesador de pagos
    [Sistema externo]
    Transbank / Flow / Stripe"]:::ext

    subgraph plataforma["Plataforma Comercial [límite del sistema]"]
        direction TB

        frontend["Frontend responsivo
        [PHP + Bootstrap 5 + JS]
        Interfaz web"]:::container

        apigw["API Gateway
        [Python / FastAPI :8000]
        Valida Bearer token y enruta"]:::container

        gqlgw["GraphQL Gateway
        [Node.js / Apollo :4000]
        Agrega datos y genera reportes"]:::container

        auth["Autenticación (outservice)
        [Python / FastAPI :9100]
        Valida si el token sigue activo"]:::container

        vault["Administrador de Secretos
        [HashiCorp Vault :8200]
        Entrega secretos internos"]:::container

        backend["Microservicios privados
        [Python / FastAPI :9000]
        Inventario, Pedidos, Clientes"]:::container

        pagosvc["Servicio de Pagos
        [Por implementar]
        Integración con pagos"]:::planned

        negociodb[("BD de negocio
        [En memoria, simulada]")]:::db

        mongo[("MongoDB
        [:27017]
        Reportes y agregaciones")]:::db
    end

    visitante & cliente & operador -->|"Usan [HTTPS]"| frontend
    frontend -->|"REST
    [HTTP/JSON + Bearer]"| apigw
    frontend -->|"Consultas y reportes
    [GraphQL + Bearer]"| gqlgw
    apigw -->|"Lee token y secreto
    [HTTP]"| vault
    apigw -->|"Reenvía petición
    [HTTP + X-Gateway-Secret]"| backend
    gqlgw -->|"Valida token
    [POST /validate]"| auth
    auth -->|"Lee client_token
    [HTTP]"| vault
    gqlgw -->|"Lee X-Gateway-Secret
    [HTTP]"| vault
    gqlgw -->|"Consulta y agrega
    [HTTP + X-Gateway-Secret]"| backend
    gqlgw -->|"Guarda y consulta reportes
    [Mongoose]"| mongo
    backend -->|"Lee datos"| negociodb
    pagosvc -->|"Cobros [HTTPS]"| pagos

    classDef person fill:#08427b,stroke:#052e56,color:#ffffff
    classDef ext fill:#8a8a8a,stroke:#6b6b6b,color:#ffffff
    classDef container fill:#438dd5,stroke:#2e6295,color:#ffffff
    classDef db fill:#438dd5,stroke:#2e6295,color:#ffffff
    classDef planned fill:#9fc3e8,stroke:#2e6295,color:#0b1f33,stroke-dasharray:6 4


## 4. Estado de implementación

| Contenedor | Estado en esta entrega |
|---|---|
| Frontend responsivo | Existente (Semana 2 y 3). Aún no consume los gateways. |
| API Gateway | Implementado (plataforma-comercial/api-gateway) |
| GraphQL Gateway | Implementado (plataforma-comercial/gql-gateway) |
| Servicio de Autenticación | Implementado (plataforma-comercial/auth-service) |
| Vault | Implementado en modo desarrollo (vault server -dev) |
| Microservicios privados | Un solo proceso (plataforma-comercial/backend-api), datos en memoria |
| MongoDB | Implementado (colección reportes en la base DBM) |
| Servicio de Pagos | Solo diseñado (pendiente de implementar) |


## 5. Cómo ejecutar

Resumen (la guía paso a paso completa incluye la instalación de Git, Node.js, Python, MongoDB y Vault en Windows, macOS y Linux):

1. Iniciar MongoDB (servicio local en 127.0.0.1:27017).
2. Iniciar Vault en modo desarrollo: vault server -dev -dev-root-token-id=root.
3. Cargar secretos: python plataforma-comercial/scripts/seed_vault.py.
4. Copiar .env.example a .env en cada servicio.
5. Iniciar backend-api (9000), auth-service (9100), api-gateway (8000) y gql-gateway (4000).
6. Probar con el Bearer token de desarrollo: token-cliente-demo-123.


### Consulta de ejemplo (GraphQL)

mutation {
    generarReporte(tipo: "resumen-general") {
        id
        creadoEn
        resumen {
            totalProductos
            precioPromedio
            totalPedidos
            totalClientes
        }
    }
}


## 6. Seguridad

- Los secretos (client_token, backend_shared_secret) viven en Vault; el código solo guarda el token de acceso a Vault en un archivo .env que NO se sube a Git.
- El backend rechaza (403) cualquier petición que no traiga X-Gateway-Secret.
- Los valores de este repositorio son solo de desarrollo y deben reemplazarse en un entorno real.