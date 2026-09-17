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
FROM python:3.12-slim
# git: the CLI's own Bash tool uses it for context (git diff/log), not for
# committing — landing commits happen on the host afterward, via hardened git.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY claude-bin /usr/local/bin/claude
RUN chmod +x /usr/local/bin/claude
# Never run as root; the sandbox also passes --user explicitly.
USER 65534:65534
WORKDIR /work
