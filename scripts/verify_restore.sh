#!/bin/bash
# Life Graph Restore-Verification Drill ("The Lifeline", F0)
#
# Restores the most recent pg_dump into a scratch database on the same
# server, verifies row counts and embedding samples against the live
# database, records the outcome in the live job_runs table, then drops
# the scratch database. Untested backups don't count.
#
# Usage:
#   ./scripts/verify_restore.sh                        # verify latest dump
#   ./scripts/verify_restore.sh backups/life_graph_20260711_020000.dump
#
# Environment variables:
#   PGUSER         — PostgreSQL user            (default: life_graph)
#   PGDATABASE     — Live database name         (default: life_graph)
#   PGHOST         — Database host              (default: localhost)
#   BACKUP_DIR     — Backup directory           (default: ./backups)
#   VERIFY_DB      — Scratch database name      (default: life_graph_verify)
#   MIN_ROW_RATIO  — Required scratch/live row ratio for memories (default: 0.90)
#
# Exit codes: 0 = verified, 1 = drill failed (backup unusable or checks failed)

set -uo pipefail

DB_USER=${PGUSER:-life_graph}
DB_NAME=${PGDATABASE:-life_graph}
DB_HOST=${PGHOST:-localhost}
BACKUP_DIR=${BACKUP_DIR:-./backups}
VERIFY_DB=${VERIFY_DB:-life_graph_verify}
MIN_ROW_RATIO=${MIN_ROW_RATIO:-0.90}

STARTED_AT=$(date -u +"%Y-%m-%d %H:%M:%S+00")

log() { echo "[$(date)] $*"; }

psql_live() {
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -tA -c "$1"
}

psql_scratch() {
    psql -h "$DB_HOST" -U "$DB_USER" -d "$VERIFY_DB" -tA -c "$1"
}

record_job_run() {
    # record_job_run <status> <result_json> [error_text]
    local status=$1
    local result=$2
    local error=${3:-}
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -q -c \
        "INSERT INTO job_runs (id, tenant_id, job_name, status, started_at, completed_at, result, error, attempt, created_at)
         VALUES (gen_random_uuid(), 'system', 'restore_drill', '$status', '$STARTED_AT', now(),
                 '$result'::jsonb, $( [ -n "$error" ] && echo "'$error'" || echo "NULL" ), 1, now())" \
        || log "WARNING: could not record job run in job_runs"
}

cleanup_scratch() {
    psql -h "$DB_HOST" -U "$DB_USER" -d postgres -q -c \
        "DROP DATABASE IF EXISTS $VERIFY_DB WITH (FORCE)" 2>/dev/null || true
}

fail() {
    log "DRILL FAILED: $1"
    record_job_run "failed" "{}" "$1"
    cleanup_scratch
    exit 1
}

# -- Pick the dump ------------------------------------------------------
if [ $# -ge 1 ]; then
    DUMP_FILE=$1
else
    DUMP_FILE=$(ls -t "$BACKUP_DIR"/life_graph_*.dump 2>/dev/null | head -1 || true)
fi
[ -n "${DUMP_FILE:-}" ] && [ -f "$DUMP_FILE" ] || fail "no backup dump found in $BACKUP_DIR"

DUMP_AGE_HOURS=$(( ( $(date +%s) - $(date -r "$DUMP_FILE" +%s) ) / 3600 ))
log "Verifying dump: $DUMP_FILE (age: ${DUMP_AGE_HOURS}h)"
if [ "$DUMP_AGE_HOURS" -gt 48 ]; then
    log "WARNING: latest dump is older than 48h — nightly backups may be broken"
fi

# -- Create scratch database and restore -------------------------------
cleanup_scratch
psql -h "$DB_HOST" -U "$DB_USER" -d postgres -q -c "CREATE DATABASE $VERIFY_DB" \
    || fail "could not create scratch database $VERIFY_DB"

# AGE and pgvector emit ignorable ownership/extension warnings on restore;
# the row-count and embedding checks below are the real gate.
RESTORE_ERRORS=$(pg_restore -h "$DB_HOST" -U "$DB_USER" -d "$VERIFY_DB" \
    --no-owner --no-privileges "$DUMP_FILE" 2>&1 | grep -c "error:" || true)
log "pg_restore finished ($RESTORE_ERRORS errors reported, warnings tolerated)"

# -- Verification checks ------------------------------------------------
TABLES="memories sessions capture_events decisions predictions agent_tasks"
RESULT_JSON="{\"dump\": \"$(basename "$DUMP_FILE")\", \"dump_age_hours\": $DUMP_AGE_HOURS, \"restore_errors\": $RESTORE_ERRORS, \"tables\": {"
FIRST=1

for tbl in $TABLES; do
    live_exists=$(psql_live "SELECT to_regclass('public.$tbl') IS NOT NULL") || fail "cannot query live database"
    [ "$live_exists" = "t" ] || continue
    live_count=$(psql_live "SELECT count(*) FROM $tbl")
    scratch_count=$(psql_scratch "SELECT count(*) FROM $tbl" 2>/dev/null) \
        || fail "table $tbl missing from restored backup"
    [ $FIRST -eq 1 ] || RESULT_JSON+=", "
    FIRST=0
    RESULT_JSON+="\"$tbl\": {\"live\": $live_count, \"restored\": $scratch_count}"
    log "  $tbl: live=$live_count restored=$scratch_count"

    if [ "$tbl" = "memories" ] && [ "$live_count" -gt 0 ]; then
        ratio_ok=$(psql_live "SELECT $scratch_count >= ceil($live_count * $MIN_ROW_RATIO)")
        [ "$ratio_ok" = "t" ] || fail "memories row count too low: restored=$scratch_count live=$live_count (min ratio $MIN_ROW_RATIO)"
    fi
done
RESULT_JSON+="}"

# -- Embedding sample check ---------------------------------------------
live_embedded=$(psql_live "SELECT count(*) FROM memories WHERE embedding IS NOT NULL")
if [ "$live_embedded" -gt 0 ]; then
    restored_embedded=$(psql_scratch "SELECT count(*) FROM memories WHERE embedding IS NOT NULL")
    [ "$restored_embedded" -gt 0 ] || fail "restored backup has zero embeddings but live has $live_embedded"
    sample_dim=$(psql_scratch "SELECT vector_dims(embedding) FROM memories WHERE embedding IS NOT NULL LIMIT 1")
    RESULT_JSON+=", \"embeddings\": {\"live\": $live_embedded, \"restored\": $restored_embedded, \"sample_dims\": $sample_dim}"
    log "  embeddings: live=$live_embedded restored=$restored_embedded dims=$sample_dim"
fi
RESULT_JSON+="}"

# -- Success ------------------------------------------------------------
cleanup_scratch
record_job_run "success" "$RESULT_JSON"
log "DRILL PASSED — backup is restorable"
exit 0
