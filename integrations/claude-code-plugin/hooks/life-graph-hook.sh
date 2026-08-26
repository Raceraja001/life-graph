#!/usr/bin/env sh
# Plugin shim: run the Life Graph hook dispatcher with the repo importable.
#
# ${CLAUDE_PLUGIN_ROOT} is <repo>/integrations/claude-code-plugin, so the repo
# root is three levels up from this script. Prefer the repo's own virtualenv —
# a bare python3 will not have httpx or life_graph on its path.
#
# Never fails loudly: a missing interpreter must not break Claude Code.
set -u
ROOT=$(cd "$(dirname "$0")/../../.." 2>/dev/null && pwd) || exit 0
PY="$ROOT/.venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="${LIFE_GRAPH_PYTHON:-python3}"
fi
if [ -n "${PYTHONPATH:-}" ]; then
  PYTHONPATH="$ROOT:$PYTHONPATH"
else
  PYTHONPATH="$ROOT"
fi
export PYTHONPATH
exec "$PY" -m life_graph.integrations.claude_code.hook
