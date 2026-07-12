#!/bin/bash
# Life Graph Backup Scheduler ("The Lifeline", F0)
#
# Long-running loop for the `backup` sidecar container (see
# docker-compose.production.yml). Runs:
#   - Nightly backup           at 02:00 UTC  (scripts/backup.sh)
#   - Weekly restore drill     Sunday 06:00 UTC (scripts/verify_restore.sh)
#
# Environment variables:
#   BACKUP_HOUR        — UTC hour for nightly backup     (default: 02)
#   DRILL_WEEKDAY      — Day for restore drill, Mon=1..Sun=7 (default: 7)
#   DRILL_HOUR         — UTC hour for restore drill      (default: 06)
#   RUN_AT_STARTUP     — Set to "1" to run a backup immediately on start
# Plus everything backup.sh / verify_restore.sh accept (PGHOST, BACKUP_DIR, ...).

set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BACKUP_HOUR=${BACKUP_HOUR:-02}
DRILL_WEEKDAY=${DRILL_WEEKDAY:-7}
DRILL_HOUR=${DRILL_HOUR:-06}

log() { echo "[$(date -u)] [backup_cron] $*"; }

run_backup() {
    log "Starting nightly backup"
    if bash "$SCRIPT_DIR/backup.sh"; then
        log "Nightly backup OK"
    else
        log "ERROR: nightly backup FAILED"
    fi
}

run_drill() {
    log "Starting weekly restore drill"
    if bash "$SCRIPT_DIR/verify_restore.sh"; then
        log "Restore drill PASSED"
    else
        log "ERROR: restore drill FAILED — backups may not be restorable"
    fi
}

log "Scheduler started: backup daily ${BACKUP_HOUR}:00 UTC, drill weekday=$DRILL_WEEKDAY ${DRILL_HOUR}:00 UTC"

if [ "${RUN_AT_STARTUP:-0}" = "1" ]; then
    run_backup
fi

LAST_BACKUP_DAY=""
LAST_DRILL_DAY=""

while true; do
    NOW_DAY=$(date -u +%Y%m%d)
    NOW_HOUR=$(date -u +%H)
    NOW_DOW=$(date -u +%u)   # Mon=1 .. Sun=7

    if [ "$NOW_HOUR" = "$BACKUP_HOUR" ] && [ "$LAST_BACKUP_DAY" != "$NOW_DAY" ]; then
        LAST_BACKUP_DAY=$NOW_DAY
        run_backup
    fi

    if [ "$NOW_DOW" = "$DRILL_WEEKDAY" ] && [ "$NOW_HOUR" = "$DRILL_HOUR" ] \
        && [ "$LAST_DRILL_DAY" != "$NOW_DAY" ]; then
        LAST_DRILL_DAY=$NOW_DAY
        run_drill
    fi

    sleep 60
done
