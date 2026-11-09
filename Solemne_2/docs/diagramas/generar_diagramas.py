"""Genera los diagramas del informe a partir de UNA definición:
  - <nombre>.drawio  (editable en diagrams.net / draw.io)
  - <nombre>.mmd     (Mermaid, editable como texto; draw.io puede importarlo)
  - <nombre>.png     (render para el informe, vía mermaid-cli)
Uso: python docs/diagramas/generar_diagramas.py [--png]
"""
import html
import os
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent

# ============================================================== modelos de clases
# clase: (nombre, estereotipo, [atributos], [operaciones], (col, fila), color)
ENT, SVC, DTO, FE, INF = "#dae8fc", "#d5e8d4", "#fff2cc", "#f5f5f5", "#e1d5e7"

DOMINIO = {
    "title": "UML de dominio (modelo interno) - Viña Urbana",
    "classes": [
        ("Credencial", "entity · auth", ["+id: UUID", "+email: String", "-passwordHash: Argon2id", "+rol: Rol", "+estado: EstadoCuenta",
                                          "-intentosFallidos: int", "-bloqueadoHasta: DateTime"], [], (0, 0), ENT),
        ("Sesion", "entity · auth", ["+jti: UUID", "+userId: UUID", "+exp: DateTime", "+revocada: bool"], [], (0, 1), ENT),
        ("PerfilCliente", "entity · clients", ["+userId: UUID", "+nombre: String", "+email: String", "+telefono: String",
                                                "+fechaNacimiento: Date", "+estado: EstadoCuenta"], [], (1, 0), ENT),
        ("Direccion", "value object", ["+calle: String", "+numero: String", "+depto: String", "+comuna: String", "+region: Region"], [], (1, 1), ENT),
        ("MensajeContacto", "entity · clients", ["+id: UUID", "+nombre: String", "+email: String", "+asunto: Asunto",
                                                  "+mensaje: String", "+estado: EstadoMensaje", "+recibidoEn: DateTime"], [], (0, 2), ENT),
        ("Pedido", "entity · orders", ["+id: UUID", "+numero: int", "+clienteId: UUID", "+estado: EstadoPedido", "+subtotal: int",
                                        "+despacho: int", "+total: int", "+venceEn: DateTime", "-idempotencyKey: UUID"], [], (2, 0), ENT),
        ("DetallePedido", "entity · orders", ["+productoId: String", "+nombre: String «copia»", "+tipo: TipoVino",
                                               "+precioUnitario: int «copia»", "+cantidad: int [1..24]", "+subtotal: int"], [], (2, 1), ENT),
        ("Entrega", "value object", ["+nombreReceptor: String", "+calle, numero, depto", "+comuna: String", "+region: Region",
                                      "+telefono: String", "+indicaciones: String"], [], (2, 2), ENT),
        ("EventoPedido", "entity · orders", ["+estado: String", "+fecha: DateTime", "+actor: String"], [], (1, 2), ENT),
        ("Producto", "entity · inventory", ["+id: String", "+nombre: String", "+tipo: TipoVino", "+vina: String", "+volumenMl: int",
                                             "+gradoAlcohol: float", "+precio: int", "+imagen: String", "+recomendado: bool",
                                             "+activo: bool", "-stock: int"], [], (3, 1), ENT),
        ("ReservaStock", "entity · inventory", ["+id: UUID «= pedido.id»", "+estado: HELD|COMMITTED|RELEASED|FAILED",
                                                 "+items: Map<productoId,int>"], [], (3, 0), ENT),
        ("MovimientoStock", "entity · inventory", ["+productoId: String", "+delta: int", "+motivo: Motivo", "+actor: UUID",
                                                    "+fecha: DateTime"], [], (3, 2), ENT),
        ("Pago", "entity · payments", ["+id: UUID", "+pedidoId: UUID", "+clienteId: UUID", "+monto: int «de orders»",
                                        "+estado: EstadoPago", "+proveedor: String", "-tokenProveedor: String"], [], (4, 0), ENT),
        ("Boleta", "value object", ["+folio: int", "+neto: int", "+iva: int", "+total: int", "+emitidaEn: DateTime"], [], (4, 1), ENT),
        ("NotificacionProveedor", "entity · payments", ["+eventId: String «único»", "+token: String", "+recibidoEn: DateTime"], [], (4, 2), ENT),
        ("PaqueteDegustacion", "entity · tastings", ["+id: String", "+nombre: String", "+incluye: String[]", "+duracionMin: int",
                                                      "+precioPorPersona: int"], [], (5, 0), ENT),
        ("SesionCata", "entity · tastings", ["+fecha: Date", "+hora: Hora", "+ocupados: int [0..12]"], [], (5, 1), ENT),
        ("ReservaDegustacion", "entity · tastings", ["+id: UUID", "+clienteId: UUID", "+personas: int [1..12]", "+total: int",
                                                      "+estado: EstadoReserva", "+contacto: Contacto", "-comentarios: String «sensible»"], [], (5, 2), ENT),
        ("EventoAnalitico", "entity · analytics", ["+eventId: UUID", "+tipo: TipoEvento", "+ocurridoEn: DateTime",
                                                    "+datos: {items, total, region}"], [], (4, 3), ENT),
        ("Carrito", "cliente · no persistido", ["+items: {productoId, cantidad}[]", "«sin precios»"], [], (2, 3), FE),
    ],
    # (origen, destino, tipo, mult_origen, mult_destino, etiqueta)
    # tipos: assoc, comp, agg, dep
    "relations": [
        ("Credencial", "Sesion", "comp", "1", "0..*", "abre"),
        ("Credencial", "PerfilCliente", "assoc", "1", "0..1", "mismo userId"),
        ("PerfilCliente", "Direccion", "comp", "1", "0..1", "predeterminada"),
        ("PerfilCliente", "MensajeContacto", "assoc", "0..1", "0..*", "envía"),
        ("PerfilCliente", "Pedido", "assoc", "1", "0..*", "realiza"),
        ("Pedido", "DetallePedido", "comp", "1", "1..*", "contiene"),
        ("Pedido", "Entrega", "comp", "1", "1", "se entrega en"),
        ("Pedido", "EventoPedido", "comp", "1", "1..*", "historial"),
        ("DetallePedido", "Producto", "assoc", "0..*", "1", "copia de"),
        ("Pedido", "ReservaStock", "assoc", "1", "0..1", "reserva"),
        ("ReservaStock", "Producto", "assoc", "0..*", "1..*", "bloquea"),
        ("Producto", "MovimientoStock", "comp", "1", "0..*", "auditoría"),
        ("Pedido", "Pago", "assoc", "1", "0..*", "se paga con"),
        ("Pago", "Boleta", "comp", "1", "0..1", "emite"),
        ("Pago", "NotificacionProveedor", "assoc", "1", "0..*", "recibe"),
        ("PaqueteDegustacion", "ReservaDegustacion", "assoc", "1", "0..*", "reservado en"),
        ("SesionCata", "ReservaDegustacion", "agg", "1", "0..*", "ocupa"),
        ("PerfilCliente", "ReservaDegustacion", "assoc", "1", "0..*", "reserva"),
        ("Pedido", "EventoAnalitico", "dep", "", "", "publica (outbox)"),
        ("Carrito", "Pedido", "dep", "", "", "se convierte en (S10)"),
    ],
}

SERVICIOS = {
    "title": "UML de servicios públicos («service») y DTO",
    "classes": [
        ("AuthService", "service", [], ["+registrar(RegistroDTO): UsuarioDTO  S03", "+iniciarSesion(LoginDTO): SesionDTO  S04",
                                        "+cerrarSesion(): void  S05", "+consultarSesion(): SesionDTO  S06"], (0, 0), SVC),
        ("ClientService", "service", [], ["+consultarPerfil(): PerfilDTO  S07", "+modificarPerfil(PerfilDTO): PerfilDTO  S08",
                                          "+eliminarCuenta(): void  S09", "+enviarContacto(ContactoDTO): AcuseDTO  S22",
                                          "+listarMensajes(estado): Pagina<MensajeDTO>  S32", "+atenderMensaje(id): MensajeDTO  S33"], (1, 0), SVC),
        ("CatalogService", "service", [], ["+consultarCatalogo(filtro): Pagina<ProductoDTO>  S01",
                                           "+listarInventario(): ProductoAdminDTO[]  S23", "+crearProducto(dto): ProductoAdminDTO  S24",
                                           "+modificarProducto(id, dto): ProductoAdminDTO  S25",
                                           "+ajustarStock(id, delta, motivo): ProductoAdminDTO  S26",
                                           "+retirarProducto(id): void  S27"], (2, 0), SVC),
        ("OrderService", "service", [], ["+cotizar(items, destino): CotizacionDTO  S02", "+crearPedido(PedidoNuevoDTO, key): PedidoDTO  S10",
                                         "+anularPedido(id): PedidoDTO  S13", "+listarPedidos(estado): Pagina<PedidoDTO>  S28",
                                         "+cambiarEstado(id, estado): PedidoDTO  S29"], (3, 0), SVC),
        ("PaymentService", "service", [], ["+iniciarPago(pedidoId): InicioPagoDTO  S14", "+verificarPago(id): PagoDTO  S15",
                                           "+recibirNotificacion(evento firmado): AcuseDTO  S16"], (4, 0), SVC),
        ("TastingService", "service", [], ["+consultarPaquetes(): PaqueteDTO[]  S17", "+consultarDisponibilidad(fecha): DisponibilidadDTO  S18",
                                           "+reservar(ReservaNuevaDTO): ReservaDTO  S19", "+misReservas(): ReservaDTO[]  S20",
                                           "+cancelarReserva(id): ReservaDTO  S21", "+listarReservas(fecha): ReservaStaffDTO[]  S30",
                                           "+gestionarReserva(id, estado): ReservaStaffDTO  S31"], (5, 0), SVC),
        ("AggregationService", "service · GraphQL", [], ["+misPedidos(pagina, tamano): PaginaPedidos  S11",
                                                         "+resumenPedido(id): ResumenPedido  S12",
                                                         "+panelVentas(desde, hasta): PanelVentas  S34"], (6, 0), SVC),
        ("SesionDTO", "DTO", ["+user: {id, email, rol}", "+expiresIn: int", "«sin token: viaja en cookie HttpOnly»"], [], (0, 1), DTO),
        ("PerfilDTO", "DTO", ["+nombre", "+email", "+telefono", "+fechaNacimiento", "+direccion"], [], (1, 1), DTO),
        ("ProductoDTO", "DTO público", ["+id, nombre, tipo, vina", "+volumenMl, gradoAlcohol", "+precio, imagen", "+recomendado",
                                         "+disponible: bool «no expone stock»"], [], (2, 1), DTO),
        ("CotizacionDTO", "DTO", ["+items: LineaCotizada[]", "+noDisponibles: String[]", "+subtotal, despacho, total"], [], (3, 1), DTO),
        ("PedidoDTO", "DTO", ["+id, numero, estado", "+items: LineaDTO[]", "+subtotal, despacho, total", "+entrega", "+historial",
                              "«clienteId sólo ADMIN»"], [], (3, 2), DTO),
        ("PagoDTO", "DTO", ["+pagoId, pedidoId, estado", "+monto: int", "+boleta: BoletaDTO"], [], (4, 1), DTO),
        ("ReservaDTO", "DTO", ["+id, paquete, fecha, hora", "+personas, total, estado", "«contacto sólo staff»"], [], (5, 1), DTO),
        ("ResumenPedido", "GraphQL type", ["+orders: estado, total, items", "+inventory: producto actual", "+payments: pago, boleta"], [], (6, 1), DTO),
        ("PanelVentas", "GraphQL type", ["+analytics: ventas, top, por día", "+inventory: stockBajo"], [], (6, 2), DTO),
    ],
    "relations": [
        ("AuthService", "SesionDTO", "dep", "", "", "«use»"),
        ("ClientService", "PerfilDTO", "dep", "", "", "«use»"),
        ("CatalogService", "ProductoDTO", "dep", "", "", "«use»"),
        ("OrderService", "CotizacionDTO", "dep", "", "", "«use»"),
        ("OrderService", "PedidoDTO", "dep", "", "", "«use»"),
        ("PaymentService", "PagoDTO", "dep", "", "", "«use»"),
        ("TastingService", "ReservaDTO", "dep", "", "", "«use»"),
        ("AggregationService", "ResumenPedido", "dep", "", "", "«use»"),
        ("AggregationService", "PanelVentas", "dep", "", "", "«use»"),
        ("ResumenPedido", "PedidoDTO", "dep", "", "", "compone"),
        ("ResumenPedido", "PagoDTO", "dep", "", "", "compone"),
    ],
}

GATEWAY = {
    "title": "UML del API Gateway, políticas, secretos y GraphQL Gateway",
    "classes": [
        ("ApiGateway", "component · edge", ["+host: localhost:8443", "+tls: Certificado", "+base: /api/v1"],
         ["+handle(req): Response", "+match(verbo, ruta): RouteDefinition", "-proxy(ruta, identidad): Response"], (1, 0), INF),
        ("RouteDefinition", "config", ["+sid: String", "+method: Verbo", "+external: Patron", "+access: Acceso", "+roles: Rol[]",
                                       "+internal: Plantilla", "+query: String[]", "+headers: String[]", "+rate: ClaseLimite",
                                       "+timeout: s", "+maxBody: bytes"], [], (0, 1), "#fff2cc"),
        ("ServiceTarget", "config", ["+nombre: String", "+baseUrl: https://svc:8000", "+tls: CA interna"], [], (0, 2), "#fff2cc"),
        ("AuthenticationPolicy", "policy", ["+cookie: vu_session", "+bearer: opcional"], ["+authenticate(req): Identidad?"], (1, 1), SVC),
        ("AuthorizationPolicy", "policy", [], ["+authorize(identidad, ruta): bool"], (1, 2), SVC),
        ("RequestPolicy", "policy", ["+csrf: X-Requested-With", "+rateLimits: Map", "+maxBody", "+stripHeaders"],
         ["+check(req, ruta): Error?"], (2, 1), SVC),
        ("AuthServiceClient", "adapter", [], ["+introspect(token): Identidad"], (2, 2), "#f8cecc"),
        ("Identidad", "value", ["+sub: UUID", "+role: Rol", "+jti: UUID"], [], (2, 3), DTO),
        ("SecretProvider", "interface · Vault", ["+addr: https://vault:8200", "-tokenFile: Path", "+cacheSeconds: 60"],
         ["+read(ruta, force): Secreto"], (3, 0), "#f8cecc"),
        ("CallerVerifier", "en cada microservicio", ["+llamadoresPermitidos: Set"], ["+require_caller(...): Contexto"], (3, 1), SVC),
        ("GraphQLGateway", "component · privado", ["+maxDepth: 4", "+maxCost: 2500", "+introspection: false", "+batching: false"],
         ["+execute(op, ctx): Resultado"], (4, 0), INF),
        ("Schema", "graphql", ["+Query: misPedidos, resumenPedido, panelVentas"], [], (4, 1), "#fff2cc"),
        ("Resolver", "graphql", [], ["+resolve(parent, args, ctx)", "+requireRole(roles)"], (4, 2), SVC),
        ("DataLoader", "batching", ["+maxBatch: 100"], ["+load(id)", "-batch(ids)"], (5, 1), SVC),
        ("SubsystemAdapter", "adapter REST", ["+target: orders|inventory|payments|analytics", "+timeout: 3 s"],
         ["+call(ruta, ctx): JSON"], (5, 2), "#f8cecc"),
        ("InventoryGrpcClient", "gRPC · orders", ["+target: inventory:50051", "+mTLS: cert orders"],
         ["+quote() 1s", "+reserve() 2s", "+commit() 2s", "+release() 2s"], (5, 0), "#f8cecc"),
    ],
    "relations": [
        ("ApiGateway", "RouteDefinition", "comp", "1", "1..*", "publica"),
        ("RouteDefinition", "ServiceTarget", "assoc", "0..*", "1", "destino"),
        ("ApiGateway", "AuthenticationPolicy", "assoc", "1", "1", "aplica"),
        ("ApiGateway", "AuthorizationPolicy", "assoc", "1", "1", "aplica"),
        ("ApiGateway", "RequestPolicy", "assoc", "1", "1", "aplica"),
        ("AuthenticationPolicy", "AuthServiceClient", "dep", "", "", "«use»"),
        ("AuthServiceClient", "Identidad", "dep", "", "", "«create»"),
        ("AuthorizationPolicy", "RouteDefinition", "dep", "", "", "roles"),
        ("ApiGateway", "SecretProvider", "dep", "", "", "credencial por tramo"),
        ("ServiceTarget", "CallerVerifier", "dep", "", "", "verifica"),
        ("GraphQLGateway", "Schema", "comp", "1", "1", ""),
        ("Schema", "Resolver", "comp", "1", "1..*", ""),
        ("Resolver", "DataLoader", "dep", "", "", "«use»"),
        ("Resolver", "SubsystemAdapter", "dep", "", "", "«use»"),
        ("DataLoader", "SubsystemAdapter", "dep", "", "", "lote"),
        ("SubsystemAdapter", "SecretProvider", "dep", "", "", "credencial"),
        ("GraphQLGateway", "SecretProvider", "dep", "", "", "verifica gateway"),
        ("InventoryGrpcClient", "SecretProvider", "dep", "", "", "(sin TLS)"),
    ],
}

# ============================================================== Mermaid (flujos)
MERMAID_FLOWS = {
    "mapa_sistemas_despliegue": """flowchart TB
  B(["Cliente HTTP<br/>(frontend v1.0 a futuro · Postman · pruebas)"])
  PROV(["Proveedor de pagos (tercero)<br/>PagoSeguro Sandbox :8090"])
  subgraph EDGE["Red edge · única con puertos publicados"]
    GW["API Gateway :8443 · TLS<br/>rutas explícitas · authN/authZ · CSRF · límites"]
  end
  subgraph BACK["Red backend · internal (sin acceso desde el host)"]
    direction TB
    GQL["GraphQL Gateway (privado)"]
    subgraph TX["Servicios transaccionales"]
      AUTH["Auth Service"]
      CLI["clients"]
      INV["inventory<br/>REST + gRPC"]
      ORD["orders"]
      PAY["payments"]
      TAS["tastings"]
    end
    ANA["analytics (reportes)"]
  end
  subgraph INFRA["Redes data y secrets · internal"]
    MDB[("MongoDB · TLS<br/>1 base + 1 usuario por servicio")]
    V[("Vault · KV v2<br/>1 token y 1 política por servicio")]
  end
  B -->|"HTTPS /api/v1 + cookie HttpOnly"| GW
  B -.->|"redirección de pago"| PROV
  PROV -->|"webhook firmado HMAC"| GW
  GW -->|"HTTPS + credencial del tramo<br/>+ identidad verificada"| TX
  GW -->|"POST /graphql"| GQL
  GQL -->|"REST + DataLoader"| ORD & INV & PAY & ANA
  ORD ==>|"gRPC mTLS unary"| INV
  ORD -.->|"outbox"| ANA
  TAS -.->|"outbox"| ANA
  PAY -->|"resultado de pago"| ORD
  PAY -->|"API comercio · red egress"| PROV
  TX --- INFRA
  ANA --- MDB
""",
    "secuencia_compra_pago": """sequenceDiagram
  autonumber
  actor C as Cliente (app / Postman)
  participant GW as API Gateway
  participant A as Auth
  participant O as orders
  participant I as inventory (gRPC)
  participant P as payments
  participant PR as Proveedor (sandbox)
  participant AN as analytics
  C->>GW: POST /api/v1/orders {items, entrega} + Idempotency-Key (cookie)
  GW->>A: introspect(token) [credencial gateway→auth]
  A-->>GW: {sub, role: CLIENTE, jti}
  GW->>O: POST /orders + X-User-Id/Role verificados
  O->>I: QuoteItems(items) — precios oficiales (plazo 1 s)
  O->>I: ReserveStock(pedidoId, items) — idempotente (plazo 2 s)
  alt sin stock
    I-->>O: FAILED_PRECONDITION
    O-->>C: 409 PRODUCTS_UNAVAILABLE
  else inventory no responde
    O->>I: ReleaseReservation (compensación idempotente)
    O-->>C: 503 sin crear pedido
  end
  I-->>O: HELD
  O-->>C: 201 PENDIENTE_PAGO (vence en 15 min)
  C->>GW: POST /api/v1/payments {pedidoId}
  GW->>P: POST /payments
  P->>O: GET /internal/orders/{id} → monto oficial
  P->>PR: crear transacción (Api-Key del comercio, desde Vault)
  P-->>C: redirectUrl
  C->>PR: paga en la página del proveedor
  PR->>GW: webhook firmado (HMAC + timestamp + event_id)
  GW->>P: POST /payments/webhook
  P->>P: valida firma, descarta event_id repetido, INICIADO→APROBADO, emite boleta
  P->>O: payment-result {APROBADO, monto}
  O->>O: PENDIENTE_PAGO→PAGADO (sólo si monto = total)
  O->>I: CommitReservation(pedidoId)
  O-)AN: outbox: order.paid (sin datos personales)
  PR-->>C: redirección a /?pago=id
  C->>GW: POST /payments/{id}/verify
  GW->>P: verify → consulta al proveedor servidor a servidor (idempotente)
  P-->>C: APROBADO + boleta
""",
    "secuencia_autorizada_denegada": """sequenceDiagram
  autonumber
  actor A as Cliente A
  actor B as Cliente B
  participant GW as API Gateway
  participant AU as Auth
  participant G as GraphQL Gateway
  participant O as orders
  A->>GW: POST /api/v1/graphql resumenPedido(id=X)
  GW->>AU: introspect(cookie A)
  AU-->>GW: activo, sub=A, rol=CLIENTE
  GW->>G: + X-Caller-Id gateway, credencial del tramo, X-User-Id=A
  G->>G: valida identidad de servicio, profundidad y costo
  G->>O: GET /internal/orders/X (credencial graphql→orders, usuario A)
  O->>O: pedido.clienteId == A ✔
  O-->>G: 200 pedido
  G-->>A: data.resumenPedido = {...}
  B->>GW: POST /api/v1/graphql resumenPedido(id=X)
  GW->>AU: introspect(cookie B)
  AU-->>GW: activo, sub=B
  GW->>G: X-User-Id=B
  G->>O: GET /internal/orders/X (usuario B)
  O->>O: pedido.clienteId ≠ B ✘
  O-->>G: 404 (no revela existencia)
  G-->>B: data.resumenPedido = null
  Note over B,O: Si B llama directo a orders:8000 sin credencial de servicio → 401 INVALID_SERVICE_IDENTITY
""",
    "estados_pedido": """stateDiagram-v2
  [*] --> PENDIENTE_PAGO: S10 crear (stock reservado)
  PENDIENTE_PAGO --> PAGADO: payments informa APROBADO y monto = total
  PENDIENTE_PAGO --> PENDIENTE_PAGO: pago RECHAZADO (puede reintentar)
  PENDIENTE_PAGO --> CANCELADO: S13 cliente anula / vence plazo de 15 min (stock liberado)
  PAGADO --> EN_PREPARACION: S29 ADMIN
  EN_PREPARACION --> DESPACHADO: S29 ADMIN
  DESPACHADO --> ENTREGADO: S29 ADMIN
  ENTREGADO --> [*]
  CANCELADO --> [*]
  note right of CANCELADO
    No se borra: queda en el historial.
    Un pago tardío se marca REQUIERE_REVERSA.
  end note
""",
}


# ============================================================== emisores
def mermaid_class(model) -> str:
    lines = ["---", f"title: {model['title']}", "---", "classDiagram", "  direction TB"]
    for name, stereo, attrs, ops, _, _ in model["classes"]:
        lines.append(f"  class {name} {{")
        lines.append(f"    <<{stereo}>>")
        for a in attrs:
            lines.append("    " + a.replace("«", "‹").replace("»", "›").replace("{", "(").replace("}", ")")
                         .replace("<", "~").replace(">", "~").replace("|", "/"))
        for o in ops:  # Mermaid: "+metodo(args) Retorno" (sin ':' tras el paréntesis)
            lines.append("    " + o.replace("): ", ") ").replace("<", "~").replace(">", "~").replace("|", "/"))
        lines.append("  }")
    arrows = {"assoc": "-->", "comp": "*--", "agg": "o--", "dep": "..>"}
    for src, dst, kind, ms, md, label in model["relations"]:
        ms_s = f' "{ms}"' if ms else ""
        md_s = f'"{md}" ' if md else ""
        lab = f" : {label}" if label else ""
        lines.append(f"  {src}{ms_s} {arrows[kind]} {md_s}{dst}{lab}")
    return "\n".join(lines) + "\n"


def drawio_class(model) -> str:
    cells, ids = [], {}
    colw, rowgap, width = 300, 40, 260
    # alto por fila = máximo de la fila
    heights = {}
    for name, stereo, attrs, ops, (col, row), _ in model["classes"]:
        h = 44 + 16 * max(1, len(attrs)) + (8 + 16 * len(ops) if ops else 0) + 8
        heights[row] = max(heights.get(row, 0), h)
    ys, acc = {}, 40
    for r in sorted(heights):
        ys[r] = acc
        acc += heights[r] + rowgap + 60
    n = 2
    for name, stereo, attrs, ops, (col, row), color in model["classes"]:
        cid = f"c{n}"; n += 1
        ids[name] = cid
        h = 44 + 16 * max(1, len(attrs)) + (8 + 16 * len(ops) if ops else 0) + 8
        title = f"«{stereo}»<br><b>{html.escape(name)}</b>"
        cells.append(f'<mxCell id="{cid}" value="{html.escape(title)}" style="swimlane;fontStyle=0;align=center;verticalAlign=top;'
                     f'childLayout=stackLayout;horizontal=1;startSize=40;horizontalStack=0;resizeParent=1;resizeParentMax=0;'
                     f'resizeLast=0;collapsible=0;marginBottom=0;html=1;whiteSpace=wrap;fillColor={color};strokeColor=#666666;" '
                     f'vertex="1" parent="1"><mxGeometry x="{40 + col * colw}" y="{ys[row]}" width="{width}" height="{h}" as="geometry"/></mxCell>')
        attr_txt = "<br>".join(html.escape(a) for a in attrs) or "&nbsp;"
        cells.append(f'<mxCell id="{cid}a" value="{html.escape(attr_txt)}" style="text;strokeColor=none;fillColor=none;align=left;'
                     f'verticalAlign=top;spacingLeft=4;spacingRight=4;overflow=hidden;rotatable=0;html=1;fontSize=11;" vertex="1" '
                     f'parent="{cid}"><mxGeometry y="40" width="{width}" height="{16 * max(1, len(attrs)) + 4}" as="geometry"/></mxCell>')
        if ops:
            y = 44 + 16 * max(1, len(attrs))
            cells.append(f'<mxCell id="{cid}l" value="" style="line;strokeWidth=1;fillColor=none;align=left;verticalAlign=middle;'
                         f'spacingTop=-1;spacingLeft=3;spacingRight=3;rotatable=0;labelPosition=right;points=[];" vertex="1" '
                         f'parent="{cid}"><mxGeometry y="{y}" width="{width}" height="8" as="geometry"/></mxCell>')
            ops_txt = "<br>".join(html.escape(o) for o in ops)
            cells.append(f'<mxCell id="{cid}o" value="{html.escape(ops_txt)}" style="text;strokeColor=none;fillColor=none;align=left;'
                         f'verticalAlign=top;spacingLeft=4;spacingRight=4;overflow=hidden;rotatable=0;html=1;fontSize=11;" vertex="1" '
                         f'parent="{cid}"><mxGeometry y="{y + 8}" width="{width}" height="{16 * len(ops) + 4}" as="geometry"/></mxCell>')
    styles = {
        "assoc": "endArrow=open;endFill=0;",
        "comp": "endArrow=none;startArrow=diamondThin;startFill=1;startSize=14;",
        "agg": "endArrow=none;startArrow=diamondThin;startFill=0;startSize=14;",
        "dep": "endArrow=open;endFill=0;dashed=1;",
    }
    for i, (src, dst, kind, ms, md, label) in enumerate(model["relations"]):
        eid = f"e{i}"
        cells.append(f'<mxCell id="{eid}" value="{html.escape(label)}" style="{styles[kind]}html=1;rounded=0;fontSize=10;'
                     f'labelBackgroundColor=#ffffff;" edge="1" parent="1" source="{ids[src]}" target="{ids[dst]}">'
                     f'<mxGeometry relative="1" as="geometry"/></mxCell>')
        for suffix, mult, x, align in (("s", ms, -0.85, "left"), ("t", md, 0.85, "right")):
            if mult:
                cells.append(f'<mxCell id="{eid}{suffix}" value="{html.escape(mult)}" style="edgeLabel;resizable=0;html=1;'
                             f'align={align};verticalAlign=bottom;fontSize=11;fontStyle=1;" connectable="0" vertex="1" parent="{eid}">'
                             f'<mxGeometry x="{x}" relative="1" as="geometry"><mxPoint as="offset"/></mxGeometry></mxCell>')
    body = "".join(cells)
    return ('<mxfile host="generar_diagramas.py"><diagram name="' + html.escape(model["title"]) + '"><mxGraphModel dx="1600" dy="900" '
            'grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
            'pageWidth="2400" pageHeight="1600" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
            + body + "</root></mxGraphModel></diagram></mxfile>\n")


def render(name: str):
    mmdc = os.getenv("MMDC", "/tmp/claude-0/mmdc/node_modules/.bin/mmdc")
    cfg = os.getenv("MMDC_PUPPETEER", "/tmp/claude-0/mmdc/p.json")
    subprocess.run([mmdc, "-p", cfg, "-i", str(OUT / f"{name}.mmd"), "-o", str(OUT / f"{name}.png"), "-s", "3",
                    "-b", "white"], check=True, capture_output=True)


def main():
    for name, model in (("uml_dominio", DOMINIO), ("uml_servicios", SERVICIOS), ("uml_gateway", GATEWAY)):
        (OUT / f"{name}.mmd").write_text(mermaid_class(model), encoding="utf-8")
        (OUT / f"{name}.drawio").write_text(drawio_class(model), encoding="utf-8")
    for name, src in MERMAID_FLOWS.items():
        (OUT / f"{name}.mmd").write_text(src, encoding="utf-8")
    if "--png" in sys.argv:
        for f in sorted(OUT.glob("*.mmd")):
            render(f.stem)
            print("render", f.stem)


if __name__ == "__main__":
    main()
