const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const {
    ApolloServer,
    gql,
    ApolloError,
    AuthenticationError,
} = require('apollo-server-express');
const Reporte = require('./models/reporte');

// ---------- Configuración (viene del archivo .env) ----------
const PORT = process.env.PORT || 4000;
const MONGO_URI = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/DBM';
const VAULT_ADDR = process.env.VAULT_ADDR || 'http://127.0.0.1:8200';
const VAULT_TOKEN = process.env.VAULT_TOKEN;
const AUTH_SERVICE_URL = process.env.AUTH_SERVICE_URL || 'http://127.0.0.1:9100';
const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:9000';

if (!VAULT_TOKEN) {
    console.error('VAULT_TOKEN no configurado (revisa el archivo .env)');
    process.exit(1);
}

// ---------- Esquema GraphQL ----------
const typeDefs = gql`
    type Producto {
        id: Int!
        name: String!
        price: Int!
    }
    type Pedido {
        id: Int!
        status: String!
    }
    type Cliente {
        id: Int!
        name: String!
        email: String!
    }
    type EstadoCantidad {
        estado: String!
        cantidad: Int!
    }
    type Resumen {
        totalProductos: Int!
        precioPromedio: Int!
        totalPedidos: Int!
        totalClientes: Int!
        pedidosPorEstado: [EstadoCantidad!]!
    }
    type Reporte {
        id: ID!
        tipo: String!
        generadoPor: String!
        creadoEn: String!
        resumen: Resumen!
    }
    type Alert {
        message: String!
    }
    type Query {
        productos: [Producto!]!
        pedidos: [Pedido!]!
        clientes: [Cliente!]!
        resumenGeneral: Resumen!
        reportes: [Reporte!]!
        reporte(id: ID!): Reporte
    }
    type Mutation {
        generarReporte(tipo: String): Reporte!
        eliminarReporte(id: ID!): Alert!
    }
`;

// ---------- Comunicación con otros servicios ----------
async function validarToken(authHeader) {
    let res;
    try {
        res = await fetch(`${AUTH_SERVICE_URL}/validate`, {
            method: 'POST',
            headers: { Authorization: authHeader || '' },
            signal: AbortSignal.timeout(5000),
        });
    } catch (err) {
        throw new ApolloError('Servicio de autenticación no disponible', 'AUTH_UNAVAILABLE');
    }
    if (!res.ok) {
        throw new ApolloError('Servicio de autenticación con error', 'AUTH_UNAVAILABLE');
    }
    return res.json(); // { active: true/false, client_id }
}

async function obtenerSecretosVault() {
    let res;
    try {
        res = await fetch(`${VAULT_ADDR}/v1/secret/data/gateway`, {
            headers: { 'X-Vault-Token': VAULT_TOKEN },
            signal: AbortSignal.timeout(5000),
        });
    } catch (err) {
        throw new ApolloError('Vault no disponible', 'VAULT_UNAVAILABLE');
    }
    if (!res.ok) {
        throw new ApolloError('No fue posible acceder a Vault', 'VAULT_ERROR');
    }
    const body = await res.json();
    return body.data.data; // { client_token, backend_shared_secret }
}

async function llamarBackend(path, ctx) {
    let res;
    try {
        res = await fetch(`${BACKEND_URL}${path}`, {
            headers: {
                'X-Gateway-Secret': ctx.backendSecret,
                'X-Authenticated-Client': ctx.clientId,
            },
            signal: AbortSignal.timeout(8000),
        });
    } catch (err) {
        throw new ApolloError(`Backend no disponible (${path})`, 'BACKEND_UNAVAILABLE');
    }
    if (!res.ok) {
        throw new ApolloError(`El backend respondió ${res.status} en ${path}`, 'BACKEND_ERROR');
    }
    return res.json();
}

// ---------- Agregación ----------
async function construirResumen(ctx) {
    const [p, o, c] = await Promise.all([
        llamarBackend('/products', ctx),
        llamarBackend('/orders', ctx),
        llamarBackend('/clients', ctx),
    ]);
    const productos = p.products;
    const pedidos = o.orders;
    const clientes = c.clients;
    const porEstado = {};
    
    pedidos.forEach((x) => {
        porEstado[x.status] = (porEstado[x.status] || 0) + 1;
    });
    
    const sumaPrecios = productos.reduce((acc, x) => acc + x.price, 0);
    return {
        totalProductos: productos.length,
        precioPromedio: productos.length ? Math.round(sumaPrecios / productos.length) : 0,
        totalPedidos: pedidos.length,
        totalClientes: clientes.length,
        pedidosPorEstado: Object.entries(porEstado).map(([estado, cantidad]) => ({
            estado,
            cantidad,
        })),
    };
}

// ---------- Resolvers ----------
const resolvers = {
    Query: {
        productos: async (_, __, ctx) => (await llamarBackend('/products', ctx)).products,
        pedidos: async (_, __, ctx) => (await llamarBackend('/orders', ctx)).orders,
        clientes: async (_, __, ctx) => (await llamarBackend('/clients', ctx)).clients,
        resumenGeneral: (_, __, ctx) => construirResumen(ctx),
        reportes: () => Reporte.find().sort({ createdAt: -1 }),
        reporte: async (_, { id }) => {
            if (!mongoose.isValidObjectId(id)) return null;
            return Reporte.findById(id);
        },
    },
    Mutation: {
        generarReporte: async (_, { tipo }, ctx) => {
            const resumen = await construirResumen(ctx);
            return Reporte.create({
                tipo: tipo || 'resumen-general',
                generadoPor: ctx.clientId,
                resumen,
            });
        },
        eliminarReporte: async (_, { id }) => {
            if (!mongoose.isValidObjectId(id)) {
                return { message: 'ID inválido' };
            }
            const r = await Reporte.deleteOne({ _id: id });
            return { message: r.deletedCount ? 'Reporte eliminado' : 'Reporte no encontrado' };
        },
    },
    Reporte: {
        creadoEn: (r) => r.createdAt.toISOString(),
    },
};

// ---------- Arranque ----------
async function startServer() {
    try {
        await mongoose.connect(MONGO_URI);
        console.log('Conectado a MongoDB');
    } catch (err) {
        console.error('Error conectando a MongoDB:', err.message);
        process.exit(1);
    }
    
    const app = express();
    app.use(cors({ origin: true, credentials: true }));
    
    const apolloServer = new ApolloServer({
        typeDefs,
        resolvers,
        // Se ejecuta en CADA petición: valida el token y trae los secretos de Vault
        context: async ({ req }) => {
            const auth = await validarToken(req.headers.authorization);
            if (!auth.active) {
                throw new AuthenticationError('Bearer token requerido o inválido');
            }
            const secretos = await obtenerSecretosVault();
            return {
                clientId: auth.client_id,
                backendSecret: secretos.backend_shared_secret,
            };
        },
    });

    await apolloServer.start();
    apolloServer.applyMiddleware({ app, cors: false });
    
    app.listen(PORT, () => {
        console.log(`GraphQL Gateway en http://localhost:${PORT}${apolloServer.graphqlPath}`);
    });
}

startServer();