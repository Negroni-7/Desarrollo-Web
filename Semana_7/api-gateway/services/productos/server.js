const express = require('express');
const productosRoutes = require('./routes/productos.routes');

const app = express();
app.use(express.json());

app.use('/productos', productosRoutes);

const PORT = 4001;
app.listen(PORT, () => {
  console.log(`API de productos corriendo en http://localhost:${PORT}`);
});
