FROM node:22-alpine
ENV NODE_ENV=production PORT=8000
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY src ./src
USER node
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD node -e "require('https').get({host:'localhost',port:process.env.PORT,path:'/health',ca:require('fs').readFileSync(process.env.TLS_CA_FILE)},r=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1))"
CMD ["node", "src/server.js"]
