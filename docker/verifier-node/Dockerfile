# Node sandbox image for the verifier chain (life_graph/services/dev/sandbox.py),
# used for projects whose registry sets `sandbox_toolchain: node`.
#
# Same contract as docker/verifier: checks run here, read-only, with no
# network. Project dependencies are not baked in: the setup phase installs
# them into a cached directory that checks mount at /node_modules.
#
# Projects on `sandbox_toolchain: bun` are checked here too: the Bun binary is
# copied in (pinned by digest, same pin as docker/claude-driver/Dockerfile; a
# unit test keeps them equal), so the image keeps real Node for npm projects.
# Multi-stage COPY of a vendor binary: the pattern OpenHands (MIT) uses.
#
# Build:  docker build -t life-graph-verifier:node22 docker/verifier-node
FROM oven/bun:1.4.5@sha256:3aa040e5445efa09d75bb428a64ba50db13e2b3ac9b6b0c7f145615f62b2ee18 AS bun

FROM node:22-slim
# bash: app_e2e_pass waits on the app's port with bash's /dev/tcp.
# git: test suites commonly create throwaway repositories.
# curl: project test suites call it (race-app's do; 2026-11-28).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git bash ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun
RUN ln -s /usr/local/bin/bun /usr/local/bin/bunx && bun --version
# Never run as root; the sandbox also passes --user explicitly.
USER 65534:65534
WORKDIR /work
