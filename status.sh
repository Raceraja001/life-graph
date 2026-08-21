#!/usr/bin/env bash
#
# Check status of all Life Graph services (Linux). Port of status.ps1.
#
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/scripts/_lib.sh"

load_service_ports
printf '\n  %sLife Graph - Status%s\n\n' "$C_CYAN" "$C_RESET"

check() {  # label, port, health-url (optional)
    local label="$1" port="$2" health="${3:-}" status colour via
    if port_listening "$port"; then
        via="(local)"; port_is_docker "$port" && via="(docker)"
        status="RUNNING $via"; colour="$C_GREEN"
        if [ -n "$health" ]; then
            if curl -fsS -m 3 "$health" >/dev/null 2>&1; then
                status="HEALTHY $via"
            else
                status="UNHEALTHY $via"; colour="$C_YELLOW"
            fi
        fi
    else
        status="STOPPED"; colour="$C_RED"
    fi
    printf '  %-14s %-6s %s%s%s\n' "$label" ":$port" "$colour" "$status" "$C_RESET"
}

check "Backend API" "$API_PORT" "http://localhost:$API_PORT/health"
check "Dashboard"   "$DASH_PORT" "http://localhost:$DASH_PORT"
# A port being up does not mean it is OURS — another project may hold it.
for spec in "Backend API:$API_PORT:api.pid" "Dashboard:$DASH_PORT:dashboard.pid"; do
    IFS=: read -r lbl prt pf <<<"$spec"
    if port_listening "$prt" && ! port_is_ours "$prt" "$RUN_DIR/$pf"; then
        warn "$lbl on :$prt is NOT this repo — $(describe_port "$prt")"
    fi
done
check "PostgreSQL"  "$DB_PORT"
check "Redis"       "$REDIS_PORT"
check "MCP Server"  8001
check "MinIO"       9001

printf '\n'

# DB migration revision. Needs the DB up; report plainly rather than dumping
# a stack trace when it is not.
if rev="$(cd "$ROOT" && "$PY" -m alembic current 2>/dev/null | grep -oE '^[0-9a-f]+' | head -1)" && [ -n "$rev" ]; then
    ok "DB migration: $rev"
else
    dim "DB migration: unavailable (is Postgres up?)"
fi

# Endpoint count straight from the running app's schema.
if count="$(curl -fsS -m 3 "http://localhost:$API_PORT/openapi.json" 2>/dev/null \
        | "$PY" -c 'import json,sys; print(len(json.load(sys.stdin)["paths"]))' 2>/dev/null)"; then
    ok "API endpoints: $count"
fi

# Anything start.sh launched that has since died leaves a stale pidfile —
# worth surfacing, since the port check alone would just say STOPPED.
for f in "$RUN_DIR"/*.pid; do
    [ -e "$f" ] || continue
    pid="$(cat "$f" 2>/dev/null)"
    if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
        warn "stale pidfile: $(basename "$f") (pid $pid is gone) — check logs/"
    fi
done

printf '\n'
