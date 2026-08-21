#!/usr/bin/env bash
#
# Stop the Life Graph application (Linux). Port of stop.ps1.
#
#   ./stop.sh              # API + dashboard (leaves Postgres/Redis up)
#   ./stop.sh --all        # everything, including docker
#   ./stop.sh --backend    # only the backend API
#   ./stop.sh --dashboard  # only the dashboard
#   ./stop.sh --infra      # only docker (Postgres + Redis)
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
        -h|--help)   sed -n '3,10p' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) warn "unknown option: $1"; exit 2 ;;
    esac
    shift
done
BOTH=0
[ $BACKEND -eq 0 ] && [ $DASHBOARD -eq 0 ] && [ $INFRA -eq 0 ] && [ $ALL -eq 0 ] && BOTH=1

printf '\n  %sLife Graph - Stopping...%s\n\n' "$C_CYAN" "$C_RESET"

# Stop by pidfile first (exactly what start.sh launched), then fall back to
# whoever holds the port. TERM before KILL so uvicorn's reloader gets to reap
# its worker instead of orphaning it.
stop_service() {  # label, pidfile, port
    local label="$1" pidfile="$2" port="$3" pid found=0
    step "[$label] Stopping..."

    if [ -f "$pidfile" ]; then
        pid="$(cat "$pidfile" 2>/dev/null)"
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            dim "killing pid $pid (from $(basename "$pidfile"))"
            # Kill the process group: uvicorn --reload and npm run dev both
            # spawn children that would otherwise survive and hold the port.
            kill -TERM -"$(ps -o pgid= -p "$pid" | tr -d ' ')" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
            sleep 2
            kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null
            found=1
        fi
        rm -f "$pidfile"
    fi

    pid="$(pid_on_port "$port")"
    if [ -n "$pid" ]; then
        dim "killing $(ps -p "$pid" -o comm=) (pid $pid) still on :$port"
        kill -TERM "$pid" 2>/dev/null; sleep 1
        kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null
        found=1
    fi

    [ $found -eq 1 ] && ok "Stopped" || dim "Not running"
}

if [ $DASHBOARD -eq 1 ] || [ $BOTH -eq 1 ] || [ $ALL -eq 1 ]; then
    stop_service dashboard "$RUN_DIR/dashboard.pid" "$DASH_PORT"
fi

if [ $BACKEND -eq 1 ] || [ $BOTH -eq 1 ] || [ $ALL -eq 1 ]; then
    stop_service backend "$RUN_DIR/api.pid" "$API_PORT"
fi

if [ $INFRA -eq 1 ] || [ $ALL -eq 1 ]; then
    step "[infra] Stopping docker services..."
    if docker_ready; then
        if (cd "$ROOT" && timeout 60 docker compose down) >"$LOG_DIR/infra.log" 2>&1; then
            ok "Stopped"
        else
            warn "compose down timed out — force killing containers"
            docker kill life_graph_db life_graph_redis >/dev/null 2>&1
            ok "Force killed"
        fi
    fi
fi

printf '\n  %sLife Graph stopped.%s\n\n' "$C_GREEN" "$C_RESET"
dim "Start with: ./start.sh"
printf '\n'
