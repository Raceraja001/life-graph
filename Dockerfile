# syntax=docker/dockerfile:1
# ── Life Graph Memory Service ─────────────────────────────────
# Multi-stage build for minimal production image.
# Supports both API server and ARQ worker via CMD override.
#
# Dependencies come from uv.lock, exactly (audit P1, 2026-11-20). Until then
# this image installed `pip install -r <ranges read out of pyproject.toml>`,
# so every rebuild resolved afresh and could ship versions CI never tested,
# on Python 3.11 while CI and the host deployment run 3.12. `uv sync
# --locked` installs the locked versions and checks every download against
# the sha256 recorded in uv.lock; it also fails the build outright when
# pyproject.toml and uv.lock disagree, rather than quietly using either.

ARG PYTHON_IMAGE=python:3.12-slim

FROM ${PYTHON_IMAGE} AS builder
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Same uv version the CI lockfile job uses, so the lock is read the same way.
RUN pip install --no-cache-dir uv==0.12.14

# The venv lives at a fixed path and is copied whole into the runtime stage.
# Never let uv fetch its own interpreter: the venv must point at the image's
# /usr/local/bin/python3.12, which the runtime stage has too.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON=/usr/local/bin/python3.12 \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Dependencies first, without the project, so an ordinary life_graph/ code
# change doesn't bust the (slow: torch/spacy/etc) deps layer — only a
# pyproject.toml or uv.lock change does. Extras: the same set this image has
# always carried (multimodal + local-nlp); torch is the CPU build, which the
# lock pins (see [tool.uv.sources] in pyproject.toml).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project \
    --extra multimodal --extra local-nlp

# The project itself, non-editable. hatchling needs the readme and the
# alembic tree it force-includes into the wheel.
COPY README.md alembic.ini ./
COPY alembic/ ./alembic/
COPY life_graph/ ./life_graph/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable \
    --extra multimodal --extra local-nlp

# spaCy model (Tier 2 NLP extraction). It is not on PyPI, so it cannot be in
# uv.lock; pinned by URL + sha256 instead. Installed AFTER the last `uv sync`,
# which would otherwise remove it as not-in-the-lock. The model version must
# stay compatible with the locked spaCy (3.8.x <-> en_core_web_sm 3.8.0).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /opt/venv/bin/python \
    "en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl#sha256=1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85"

# ── Production image ─────────────────────────────────────────
FROM ${PYTHON_IMAGE}

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

# The locked environment from the builder. Its interpreter symlink points at
# /usr/local/bin/python3.12, present here because both stages share the base.
COPY --from=builder /opt/venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

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
