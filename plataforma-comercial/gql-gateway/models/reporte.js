const mongoose = require('mongoose');

const estadoSchema = new mongoose.Schema(
    { estado: String, cantidad: Number },
    { _id: false }
);

const reporteSchema = new mongoose.Schema(
    {
        tipo: { type: String, default: 'resumen-general' },
        generadoPor: { type: String, required: true },
        resumen: {
            totalProductos: Number,
            precioPromedio: Number,
            totalPedidos: Number,
            totalClientes: Number,
            pedidosPorEstado: [estadoSchema],
        },
    },
    { timestamps: true }
);

module.exports = mongoose.model('Reporte', reporteSchema);