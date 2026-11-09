# Imagen común de los microservicios Python. SERVICE indica qué servicio se copia.
FROM python:3.12-slim
ARG SERVICE
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 SERVICE_NAME=${SERVICE} \
    PYTHONPATH=/app/common:/app/service PORT=8000
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common /app/common
COPY proto /app/proto
COPY services/${SERVICE} /app/service
# Los stubs gRPC se regeneran en la imagen para coincidir con la versión instalada.
RUN if [ -f /app/service/inventory_pb2.py ]; then \
      python -m grpc_tools.protoc -I /app/proto --python_out=/app/service --grpc_python_out=/app/service /app/proto/inventory.proto; fi \
 && useradd -r -u 10001 app
USER 10001
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD python -c "import httpx,os,sys; sys.exit(0 if httpx.get(f'https://localhost:{os.environ[\"PORT\"]}/health', verify=os.environ['TLS_CA_FILE']).status_code==200 else 1)"
CMD ["python", "/app/service/app.py"]
