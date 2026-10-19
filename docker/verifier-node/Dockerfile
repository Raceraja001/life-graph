# Node sandbox image for the verifier chain (life_graph/services/sandbox.py),
# used for projects whose registry sets `sandbox_toolchain: node`.
#
# Same contract as docker/verifier: checks run here, read-only, with no
# network. Project dependencies are not baked in: the setup phase installs
# them into a cached directory that checks mount at /node_modules.
#
# Build:  docker build -t life-graph-verifier:node22 docker/verifier-node
FROM node:22-slim
# bash: app_e2e_pass waits on the app's port with bash's /dev/tcp.
# git: test suites commonly create throwaway repositories.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git bash ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# Never run as root; the sandbox also passes --user explicitly.
USER 65534:65534
WORKDIR /work
