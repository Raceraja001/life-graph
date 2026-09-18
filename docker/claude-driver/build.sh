#!/usr/bin/env bash
# Build the claude_code driver's sandbox image from the machine's own,
# already-authenticated `claude` install — see Dockerfile for why the
# binary isn't vendored in git.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

bin="$(command -v claude || true)"
if [ -z "$bin" ]; then
    echo "claude CLI not found on PATH — install it first (claude.ai/install.sh)" >&2
    exit 1
fi
bin="$(readlink -f "$bin")"

trap 'rm -f claude-bin' EXIT
cp "$bin" claude-bin

image="${1:-life-graph-claude-driver:latest}"
docker build -t "$image" .
echo "built $image from $bin"
