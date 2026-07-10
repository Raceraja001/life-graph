# ── Life Graph Memory Service ─────────────────────────────────
# Multi-stage build for minimal production image.
# Supports both API server and ARQ worker via CMD override.

FROM python:3.11-slim AS builder
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY life_graph/ ./life_graph/

# Install all deps with CPU-only PyTorch (no CUDA — saves ~1.8GB)
# --extra-index-url for non-torch packages, primary index is CPU-only torch
RUN pip install --no-cache-dir --prefix=/install \
    --extra-index-url https://pypi.org/simple \
    --index-url https://download.pytorch.org/whl/cpu \
    . psycopg2-binary

# ── Production image ─────────────────────────────────────────
FROM python:3.11-slim

# Runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 bash && \
    rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd -m -r -s /bin/false appuser && \
    mkdir /app && chown appuser:appuser /app

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /install/bin /usr/local/bin

# Download spaCy model (needed for Tier 2 NLP extraction)
RUN python -m spacy download en_core_web_sm

# Copy application code
COPY life_graph/ /app/life_graph/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/
COPY pyproject.toml /app/
COPY scripts/entrypoint.sh /app/scripts/entrypoint.sh
RUN chmod +x /app/scripts/entrypoint.sh

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Default: API server
# Override for worker: ["arq", "life_graph.workers.settings.WorkerSettings"]
CMD ["uvicorn", "life_graph.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
