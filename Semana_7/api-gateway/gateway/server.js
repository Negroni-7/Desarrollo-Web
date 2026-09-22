const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();

app.use((req, res, next) => {
  console.log(`[Gateway] ${req.method} ${req.originalUrl}`);
  next();
});

app.use('/api/productos', createProxyMiddleware({
  target: 'http://localhost:4001/productos',
  changeOrigin: true,
}));

app.use('/api/clientes', createProxyMiddleware({
  target: 'http://localhost:4002/clientes',
  changeOrigin: true,
}));

const PORT = 3000;
app.listen(PORT, () => {
  console.log(`API Gateway corriendo en http://localhost:${PORT}`);
});
