#!/bin/bash
# Life Graph Restore Script
#
# Usage:
#   ./scripts/restore.sh backups/life_graph_20260702_120000.dump
#   ./scripts/restore.sh --yes backups/life_graph_20260702_120000.dump   # no prompt
#
# Restores into a NEW staging database, proves it (pg_restore without errors,
# Apache AGE graph identical to the dump's manifest, cypher answers), and only
# then swaps it in: the current database is renamed to
# <name>_before_restore_<timestamp> (kept, drop it yourself once happy) and the
# staging database takes its name. A failed restore leaves the current
# database untouched.
#
# The old `pg_restore --clean` into the live database could not work with AGE:
# AGE refuses to drop label tables, so the graph rows were appended a second
# time and the catalog was left inconsistent (see scripts/lib_backup.sh).
#
# Environment variables:
#   PGUSER     — PostgreSQL user    (default: life_graph)
#   PGDATABASE — Database name      (default: life_graph)
#   PGHOST     — Database host      (default: localhost)
#   RESTORE_JOBS — pg_restore parallelism for data/indexes (default: 1)
#
# Stop the API and workers first: the swap terminates every connection to the
# database being replaced.

set -euo pipefail
umask 077

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=lib_backup.sh
source "$SCRIPT_DIR/lib_backup.sh"

# ── Config ────────────────────────────────────────────────────
DB_USER=${PGUSER:-life_graph}
DB_NAME=${PGDATABASE:-life_graph}
DB_HOST=${PGHOST:-localhost}

ASSUME_YES=false
if [ "${1:-}" = "--yes" ]; then ASSUME_YES=true; shift; fi

# ── Validate arguments ────────────────────────────────────────
if [ $# -eq 0 ]; then
    echo "Usage: $0 [--yes] <backup_file.dump>"
    echo ""
    echo "Available backups:"
    ls -la backups/life_graph_*.dump 2>/dev/null || echo "  No backups found"
    exit 1
fi

BACKUP_FILE=$1

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

STAMP=$(date -u +%Y%m%d%H%M%S)
STAGE_DB="${DB_NAME}_restoring_${STAMP}"
OLD_DB="${DB_NAME}_before_restore_${STAMP}"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

maint() { psql -h "$DB_HOST" -U "$DB_USER" -d postgres -X -q -v ON_ERROR_STOP=1 -c "$1"; }

# ── Confirm with user ────────────────────────────────────────
echo "WARNING: This will replace the database '$DB_NAME' on host '$DB_HOST'"
echo "Backup file: $BACKUP_FILE"
echo "The current database is kept as '$OLD_DB'."
if ! $ASSUME_YES; then
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Restore cancelled."
        exit 0
    fi
fi

# ── Restore into a staging database ───────────────────────────
echo "[$(date)] Restoring $BACKUP_FILE into staging database $STAGE_DB..."
maint "CREATE DATABASE \"$STAGE_DB\""
if ! restore_dump "$STAGE_DB" "$BACKUP_FILE" "$WORK/restore.log"; then
    grep 'error:' "$WORK/restore.log" | head -10 || tail -20 "$WORK/restore.log"
    maint "DROP DATABASE IF EXISTS \"$STAGE_DB\" WITH (FORCE)" || true
    echo "[$(date)] ERROR: pg_restore failed — '$DB_NAME' was not touched"
    exit 1
fi

# ── Prove the graph before swapping ───────────────────────────
MANIFEST="${BACKUP_FILE%.dump}.graph"
if [ -f "$MANIFEST" ]; then
    cp "$MANIFEST" "$WORK/expected"; BASELINE=manifest
else
    # Older dump without a manifest: check the copy against itself (catalog,
    # sequences, cypher answers what the tables hold).
    echo "[$(date)] WARNING: no manifest next to the dump; checking graph consistency only"
    graph_counts "$STAGE_DB" > "$WORK/expected"; BASELINE=self
fi
if ! check_graph "$STAGE_DB" "$WORK/expected" "$BASELINE"; then
    echo "[$(date)] ERROR: restored graph failed verification: $GRAPH_ERROR"
    maint "DROP DATABASE IF EXISTS \"$STAGE_DB\" WITH (FORCE)" || true
    echo "[$(date)] '$DB_NAME' was not touched"
    exit 1
fi
echo "[$(date)] Restored copy verified: $GRAPH_JSON"

# ── Swap ──────────────────────────────────────────────────────
DB_EXISTS=$(psql -h "$DB_HOST" -U "$DB_USER" -d postgres -X -qAt -v ON_ERROR_STOP=1 \
    -c "SELECT count(*) FROM pg_database WHERE datname = '$DB_NAME'")
if [ "$DB_EXISTS" = "1" ]; then
    maint "ALTER DATABASE \"$DB_NAME\" WITH ALLOW_CONNECTIONS false"
    maint "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid()" > /dev/null
    maint "ALTER DATABASE \"$DB_NAME\" RENAME TO \"$OLD_DB\""
    maint "ALTER DATABASE \"$OLD_DB\" WITH ALLOW_CONNECTIONS true"
fi
maint "ALTER DATABASE \"$STAGE_DB\" RENAME TO \"$DB_NAME\""
echo "[$(date)] Restore complete: '$DB_NAME' now holds $BACKUP_FILE"
[ "$DB_EXISTS" = "1" ] && echo "[$(date)] Previous database kept as '$OLD_DB' (DROP DATABASE \"$OLD_DB\"; when no longer needed)"
exit 0
