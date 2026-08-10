# syntax=docker/dockerfile:1
# ── Life Graph Memory Service ─────────────────────────────────
# Multi-stage build for minimal production image.
# Supports both API server and ARQ worker via CMD override.

FROM python:3.11-slim AS builder
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Dependency install is split from the source copy below so an ordinary
# life_graph/ code change doesn't bust the (slow: torch/spacy/etc) deps
# layer — only a pyproject.toml change does. The requirements list is
# read straight out of pyproject.toml (stdlib tomllib) so this step needs
# no local package build, hence no source tree yet.
COPY pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/pip \
    python -c "import tomllib; d = tomllib.load(open('pyproject.toml', 'rb')); open('requirements.lock.txt', 'w').write('\n'.join(d['project']['dependencies'] + d['project']['optional-dependencies']['multimodal']))" && \
    pip install --prefix=/install \
    --extra-index-url https://pypi.org/simple \
    --index-url https://download.pytorch.org/whl/cpu \
    -r requirements.lock.txt psycopg2-binary

COPY life_graph/ ./life_graph/

# Local package only, no deps re-resolution — fast even though it reruns
# on every code change.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install --no-deps .

# ── Production image ─────────────────────────────────────────
FROM python:3.11-slim

# Runtime dependencies
# `git` is required at run time (not just build time): drivers/workdir.py
# shells out to `git worktree add/remove` to isolate agent_task dispatches,
# and services/verifiers.py's diff-scoped verifiers shell out to `git diff`.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 bash git tesseract-ocr tesseract-ocr-eng tesseract-ocr-tam && \
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
