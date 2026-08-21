#!/usr/bin/env bash
#
# Start the Life Graph application (Linux).
#
# Linux port of start.ps1. Same hybrid layout the PowerShell version uses:
#   - Postgres + Redis : docker containers, started once and left running
#   - Backend API      : local uvicorn on :8080, avoiding the docker port clash
#   - Dashboard        : local Next.js dev server on :3000
#
# The PowerShell version opens minimised windows for the long-running
# processes. There is no equivalent here, so each is backgrounded with its
# output in logs/ and its pid in .run/ — which is also what lets stop.sh kill
# exactly what start.sh launched rather than guessing from the port.
#
#   ./start.sh              # API + dashboard (assumes Postgres/Redis running)
#   ./start.sh --all        # everything, including Postgres/Redis
#   ./start.sh --backend    # only the backend API
#   ./start.sh --dashboard  # only the dashboard
#   ./start.sh --infra      # only Postgres + Redis
#
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/scripts/_lib.sh"

BACKEND=0 DASHBOARD=0 INFRA=0 ALL=0
while [ $# -gt 0 ]; do
    case "$1" in
        --backend)   BACKEND=1 ;;
        --dashboard) DASHBOARD=1 ;;
        --infra)     INFRA=1 ;;
        --all)       ALL=1 ;;
        -h|--help)   sed -n '3,19p' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) warn "unknown option: $1"; exit 2 ;;
    esac
    shift
done
# No flags at all means backend + dashboard, matching start.ps1.
BOTH=0
[ $BACKEND -eq 0 ] && [ $DASHBOARD -eq 0 ] && [ $INFRA -eq 0 ] && [ $ALL -eq 0 ] && BOTH=1

mkdir -p "$RUN_DIR" "$LOG_DIR"
load_service_ports
printf '\n  %sLife Graph - Starting...%s\n\n' "$C_CYAN" "$C_RESET"

# ── Infrastructure ────────────────────────────────────────────
if [ $INFRA -eq 1 ] || [ $ALL -eq 1 ]; then
    step "[infra] Starting Postgres + Redis..."
    if detect_compose; then
        dim "using: $COMPOSE"
        if (cd "$ROOT" && timeout 120 $COMPOSE up -d postgres redis) >"$LOG_DIR/infra.log" 2>&1; then
            grep -aiE 'started|running|created|healthy' "$LOG_DIR/infra.log" | sed 's/^/  /' || true
        else
            warn "$COMPOSE failed — see logs/infra.log"
        fi
        wait_for_port "$DB_PORT" 20 "Postgres on :$DB_PORT"
    else
        warn "no usable container runtime (tried docker, podman)"
    fi
fi

# ── Backend API ───────────────────────────────────────────────
if [ $BACKEND -eq 1 ] || [ $BOTH -eq 1 ] || [ $ALL -eq 1 ]; then
    if ! port_listening "$DB_PORT"; then
        warn "[backend] Postgres is not listening on :$DB_PORT"
        dim "run: ./start.sh --infra"
    fi

    # Reclaim the API port only if the holder is ours. Another project's
    # process on the same port is not ours to kill — on this machine :3000
    # belongs to a different repo's dev server, and blind port-freeing would
    # have taken it out.
    if port_listening "$API_PORT"; then
        if port_is_ours "$API_PORT" "$RUN_DIR/api.pid"; then
            existing="$(pid_on_port "$API_PORT")"
            dim "[backend] reclaiming :$API_PORT from our own pid $existing"
            kill "$existing" 2>/dev/null; sleep 2
            kill -0 "$existing" 2>/dev/null && kill -9 "$existing" 2>/dev/null
        else
            warn "[backend] :$API_PORT is held by something that is not ours:"
            dim "$(describe_port "$API_PORT")"
            dim "refusing to kill it — stop it yourself, or set LIFE_GRAPH_API_PORT"
            exit 1
        fi
    fi

    step "[backend] Running migrations..."
    if (cd "$ROOT" && "$PY" -m alembic upgrade head) >"$LOG_DIR/alembic.log" 2>&1; then
        rev="$(cd "$ROOT" && "$PY" -m alembic current 2>/dev/null | grep -oE '^[0-9a-f]+' | head -1)"
        ok "DB at revision: ${rev:-unknown}"
    else
        warn "migrations failed — see logs/alembic.log"
    fi

    step "[backend] Starting uvicorn on :$API_PORT..."
    (cd "$ROOT" && nohup "$PY" -m uvicorn life_graph.main:app \
        --host 0.0.0.0 --port "$API_PORT" --reload --reload-dir life_graph \
        >"$LOG_DIR/uvicorn.log" 2>&1 & echo $! >"$RUN_DIR/api.pid")
    dim "pid $(cat "$RUN_DIR/api.pid" 2>/dev/null)  log: logs/uvicorn.log"
    wait_for_http "http://localhost:$API_PORT/health" 25 "API" || dim "check logs/uvicorn.log"
fi

# ── Dashboard ─────────────────────────────────────────────────
if [ $DASHBOARD -eq 1 ] || [ $BOTH -eq 1 ] || [ $ALL -eq 1 ]; then
    if port_listening "$DASH_PORT"; then
        if port_is_ours "$DASH_PORT" "$RUN_DIR/dashboard.pid"; then
            existing="$(pid_on_port "$DASH_PORT")"
            dim "[dashboard] reclaiming :$DASH_PORT from our own pid $existing"
            kill "$existing" 2>/dev/null; sleep 1
        else
            warn "[dashboard] :$DASH_PORT is held by something that is not ours:"
            dim "$(describe_port "$DASH_PORT")"
            dim "refusing to kill it — set LIFE_GRAPH_DASH_PORT to use another port"
            exit 1
        fi
    fi

    if [ ! -d "$ROOT/dashboard/node_modules" ]; then
        step "[dashboard] Installing dependencies..."
        # npm ci when the lockfile is authoritative, install otherwise.
        if [ -f "$ROOT/dashboard/package-lock.json" ]; then
            (cd "$ROOT/dashboard" && npm ci) >"$LOG_DIR/npm.log" 2>&1 || \
                warn "npm ci failed — see logs/npm.log"
        else
            (cd "$ROOT/dashboard" && npm install) >"$LOG_DIR/npm.log" 2>&1 || \
                warn "npm install failed — see logs/npm.log"
        fi
    fi

    step "[dashboard] Starting Next.js on :$DASH_PORT..."
    (cd "$ROOT/dashboard" && nohup npm run dev \
        >"$LOG_DIR/dashboard.log" 2>&1 & echo $! >"$RUN_DIR/dashboard.pid")
    dim "pid $(cat "$RUN_DIR/dashboard.pid" 2>/dev/null)  log: logs/dashboard.log"
fi

printf '\n  %sLife Graph is running!%s\n\n' "$C_GREEN" "$C_RESET"
say  "  Backend API:  http://localhost:$API_PORT"
say  "  API Docs:     http://localhost:$API_PORT/docs"
say  "  Dashboard:    http://localhost:$DASH_PORT"
say  "  WebSocket:    ws://localhost:$API_PORT/ws"
printf '\n'
dim  "Stop with:    ./stop.sh"
dim  "Status:       ./status.sh"
dim  "Logs:         tail -f logs/uvicorn.log"
printf '\n'
