#!/usr/bin/env bash
# Start (or restart) the local SearXNG instance on 127.0.0.1:8888.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
conf="${SEARXNG_CONF_DIR:-$HOME/.config/life-graph/searxng}"
mkdir -p "$conf"
if [ ! -f "$conf/settings.yml" ]; then
  sed "s/__SECRET__/$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')/" "$here/settings.yml" > "$conf/settings.yml"
fi
docker rm -f life_graph_searxng >/dev/null 2>&1 || true
docker run -d --name life_graph_searxng --restart unless-stopped \
  -p 127.0.0.1:8888:8080 \
  -v "$conf:/etc/searxng" \
  searxng/searxng:latest >/dev/null
echo "SearXNG on http://localhost:8888 (config $conf)"
