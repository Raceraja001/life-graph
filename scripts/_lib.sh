#!/usr/bin/env bash
# Shared helpers for start.sh / stop.sh / status.sh.
# Sourced, never executed directly.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PORT="${LIFE_GRAPH_API_PORT:-8080}"
DASH_PORT="${LIFE_GRAPH_DASH_PORT:-3000}"
# Postgres/Redis ports are read from the app's own settings below, NOT
# assumed to be 5432/6379. docker-compose.override.yml maps them to
# 55432/56379 precisely so they do not collide with another project's
# containers on the default ports — and on this machine they do.
DB_PORT=5432
REDIS_PORT=6379
RUN_DIR="$ROOT/.run"
LOG_DIR="$ROOT/logs"

# Colour only when stdout is a terminal, so piping to a file stays readable.
if [ -t 1 ]; then
    C_RESET=$'\033[0m'; C_CYAN=$'\033[36m'; C_GREEN=$'\033[32m'
    C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_DIM=$'\033[2m'
else
    C_RESET=; C_CYAN=; C_GREEN=; C_YELLOW=; C_RED=; C_DIM=
fi

say()  { printf '%s\n' "$*"; }
step() { printf '%s%s%s\n' "$C_YELLOW" "$*" "$C_RESET"; }
ok()   { printf '  %s%s%s\n' "$C_GREEN" "$*" "$C_RESET"; }
dim()  { printf '  %s%s%s\n' "$C_DIM" "$*" "$C_RESET"; }
warn() { printf '  %s%s%s\n' "$C_RED" "$*" "$C_RESET"; }

# The venv python, falling back to whatever python3 is on PATH. Callers that
# shell out to `ruff` etc. need .venv/bin on PATH too, so export it.
if [ -x "$ROOT/.venv/bin/python" ]; then
    PY="$ROOT/.venv/bin/python"
    export PATH="$ROOT/.venv/bin:$PATH"
else
    PY="$(command -v python3 || true)"
fi

# Ask the app where its Postgres and Redis actually are. Falls back to the
# defaults only when the config cannot be loaded at all.
load_service_ports() {
    local out
    out="$("$PY" - <<'PYEOF' 2>/dev/null
from urllib.parse import urlparse
from life_graph.config import settings
for url, default in ((settings.database_url, 5432), (settings.redis_url, 6379)):
    try:
        print(urlparse(url.split("+")[0] + "://" + url.split("://", 1)[1]).port or default)
    except Exception:
        print(default)
PYEOF
)"
    [ -n "$out" ] && { DB_PORT="$(sed -n 1p <<<"$out")"; REDIS_PORT="$(sed -n 2p <<<"$out")"; }
}

# Which container CLI can we actually talk to? This machine runs rootless
# podman, so a bare `docker info` fails even though containers are running.
COMPOSE=""
detect_compose() {
    [ -n "$COMPOSE" ] && return 0
    if docker info >/dev/null 2>&1; then COMPOSE="docker compose"
    elif podman info >/dev/null 2>&1; then
        if podman compose version >/dev/null 2>&1; then COMPOSE="podman compose"
        elif command -v podman-compose >/dev/null 2>&1; then COMPOSE="podman-compose"
        fi
    fi
    [ -n "$COMPOSE" ]
}

port_listening() { ss -ltn "sport = :$1" 2>/dev/null | grep -q LISTEN; }

# Is the process on this port ours? Only a pid we launched, or one whose cwd
# is inside this repo, may be killed. Another project's dev server on the
# same port must never be reclaimed silently — that is somebody's work.
port_is_ours() {  # port, pidfile
    local port="$1" pidfile="${2:-}" pid cwd
    pid="$(pid_on_port "$port")"; [ -n "$pid" ] || return 1
    if [ -n "$pidfile" ] && [ -f "$pidfile" ] && [ "$(cat "$pidfile" 2>/dev/null)" = "$pid" ]; then
        return 0
    fi
    cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null)" || return 1
    [[ "$cwd" == "$ROOT" || "$cwd" == "$ROOT"/* ]]
}

describe_port() {  # port -> "comm (pid N, cwd X)"
    local pid; pid="$(ss -ltnp "sport = :$1" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | head -1)"
    [ -n "$pid" ] || { printf 'unknown'; return; }
    printf '%s (pid %s%s)' "$(ps -p "$pid" -o comm= 2>/dev/null)" "$pid" \
        "$(cwd="$(readlink -f /proc/$pid/cwd 2>/dev/null)"; [ -n "$cwd" ] && printf ', cwd %s' "$cwd")"
}

# PID owning a listening port, or empty. Skips container-side sockets: a
# docker-published port is owned by docker-proxy/containerd on the host, and
# killing that would tear down the container rather than the local process.
pid_on_port() {
    local pid
    pid="$(ss -ltnp "sport = :$1" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | head -1)"
    [ -n "$pid" ] || return 0
    # rootlessport is the port forwarder for rootless podman/docker. Killing
    # it tears down the container's published port, so treat it — and the
    # daemon-side forwarders — as not-ours.
    case "$(ps -p "$pid" -o comm= 2>/dev/null)" in
        docker-proxy|containerd*|dockerd|rootlessport|conmon|slirp4netns) return 0 ;;
    esac
    printf '%s' "$pid"
}

port_is_docker() {
    local pid comm
    pid="$(ss -ltnp "sport = :$1" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | head -1)"
    [ -n "$pid" ] || return 1
    comm="$(ps -p "$pid" -o comm= 2>/dev/null)"
    [[ "$comm" == docker-proxy || "$comm" == containerd* || "$comm" == dockerd \
       || "$comm" == rootlessport || "$comm" == conmon || "$comm" == slirp4netns ]]
}

# docker compose needs group membership; say so once, plainly, instead of
# letting a raw "permission denied on /var/run/docker.sock" surface.
docker_ready() {
    if ! command -v docker >/dev/null 2>&1; then
        warn "docker not installed — skipping infrastructure"
        return 1
    fi
    if ! docker info >/dev/null 2>&1; then
        warn "cannot talk to the docker daemon"
        dim "run: sudo usermod -aG docker \$USER   # then log out and back in"
        return 1
    fi
    return 0
}

wait_for_http() {  # url, attempts, label
    local url="$1" tries="${2:-25}" label="${3:-service}" i
    printf '  %swaiting for %s%s' "$C_DIM" "$label" "$C_RESET"
    for ((i = 0; i < tries; i++)); do
        if curl -fsS -m 2 "$url" >/dev/null 2>&1; then printf ' %sOK%s\n' "$C_GREEN" "$C_RESET"; return 0; fi
        printf '.'; sleep 2
    done
    printf ' %stimeout%s\n' "$C_RED" "$C_RESET"; return 1
}

wait_for_port() {  # port, attempts, label
    local port="$1" tries="${2:-20}" label="${3:-port}" i
    printf '  %swaiting for %s%s' "$C_DIM" "$label" "$C_RESET"
    for ((i = 0; i < tries; i++)); do
        if port_listening "$port"; then printf ' %sOK%s\n' "$C_GREEN" "$C_RESET"; return 0; fi
        printf '.'; sleep 2
    done
    printf ' %stimeout%s\n' "$C_RED" "$C_RESET"; return 1
}
