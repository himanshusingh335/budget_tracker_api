FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY data/ ./data/
COPY models/ ./models/

# Bake the ONNX embedding model into the image so it's self-contained and
# /classify never touches the network at runtime
RUN python -m app.embedder

EXPOSE 8502

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8502", "--workers", "1", "--log-config", "app/uvicorn_log_config.json"]
