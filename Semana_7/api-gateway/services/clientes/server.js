const express = require('express');
const clientesRoutes = require('./routes/clientes.routes');

const app = express();
app.use(express.json());

app.use('/clientes', clientesRoutes);

const PORT = 4002;
app.listen(PORT, () => {
  console.log(`API de clientes corriendo en http://localhost:${PORT}`);
});
