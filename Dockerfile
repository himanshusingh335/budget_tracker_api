FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
# Install CPU-only torch before sentence-transformers to avoid the ~2GB CUDA build
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the sentence-transformer model so the image is self-contained
# and the first /classify request has no cold-start network penalty
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY app/ ./app/
COPY static/ ./static/
COPY data/ ./data/
COPY models/ ./models/

EXPOSE 8502

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8502", "--workers", "1"]
