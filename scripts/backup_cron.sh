#!/bin/bash
# Life Graph Backup Scheduler ("The Lifeline", F0)
#
# Long-running loop for the `backup` sidecar container (see
# docker-compose.production.yml). Runs:
#   - Nightly backup           at 02:00 UTC  (scripts/backup.sh)
#   - Weekly restore drill     Sunday 06:00 UTC (scripts/verify_restore.sh)
#   - Retries                  a failed backup every BACKUP_RETRY_MINUTES,
#                              a skipped off-site copy every OFFSITE_RETRY_MINUTES
#
# Environment variables:
#   BACKUP_HOUR        — UTC hour for nightly backup     (default: 02)
#   DRILL_WEEKDAY      — Day for restore drill, Mon=1..Sun=7 (default: 7)
#   DRILL_HOUR         — UTC hour for restore drill      (default: 06)
#   RUN_AT_STARTUP     — Set to "1" to run a backup immediately on start
#   DB_WAIT_SECONDS    — Max wait for the database before a run (default: 600)
#   BACKUP_RETRY_MINUTES  — Retry interval after a failed backup (default: 15)
#   OFFSITE_RETRY_MINUTES — Retry interval for a skipped off-site copy (default: 60)
# Plus everything backup.sh / verify_restore.sh accept (PGHOST, BACKUP_DIR, ...).

set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BACKUP_HOUR=${BACKUP_HOUR:-02}
DRILL_WEEKDAY=${DRILL_WEEKDAY:-7}
DRILL_HOUR=${DRILL_HOUR:-06}
DB_WAIT_SECONDS=${DB_WAIT_SECONDS:-600}
BACKUP_RETRY_SECONDS=$(( ${BACKUP_RETRY_MINUTES:-15} * 60 ))
OFFSITE_RETRY_SECONDS=$(( ${OFFSITE_RETRY_MINUTES:-60} * 60 ))
PENDING_MARKER="${BACKUP_DIR:-./backups}/.offsite_pending"

log() { echo "[$(date -u)] [backup_cron] $*"; }

# Docker's restart policy brings this container back at boot independently of
# compose's depends_on, so it can start before Postgres is up — or before the
# compose network resolves "postgres" at all. Both happened on real reboots and
# the startup backup was simply lost. Wait for the server instead.
wait_for_db() {
    local waited=0
    until pg_isready -h "${PGHOST:-localhost}" -U "${PGUSER:-life_graph}" \
        -d "${PGDATABASE:-life_graph}" -q 2>/dev/null; do
        if [ "$waited" -ge "$DB_WAIT_SECONDS" ]; then
            log "database not ready after ${DB_WAIT_SECONDS}s"
            return 1
        fi
        [ "$waited" -eq 0 ] && log "Waiting for database at ${PGHOST:-localhost}..."
        sleep 10
        waited=$(( waited + 10 ))
    done
    [ "$waited" -gt 0 ] && log "Database ready after ${waited}s"
    return 0
}

NEXT_BACKUP_RETRY=0   # epoch seconds; 0 = no retry pending

run_backup() {
    log "Starting nightly backup"
    if wait_for_db && bash "$SCRIPT_DIR/backup.sh"; then
        log "Nightly backup OK"
        NEXT_BACKUP_RETRY=0
    else
        NEXT_BACKUP_RETRY=$(( $(date +%s) + BACKUP_RETRY_SECONDS ))
        log "ERROR: nightly backup FAILED — retrying at $(date -u -d "@$NEXT_BACKUP_RETRY" +%H:%M) UTC"
    fi
}

NEXT_OFFSITE_RETRY=$(( $(date +%s) + OFFSITE_RETRY_SECONDS ))

run_offsite_retry() {
    log "Retrying off-site copy (pending since $(cat "$PENDING_MARKER" 2>/dev/null))"
    if wait_for_db; then
        bash "$SCRIPT_DIR/backup.sh" --offsite-only
    fi
    NEXT_OFFSITE_RETRY=$(( $(date +%s) + OFFSITE_RETRY_SECONDS ))
}

run_drill() {
    log "Starting weekly restore drill"
    if wait_for_db && bash "$SCRIPT_DIR/verify_restore.sh"; then
        log "Restore drill PASSED"
    else
        log "ERROR: restore drill FAILED — backups may not be restorable"
    fi
}

log "Scheduler started: backup daily ${BACKUP_HOUR}:00 UTC, drill weekday=$DRILL_WEEKDAY ${DRILL_HOUR}:00 UTC"

LAST_BACKUP_DAY=""
LAST_DRILL_DAY=""

if [ "${RUN_AT_STARTUP:-0}" = "1" ]; then
    run_backup
    # A startup backup inside the scheduled hour *is* that day's backup;
    # without this the loop ran a second full backup a minute later.
    if [ "$NEXT_BACKUP_RETRY" -eq 0 ] && [ "$(date -u +%H)" = "$BACKUP_HOUR" ]; then
        LAST_BACKUP_DAY=$(date -u +%Y%m%d)
    fi
fi

while true; do
    NOW=$(date +%s)
    NOW_DAY=$(date -u +%Y%m%d)
    NOW_HOUR=$(date -u +%H)
    NOW_DOW=$(date -u +%u)   # Mon=1 .. Sun=7

    if [ "$NOW_HOUR" = "$BACKUP_HOUR" ] && [ "$LAST_BACKUP_DAY" != "$NOW_DAY" ]; then
        LAST_BACKUP_DAY=$NOW_DAY
        run_backup
    elif [ "$NEXT_BACKUP_RETRY" -gt 0 ] && [ "$NOW" -ge "$NEXT_BACKUP_RETRY" ]; then
        run_backup
    fi

    if [ -f "$PENDING_MARKER" ] && [ "$NOW" -ge "$NEXT_OFFSITE_RETRY" ]; then
        run_offsite_retry
    fi

    if [ "$NOW_DOW" = "$DRILL_WEEKDAY" ] && [ "$NOW_HOUR" = "$DRILL_HOUR" ] \
        && [ "$LAST_DRILL_DAY" != "$NOW_DAY" ]; then
        LAST_DRILL_DAY=$NOW_DAY
        run_drill
    fi

    sleep 60
done
