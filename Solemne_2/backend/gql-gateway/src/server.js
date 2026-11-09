// GraphQL Gateway privado de Viña Urbana.
// - Sólo acepta llamadas del API Gateway (identidad de servicio "gateway").
// - Usa la identidad de usuario ya verificada (X-User-Id / X-User-Role).
// - Agrega orders + inventory + payments (pedidos) y analytics + inventory (panel).
// - Límites: profundidad, costo, tamaño de página, plazos por llamada y errores parciales.
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const https = require('node:https');
const http = require('node:http');
const crypto = require('node:crypto');
const express = require('express');
const { ApolloServer } = require('@apollo/server');
const { expressMiddleware } = require('@as-integrations/express5');
const DataLoader = require('dataloader');
const { GraphQLError, Kind, getNullableType, isListType } = require('graphql');

const env = process.env;
const PORT = Number(env.PORT || 4000);
const TLS = (env.TLS_ENABLED || 'true') === 'true';
const MAX_DEPTH = Number(env.GRAPHQL_MAX_DEPTH || 4); // profundidad máxima que usa el frontend
const MAX_COST = Number(env.GRAPHQL_MAX_COST || 2500);
const DOWNSTREAM_TIMEOUT_MS = Number(env.DOWNSTREAM_TIMEOUT_MS || 3000);
const TARGETS = {
  orders: env.ORDERS_URL,
  inventory: env.INVENTORY_URL,
  payments: env.PAYMENTS_URL,
  analytics: env.ANALYTICS_URL,
};

// ------------------------------------------------------------------ logs (sin secretos ni datos personales)
function log(level, msg, extra = {}) {
  process.stdout.write(JSON.stringify({ ts: new Date().toISOString(), level, service: 'graphql', msg, ...extra }) + '\n');
}

// ------------------------------------------------------------------ Vault (token propio en archivo, caché 60 s)
const cache = new Map();
async function readSecret(p, force = false) {
  const hit = cache.get(p);
  if (hit && !force && Date.now() - hit.t < 60_000) return hit.v;
  try {
    const token = fs.readFileSync(env.VAULT_TOKEN_FILE, 'utf8').trim();
    const res = await fetch(`${env.VAULT_ADDR}/v1/secret/data/${p}`, {
      headers: { 'X-Vault-Token': token },
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) throw new Error(`vault ${res.status}`);
    const v = (await res.json()).data.data;
    cache.set(p, { t: Date.now(), v });
    return v;
  } catch (err) {
    if (hit) { log('WARN', 'vault_unavailable_using_cached', { path: p }); return hit.v; }
    throw new GraphQLError('Servicio temporalmente no disponible', { extensions: { code: 'SECRETS_UNAVAILABLE' } });
  }
}

function safeEqual(a, b) {
  const x = Buffer.from(String(a)); const y = Buffer.from(String(b));
  return x.length === y.length && crypto.timingSafeEqual(x, y);
}

// ------------------------------------------------------------------ llamadas a subsistemas
async function callService(target, urlPath, ctx, retry = true) {
  const { token } = await readSecret(`internal/${target}/graphql`, !retry);
  let res;
  try {
    res = await fetch(`${TARGETS[target]}${urlPath}`, {
      headers: {
        'X-Caller-Id': 'graphql', 'X-Service-Token': token, 'X-Request-Id': ctx.requestId,
        'X-User-Id': ctx.user.id, 'X-User-Role': ctx.user.role,
      },
      signal: AbortSignal.timeout(DOWNSTREAM_TIMEOUT_MS),
    });
    // Credencial del tramo rotada: se relee desde Vault y se reintenta una vez.
    if (res.status === 401 && retry) return callService(target, urlPath, ctx, false);
  } catch (err) {
    log('WARN', 'dependency_unavailable', { target, requestId: ctx.requestId });
    throw new GraphQLError(`${target} no disponible`, { extensions: { code: 'DEPENDENCY_UNAVAILABLE', service: target } });
  }
  if (res.status === 404) return null;
  if (res.status === 403) throw new GraphQLError('No autorizado', { extensions: { code: 'FORBIDDEN' } });
  if (!res.ok) throw new GraphQLError(`${target} respondió con error`, { extensions: { code: 'DEPENDENCY_ERROR', service: target } });
  return res.json();
}

function createLoaders(ctx) {
  return {
    // Una sola llamada a inventory por solicitud GraphQL, sin importar cuántos ítems haya.
    producto: new DataLoader(async (ids) => {
      const data = await callService('inventory', `/internal/products/batch?ids=${ids.map(encodeURIComponent).join(',')}`, ctx);
      const byId = new Map((data?.items || []).map((p) => [p.id, p]));
      return ids.map((id) => byId.get(id) || null);
    }, { maxBatchSize: 100 }),
    // Una sola llamada a payments para todos los pedidos de la página.
    pago: new DataLoader(async (ids) => {
      const data = await callService('payments', `/internal/payments?pedidoIds=${ids.map(encodeURIComponent).join(',')}`, ctx);
      const byOrder = new Map((data?.items || []).map((p) => [p.pedidoId, p]));
      return ids.map((id) => byOrder.get(id) || null);
    }, { maxBatchSize: 50 }),
  };
}

// ------------------------------------------------------------------ autorización
function requireRole(ctx, ...roles) {
  if (!roles.includes(ctx.user.role)) {
    throw new GraphQLError('Tu rol no permite esta consulta', { extensions: { code: 'FORBIDDEN' } });
  }
}

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

const resolvers = {
  Query: {
    misPedidos: async (_, { pagina, tamano }, ctx) => {
      requireRole(ctx, 'CLIENTE');
      if (pagina < 1 || tamano < 1 || tamano > 10) {
        throw new GraphQLError('Paginación inválida (tamano entre 1 y 10)', { extensions: { code: 'BAD_USER_INPUT' } });
      }
      return callService('orders', `/internal/orders?pagina=${pagina}&tamano=${tamano}`, ctx);
    },
    resumenPedido: async (_, { id }, ctx) => {
      requireRole(ctx, 'CLIENTE', 'ADMIN');
      if (!/^[A-Za-z0-9-]{1,64}$/.test(id)) throw new GraphQLError('ID inválido', { extensions: { code: 'BAD_USER_INPUT' } });
      // orders aplica la regla de propiedad: si no es tuyo responde 404 y aquí se devuelve null.
      return callService('orders', `/internal/orders/${id}`, ctx);
    },
    panelVentas: async (_, { desde, hasta }, ctx) => {
      requireRole(ctx, 'ADMIN');
      if (!DATE_RE.test(desde) || !DATE_RE.test(hasta)) {
        throw new GraphQLError('Fechas en formato AAAA-MM-DD', { extensions: { code: 'BAD_USER_INPUT' } });
      }
      return callService('analytics', `/internal/sales-summary?desde=${desde}&hasta=${hasta}`, ctx);
    },
  },
  ResumenPedido: {
    pago: (order, _, ctx) => ctx.loaders.pago.load(order.id),
    clienteId: (order, _, ctx) => {
      if (ctx.user.role !== 'ADMIN') {
        throw new GraphQLError('Campo restringido a administración', { extensions: { code: 'FORBIDDEN_FIELD' } });
      }
      return order.clienteId;
    },
  },
  ItemPedido: {
    producto: async (item, _, ctx) => {
      const p = await ctx.loaders.producto.load(item.productoId);
      return p && { id: p.id, nombre: p.nombre, tipo: p.tipo, imagen: p.imagen, disponible: p.disponible, precioActual: p.precio };
    },
  },
  Pago: { id: (p) => p.pagoId },
  PanelVentas: {
    stockBajo: async (_, __, ctx) => (await callService('inventory', '/internal/products/low-stock?umbral=5', ctx))?.items || [],
  },
};

// ------------------------------------------------------------------ límite de profundidad
// Implementación propia: recorre fragmentos con un conjunto de visitados, de modo que un
// ciclo de fragmentos no provoca recursión infinita (la librería graphql-depth-limit
// respondía 500 ante ese caso; lo detectó la prueba G02).
function depthLimitRule(max) {
  return (context) => {
    const fragments = Object.create(null);
    for (const def of context.getDocument().definitions) {
      if (def.kind === Kind.FRAGMENT_DEFINITION) fragments[def.name.value] = def;
    }
    const measure = (selectionSet, depth, visited) => {
      let deepest = depth;
      for (const sel of selectionSet.selections) {
        if (sel.kind === Kind.FIELD && sel.selectionSet) {
          deepest = Math.max(deepest, measure(sel.selectionSet, depth + 1, visited));
        } else if (sel.kind === Kind.INLINE_FRAGMENT) {
          deepest = Math.max(deepest, measure(sel.selectionSet, depth, visited));
        } else if (sel.kind === Kind.FRAGMENT_SPREAD) {
          const name = sel.name.value;
          if (visited.has(name) || !fragments[name]) continue; // el ciclo lo reporta NoFragmentCycles
          deepest = Math.max(deepest, measure(fragments[name].selectionSet, depth, new Set([...visited, name])));
        }
      }
      return deepest;
    };
    return {
      OperationDefinition(node) {
        const depth = measure(node.selectionSet, 0, new Set());
        if (depth > max) {
          context.reportError(new GraphQLError(`Consulta demasiado profunda (${depth} > ${max})`,
            { nodes: [node], extensions: { code: 'QUERY_TOO_DEEP' } }));
        }
      },
    };
  };
}

// ------------------------------------------------------------------ límite de costo de la consulta
function costLimitRule(max) {
  return (context) => {
    let total = 0; let reported = false; const stack = [1];
    return {
      Field: {
        enter(node) {
          const mult = stack[stack.length - 1];
          total += mult;
          let next = mult;
          const size = node.arguments?.find((a) => a.name.value === 'tamano');
          if (size) next *= size.value.kind === 'IntValue' ? Number(size.value.value) : 10;
          else if (context.getType() && isListType(getNullableType(context.getType()))) next *= 5;
          stack.push(next);
          if (total > max && !reported) {
            reported = true;
            context.reportError(new GraphQLError(`Consulta demasiado costosa (costo ${total} > ${max})`,
              { nodes: [node], extensions: { code: 'QUERY_TOO_COSTLY' } }));
          }
        },
        leave() { stack.pop(); },
      },
    };
  };
}

// ------------------------------------------------------------------ servidor
async function main() {
  const typeDefs = fs.readFileSync(path.join(__dirname, 'schema.graphql'), 'utf8');
  const server = new ApolloServer({
    typeDefs,
    resolvers,
    introspection: env.GRAPHQL_INTROSPECTION === 'true',
    allowBatchedHttpRequests: false,
    validationRules: [depthLimitRule(MAX_DEPTH), costLimitRule(MAX_COST)],
    includeStacktraceInErrorResponses: false,
    formatError: (formatted) => {
      const code = formatted.extensions?.code;
      if (!code || code === 'INTERNAL_SERVER_ERROR') {
        return { message: 'Error interno', extensions: { code: 'INTERNAL_SERVER_ERROR' }, path: formatted.path };
      }
      return { message: formatted.message, path: formatted.path, extensions: { code, service: formatted.extensions?.service } };
    },
  });
  await server.start();

  const app = express();
  app.disable('x-powered-by');
  app.get('/health', (_req, res) => res.json({ status: 'ok', service: 'graphql' }));

  // Identidad de servicio: sólo el API Gateway puede invocar este componente.
  app.use('/graphql', async (req, res, next) => {
    const requestId = req.get('x-request-id') || crypto.randomUUID();
    req.requestId = requestId;
    try {
      const caller = req.get('x-caller-id');
      let ok = caller === 'gateway';
      if (ok) {
        const given = req.get('x-service-token') || '';
        ok = safeEqual(given, (await readSecret('internal/graphql/gateway')).token);
        if (!ok) ok = safeEqual(given, (await readSecret('internal/graphql/gateway', true)).token); // rotación
      }
      if (!ok) {
        log('WARN', 'caller_rejected', { caller: caller || '-', requestId });
        return res.status(401).json({ error: { code: 'INVALID_SERVICE_IDENTITY', message: 'Identidad de servicio inválida', requestId } });
      }
      if (!req.get('x-user-id') || !req.get('x-user-role')) {
        return res.status(401).json({ error: { code: 'UNAUTHENTICATED', message: 'Se requiere sesión', requestId } });
      }
    } catch (err) {
      return res.status(503).json({ error: { code: 'SECRETS_UNAVAILABLE', message: 'Servicio no disponible', requestId } });
    }
    const start = Date.now();
    res.on('finish', () => log('INFO', 'request', { requestId, status: res.statusCode, duration_ms: Date.now() - start }));
    return next();
  });

  app.use('/graphql', express.json({ limit: '8kb' }), expressMiddleware(server, {
    context: async ({ req }) => {
      const ctx = { requestId: req.requestId, user: { id: req.get('x-user-id'), role: req.get('x-user-role') } };
      ctx.loaders = createLoaders(ctx);
      return ctx;
    },
  }));

  const listener = TLS
    ? https.createServer({ key: fs.readFileSync(env.TLS_KEY_FILE), cert: fs.readFileSync(env.TLS_CERT_FILE) }, app)
    : http.createServer(app);
  listener.listen(PORT, env.HOST || '0.0.0.0', () => log('INFO', 'graphql_gateway_started', { port: PORT, tls: TLS }));
}

main().catch((err) => { log('ERROR', 'startup_failed', { err: err.message }); process.exit(1); });
