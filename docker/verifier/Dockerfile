# Sandbox image for the verifier chain (life_graph/services/sandbox.py).
#
# Verifiers run code an agent just wrote — a test suite is arbitrary code —
# so they run here instead of on the host. The image carries a fallback
# toolchain only; a project's own dependencies are installed into a separate,
# cached venv by the sandbox's setup phase.
#
# Build:  docker build -t life-graph-verifier:py3.12 docker/verifier
FROM ghcr.io/astral-sh/uv:0.12.14 AS uv

FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
RUN pip install --no-cache-dir "pytest==9.1.1" "ruff==0.16.1"
# Never run as root; the sandbox also passes --user explicitly.
USER 65534:65534
WORKDIR /work
