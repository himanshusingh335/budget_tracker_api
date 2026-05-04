FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY static/ ./static/
COPY data/ ./data/
COPY models/ ./models/

EXPOSE 8502

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8502", "--workers", "1"]
