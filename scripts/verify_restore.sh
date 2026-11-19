#!/bin/bash
# Life Graph Restore-Verification Drill ("The Lifeline", F0)
#
# Restores the most recent pg_dump into a scratch database on the same
# server (with the same procedure restore.sh uses), verifies it, records the
# outcome in the live job_runs table, then drops the scratch database.
# Untested backups don't count.
#
# The drill FAILS (job_runs status=failed + an owner notification) when:
#   - pg_restore reports any error;
#   - the Apache AGE graph differs from the dump's manifest
#     (life_graph_<ts>.graph, written by backup.sh from the dump's own
#     snapshot): ag_graph/ag_label rows, rows per label, vertex or edge totals;
#     without a manifest (older dumps) the live graph is the baseline;
#   - label tables and catalog disagree, or a label's id sequence is behind;
#   - a cypher MATCH on any label fails or returns a different count;
#   - a checked table is missing, memories < MIN_ROW_RATIO of live, or the
#     restored copy has no embeddings while live has them.
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
#   RESTORE_JOBS   — pg_restore parallelism for data/indexes (default: 1)
#
# Exit codes: 0 = verified, 1 = drill failed (backup unusable or checks failed)

set -uo pipefail
umask 077

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=lib_backup.sh
source "$SCRIPT_DIR/lib_backup.sh"

DB_USER=${PGUSER:-life_graph}
DB_NAME=${PGDATABASE:-life_graph}
DB_HOST=${PGHOST:-localhost}
BACKUP_DIR=${BACKUP_DIR:-./backups}
VERIFY_DB=${VERIFY_DB:-life_graph_verify}
MIN_ROW_RATIO=${MIN_ROW_RATIO:-0.90}

STARTED_AT=$(date -u +"%Y-%m-%d %H:%M:%S+00")
WORK=$(mktemp -d)

log() { echo "[$(date)] $*"; }

psql_live() {
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -X -tA -c "$1"
}

psql_scratch() {
    psql -h "$DB_HOST" -U "$DB_USER" -d "$VERIFY_DB" -X -tA -c "$1"
}

cleanup_scratch() {
    psql -h "$DB_HOST" -U "$DB_USER" -d postgres -X -q -c \
        "DROP DATABASE IF EXISTS $VERIFY_DB WITH (FORCE)" 2>/dev/null || true
}

RESULT_JSON=""

fail() {
    log "DRILL FAILED: $1"
    local result="{}"
    [ -n "$RESULT_JSON" ] && result="$RESULT_JSON}"
    record_job_run "restore_drill" "failed" "$result" "$1"
    notify_owner "restore_drill_failed" "important" "Restore drill FAILED" \
        "The weekly restore drill could not prove the latest backup is restorable: $1"
    cleanup_scratch
    rm -rf "$WORK"
    exit 1
}

# -- Pick the dump ------------------------------------------------------
if [ $# -ge 1 ]; then
    DUMP_FILE=$1
else
    # Newest non-empty dump: a failed pg_dump used to leave a 0-byte file that
    # sorted first and made the drill test an empty file.
    DUMP_FILE=$(find "$BACKUP_DIR" -maxdepth 1 -name 'life_graph_*.dump' -size +0 \
        -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2- || true)
fi
[ -n "${DUMP_FILE:-}" ] && [ -f "$DUMP_FILE" ] || fail "no backup dump found in $BACKUP_DIR"
[ -s "$DUMP_FILE" ] || fail "backup dump is empty: $DUMP_FILE"

DUMP_AGE_HOURS=$(( ( $(date +%s) - $(date -r "$DUMP_FILE" +%s) ) / 3600 ))
log "Verifying dump: $DUMP_FILE (age: ${DUMP_AGE_HOURS}h)"
if [ "$DUMP_AGE_HOURS" -gt 48 ]; then
    log "WARNING: latest dump is older than 48h — nightly backups may be broken"
fi

# -- Create scratch database and restore -------------------------------
cleanup_scratch
psql -h "$DB_HOST" -U "$DB_USER" -d postgres -X -q -c "CREATE DATABASE $VERIFY_DB" \
    || fail "could not create scratch database $VERIFY_DB"

# Errors are no longer tolerated: the old "warnings tolerated" restore hid a
# graph whose AGE catalog never came back.
if restore_dump "$VERIFY_DB" "$DUMP_FILE" "$WORK/restore.log"; then
    RESTORE_ERRORS=0
    log "pg_restore finished without errors"
else
    RESTORE_ERRORS=$(grep -c 'error:' "$WORK/restore.log" || true)
    grep 'error:' "$WORK/restore.log" | head -5
    fail "pg_restore reported errors ($RESTORE_ERRORS): $(grep -m1 'error:' "$WORK/restore.log" | head -c 300)"
fi

RESULT_JSON="{\"dump\": \"$(basename "$DUMP_FILE")\", \"dump_age_hours\": $DUMP_AGE_HOURS, \"restore_errors\": $RESTORE_ERRORS"

# -- Apache AGE graph -------------------------------------------------------
MANIFEST="${DUMP_FILE%.dump}.graph"
if [ -f "$MANIFEST" ]; then
    BASELINE=manifest
    cp "$MANIFEST" "$WORK/expected"
else
    # Dumps taken before manifests existed: compare with the live graph.
    BASELINE=live
    log "WARNING: no manifest $(basename "$MANIFEST") — comparing the graph with live instead"
    graph_counts "$DB_NAME" > "$WORK/expected" || fail "cannot read the live graph inventory"
fi
if check_graph "$VERIFY_DB" "$WORK/expected" "$BASELINE"; then
    RESULT_JSON+=", \"graph\": $GRAPH_JSON"
    log "  graph: $GRAPH_JSON"
else
    RESULT_JSON+=", \"graph\": $GRAPH_JSON"
    fail "$GRAPH_ERROR"
fi

# -- Verification checks ------------------------------------------------
TABLES="memories sessions capture_events decisions predictions agent_tasks"
RESULT_JSON+=", \"tables\": {"
FIRST=1

for tbl in $TABLES; do
    # Resolve the schema instead of assuming public: capture_events, decisions
    # and predictions live in the life_graph schema, so a public-only lookup
    # skipped them silently and the drill verified half of what it reported.
    schema=$(psql_live "SELECT table_schema FROM information_schema.tables
                        WHERE table_name = '$tbl' AND table_schema IN ('public', 'life_graph')
                        ORDER BY table_schema = 'public' DESC LIMIT 1") || fail "cannot query live database"
    [ -n "$schema" ] || continue
    qualified="$schema.$tbl"
    live_count=$(psql_live "SELECT count(*) FROM $qualified")
    scratch_count=$(psql_scratch "SELECT count(*) FROM $qualified" 2>/dev/null) \
        || { RESULT_JSON+="}"; fail "table $qualified missing from restored backup"; }
    [ $FIRST -eq 1 ] || RESULT_JSON+=", "
    FIRST=0
    RESULT_JSON+="\"$qualified\": {\"live\": $live_count, \"restored\": $scratch_count}"
    log "  $qualified: live=$live_count restored=$scratch_count"

    if [ "$tbl" = "memories" ] && [ "$live_count" -gt 0 ]; then
        ratio_ok=$(psql_live "SELECT $scratch_count >= ceil($live_count * $MIN_ROW_RATIO)")
        [ "$ratio_ok" = "t" ] || { RESULT_JSON+="}"; fail "memories row count too low: restored=$scratch_count live=$live_count (min ratio $MIN_ROW_RATIO)"; }
    fi
done
RESULT_JSON+="}"

# -- Embedding sample check ---------------------------------------------
live_embedded=$(psql_live "SELECT count(*) FROM memories WHERE embedding IS NOT NULL")
if [ "${live_embedded:-0}" -gt 0 ]; then
    restored_embedded=$(psql_scratch "SELECT count(*) FROM memories WHERE embedding IS NOT NULL")
    [ "${restored_embedded:-0}" -gt 0 ] || fail "restored backup has zero embeddings but live has $live_embedded"
    sample_dim=$(psql_scratch "SELECT vector_dims(embedding) FROM memories WHERE embedding IS NOT NULL LIMIT 1")
    RESULT_JSON+=", \"embeddings\": {\"live\": $live_embedded, \"restored\": $restored_embedded, \"sample_dims\": $sample_dim}"
    log "  embeddings: live=$live_embedded restored=$restored_embedded dims=$sample_dim"
fi
RESULT_JSON+="}"

# -- Success ------------------------------------------------------------
cleanup_scratch
rm -rf "$WORK"
record_job_run "restore_drill" "success" "$RESULT_JSON"
log "DRILL PASSED — backup is restorable"
exit 0
