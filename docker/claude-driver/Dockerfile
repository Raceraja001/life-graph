# Sandbox image for the claude_code driver (life_graph/drivers/claude_code.py).
#
# The driver used to run `claude -p ...` as a plain host subprocess: scoped
# by --allowedTools/--permission-mode, but with no OS-level boundary behind
# that scoping. This image is that boundary — the CLI runs here instead,
# writable only inside the mounted worktree, with everything else from the
# host (other projects, .env, credentials besides its own token) absent.
#
# The `claude` binary is NOT vendored in git (it's a ~200MB signed release
# artifact under Anthropic's own license) — build.sh copies it in from a
# working local install at build time.
#
# Build: docker/claude-driver/build.sh
FROM ghcr.io/astral-sh/uv:0.12.14 AS uv
# Bun for projects on `sandbox_toolchain: bun`: the same pinned binary as
# docker/verifier-node (a unit test keeps the pins equal), so the agent runs
# its project's tests with the runtime the verifiers use.
FROM oven/bun:1.4.5@sha256:3aa040e5445efa09d75bb428a64ba50db13e2b3ac9b6b0c7f145615f62b2ee18 AS bun

FROM python:3.12-slim
# git: the CLI's own Bash tool uses it for context (git diff/log), not for
# committing — landing commits happen on the host afterward, via hardened git.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# The verifier image's toolchain, same pins (docker/verifier/Dockerfile; a unit
# test keeps them equal). The project's cached verifier venv is mounted
# read-only at /venv with --system-site-packages, so these are the pytest/ruff
# /mypy it falls back to, exactly as in the verifiers. Installed at build time:
# the runtime's egress allowlist reaches no package index.
COPY --from=uv /uv /usr/local/bin/uv
RUN pip install --no-cache-dir "pytest==9.1.1" "ruff==0.16.1" "mypy==1.15.0"
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun
RUN ln -s /usr/local/bin/bun /usr/local/bin/bunx && bun --version
COPY claude-bin /usr/local/bin/claude
RUN chmod +x /usr/local/bin/claude
# Never run as root; the sandbox also passes --user explicitly.
USER 65534:65534
WORKDIR /work
