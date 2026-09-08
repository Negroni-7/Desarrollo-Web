const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');

const { ApolloServer, gql } = require('apollo-server-express');
const Usuario = require('./models/usuario');

const typeDefs = gql`
    type Usuario {
        id: ID!
        nombre: String!
        pass: String!
    }
    input UsuarioInput {
        nombre: String!
        pass: String!
    }
    type Alert {
        message: String!
    }
    type Query {
        getUsuarios: [Usuario]
        getUsuarioById(id: ID!): Usuario
    }
    type Mutation {
        addUsuario(input: UsuarioInput): Usuario
        updateUsuario(id: ID!, input: UsuarioInput): Usuario
        deleteUsuario(id: ID!): Alert
    }
`;

const resolvers = {
    Query: {
        async getUsuarios(obj) {
            const usuarios = await Usuario.find();
            return usuarios;
        },
        async getUsuarioById(obj, { id }) {
            const usuarioBuscado = await Usuario.findById(id);
            return usuarioBuscado;
        }
    },
    Mutation: {
        async addUsuario(obj, { input }) {
            const usuario = new Usuario(input);
            await usuario.save();
            return usuario;
        },
        async updateUsuario(obj, { id, input }) {
            const usuario = await Usuario.findByIdAndUpdate(id, input, { new: true });
            return usuario;
        },
        async deleteUsuario(obj, { id }) {
            await Usuario.deleteOne({ _id: id });
            return { message: 'Usuario eliminado' };
        }
    }
};


const corsOptions = {
    origin: true,
    credentials: true
};

async function startServer() {
    try {
        await mongoose.connect('mongodb://localhost:27017/DBM');
        console.log('Conectado a MongoDB');
    } catch (err) {
        console.error('Error conectando a MongoDB:', err.message);
        process.exit(1);
    }

    const app = express();
    app.use(cors(corsOptions));

    const apolloServer = new ApolloServer({ typeDefs, resolvers });
    await apolloServer.start();

    apolloServer.applyMiddleware({ app, cors: false }); 


    app.listen(8090, () => {
        console.log('DWM iniciado en http://localhost:8090' + apolloServer.graphqlPath);
    });
}

startServer();