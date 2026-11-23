# Production-ready multi-platform build for EHR Media Intelligence Platform
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend \
    SQLITE_DB_PATH=/app/data/ehr_intelligence.db \
    CHROMA_PERSIST_DIRECTORY=/app/data/chroma_db \
    FRONTEND_DIR=/app/frontend \
    API_HOST=0.0.0.0 \
    API_PORT=8000

# Install curl and ca-certificates for health checks and secure SSL connections
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies with trusted hosts for corporate proxy resilience
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    --trusted-host pypi.python.org \
    -r /app/backend/requirements.txt

# Copy application source code and static frontend assets
COPY backend /app/backend
COPY frontend /app/frontend

# Create storage directory for SQLite database and vector embeddings
RUN mkdir -p /app/data && chmod +x /app/backend/scripts/docker-entrypoint.sh

# Expose standard application port
EXPOSE 8000

# Container healthcheck using the built-in health endpoint
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

WORKDIR /app/backend

# Entrypoint auto-seeds synthetic data on first run then starts uvicorn
ENTRYPOINT ["/bin/sh", "/app/backend/scripts/docker-entrypoint.sh"]
