const express = require('express');
const router = express.Router();

let clientes = [
  { id: 1, nombre: 'María Pérez', email: 'maria@correo.cl' },
  { id: 2, nombre: 'Juan Soto', email: 'juan@correo.cl' },
];

router.get('/', (req, res) => {
  res.json(clientes);
});

router.get('/:id', (req, res) => {
  const cliente = clientes.find(c => c.id === Number(req.params.id));
  if (!cliente) return res.status(404).json({ error: 'Cliente no encontrado' });
  res.json(cliente);
});

router.post('/', (req, res) => {
  const nuevo = { id: clientes.length + 1, ...req.body };
  clientes.push(nuevo);
  res.status(201).json(nuevo);
});

module.exports = router;
