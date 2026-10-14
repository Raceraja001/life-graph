#!/usr/bin/env bash
# Restart the API without killing dev-agent work.
#
# A restart used to cut a running dev task off mid-run (and `--reload` did it
# on every saved file). This waits until no dev task is running, then stops
# only this repo's API (by its pid file) and starts it again the way start.sh
# does. A task that still gets interrupted is re-queued once on startup
# (services/dev_tasks.py fail_interrupted), so a forced restart costs a re-run,
# not the task.
#
#   scripts/restart-api.sh            wait up to 30 min for an idle moment
#   WAIT_MINUTES=5 scripts/restart-api.sh
#   FORCE=1 scripts/restart-api.sh    restart now (running tasks are re-queued)
#   DEV_RELOAD=1 scripts/restart-api.sh   start with --reload (kills tasks on save)
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

PIDFILE="$RUN_DIR/api.pid"
WAIT_MINUTES="${WAIT_MINUTES:-30}"

running_tasks() {
    (cd "$ROOT" && "$PY" - <<'EOF' 2>/dev/null) || echo "?"
import asyncio
from sqlalchemy import func, select
from life_graph.models.db import AgentTask
from life_graph.services.dev_tasks import _kind_filter
from life_graph.storage.database import async_session
async def main():
    async with async_session() as s:
        n = (await s.execute(select(func.count()).select_from(AgentTask)
             .where(_kind_filter(), AgentTask.status == "running"))).scalar()
        print(n)
asyncio.run(main())
EOF
}

if [ "${FORCE:-0}" != "1" ]; then
    step "[api] waiting for running dev tasks to finish (up to ${WAIT_MINUTES} min)..."
    deadline=$(( $(date +%s) + WAIT_MINUTES * 60 ))
    while :; do
        n="$(running_tasks)"
        [ "$n" = "0" ] && break
        if [ "$(date +%s)" -ge "$deadline" ]; then
            warn "still $n running after ${WAIT_MINUTES} min — not restarting (FORCE=1 to override)"
            exit 1
        fi
        dim "$n running; checking again in 15s"
        sleep 15
    done
    ok "no dev task running"
fi

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    old="$(cat "$PIDFILE")"
    kids="$(pgrep -P "$old" || true)"
    step "[api] stopping pid $old"
    kill "$old"
    for _ in $(seq 1 20); do kill -0 "$old" 2>/dev/null || break; sleep 1; done
    for k in $kids; do kill -0 "$k" 2>/dev/null && kill "$k" || true; done
else
    dim "no running API recorded in $PIDFILE"
fi

reload_args=()
if [ "${DEV_RELOAD:-0}" = "1" ]; then
    # DrvFs (/mnt/*) delivers no inotify events; polling is the only watch mode.
    export WATCHFILES_FORCE_POLLING=true
    reload_args=(--reload --reload-dir life_graph)
fi
mkdir -p "$RUN_DIR" "$LOG_DIR"
step "[api] starting on :$API_PORT${reload_args:+ (reload on)}"
# exec: the subshell BECOMES uvicorn, so $! is uvicorn's own pid (not a
# wrapper that outlives this script holding its stdout open).
(cd "$ROOT" && exec nohup "$PY" -m uvicorn life_graph.main:app --host 0.0.0.0 --port "$API_PORT" \
    "${reload_args[@]}" >"$LOG_DIR/uvicorn.log" 2>&1 </dev/null) &
echo $! >"$PIDFILE"
wait_for_http "http://localhost:$API_PORT/health" 40 "API" || { warn "see logs/uvicorn.log"; exit 1; }
ok "pid $(cat "$PIDFILE")"
