# ── Stage 1: Build React frontend ─────────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci --silent
COPY frontend/ .
RUN npm run build

# ── Stage 2: Python application ───────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

# System dependencies (librdkafka-dev is optional; Kafka/confluent-kafka gracefully degrades)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gcc \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first (saves ~500 MB vs CUDA build)
RUN pip install --no-cache-dir torch==2.2.1 \
    --index-url https://download.pytorch.org/whl/cpu

# Install remaining Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/   app/
COPY ml/    ml/
COPY spark/ spark/

# Copy pre-trained model artifacts
# (recommender.pkl, rec_scaler.pkl, rec_history.npz are committed to the repo)

# Copy React production build
COPY --from=frontend /frontend/dist /app/static

# Persistent data directory for SQLite
RUN mkdir -p /app/data

# HF Spaces runs as root by default; non-root for everything else
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser

# Environment defaults — override via HF Spaces Secrets or docker-compose
ENV SERVE_STATIC=1 \
    STATIC_DIR=/app/static \
    DATABASE_URL=sqlite+aiosqlite:////app/data/flashledger.db \
    PORT=7860

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
