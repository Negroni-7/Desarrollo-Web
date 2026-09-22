const express = require('express');
const router = express.Router();

let productos = [
  { id: 1, nombre: 'Carmenere Reserva 2021', tipo: 'tinto', precio: 22900 },
  { id: 2, nombre: 'Sauvignon Blanc Costa', tipo: 'blanco', precio: 24900 },
  { id: 3, nombre: 'Pinot Noir Rosé', tipo: 'rosado', precio: 16900 },
];

router.get('/', (req, res) => {
  const { tipo } = req.query;
  const resultado = tipo ? productos.filter(p => p.tipo === tipo) : productos;
  res.json(resultado);
});

router.get('/:id', (req, res) => {
  const producto = productos.find(p => p.id === Number(req.params.id));
  if (!producto) return res.status(404).json({ error: 'Producto no encontrado' });
  res.json(producto);
});

router.post('/', (req, res) => {
  const nuevo = { id: productos.length + 1, ...req.body };
  productos.push(nuevo);
  res.status(201).json(nuevo);
});

module.exports = router;
