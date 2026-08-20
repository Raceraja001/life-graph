#!/bin/bash
# Life Graph Backup Script
# Performs daily pg_dump + optional restic encrypted off-site backup
#
# Usage:
#   ./scripts/backup.sh                     # use defaults
#   BACKUP_DIR=/mnt/backups ./scripts/backup.sh  # custom backup dir
#
# Environment variables:
#   PGUSER          — PostgreSQL user         (default: life_graph)
#   PGDATABASE      — Database name           (default: life_graph)
#   PGHOST          — Database host           (default: localhost)
#   BACKUP_DIR      — Backup directory        (default: ./backups)
#   RETENTION_DAYS  — Days to keep backups    (default: 30)
#   RESTIC_REPOSITORY — If set, runs restic backup after pg_dump

set -euo pipefail

# ── Config ────────────────────────────────────────────────────
DB_USER=${PGUSER:-life_graph}
DB_NAME=${PGDATABASE:-life_graph}
DB_HOST=${PGHOST:-localhost}
BACKUP_DIR=${BACKUP_DIR:-./backups}
RETENTION_DAYS=${RETENTION_DAYS:-30}

# ── Setup ─────────────────────────────────────────────────────
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
STARTED_AT=$(date -u +"%Y-%m-%d %H:%M:%S+00")

record_job_run() {
    # record_job_run <status> <result_json> [error_text]
    local status=$1 result=$2 error=${3:-}
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -q -c \
        "INSERT INTO job_runs (id, tenant_id, job_name, status, started_at, completed_at, result, error, attempt, created_at)
         VALUES (gen_random_uuid(), 'system', 'backup', '$status', '$STARTED_AT', now(),
                 '$result'::jsonb, $( [ -n "$error" ] && echo "'$error'" || echo "NULL" ), 1, now())" \
        2>/dev/null || echo "[$(date)] WARNING: could not record job run"
}

on_error() {
    record_job_run "failed" "{}" "backup script failed at line $1"
}
trap 'on_error $LINENO' ERR

# ── pg_dump ───────────────────────────────────────────────────
echo "[$(date)] Starting backup..."
pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" \
    --format=custom \
    --compress=9 \
    --file="$BACKUP_DIR/life_graph_${TIMESTAMP}.dump"

DUMP_SIZE=$(stat -c%s "$BACKUP_DIR/life_graph_${TIMESTAMP}.dump" 2>/dev/null || echo 0)
echo "[$(date)] Backup created: life_graph_${TIMESTAMP}.dump (${DUMP_SIZE} bytes)"

# ── Clean old backups ─────────────────────────────────────────
find "$BACKUP_DIR" -name "life_graph_*.dump" -mtime +$RETENTION_DAYS -delete
echo "[$(date)] Cleaned backups older than $RETENTION_DAYS days"

# ── Optional: restic encrypted off-site backup ────────────────
RESTIC_RAN=false
if command -v restic &> /dev/null && [ -n "${RESTIC_REPOSITORY:-}" ]; then
    echo "[$(date)] Running restic backup..."
    # Include MinIO object data if its directory is mounted/available
    RESTIC_PATHS=("$BACKUP_DIR")
    if [ -n "${MINIO_DATA_DIR:-}" ] && [ -d "$MINIO_DATA_DIR" ]; then
        RESTIC_PATHS+=("$MINIO_DATA_DIR")
    fi
    restic backup "${RESTIC_PATHS[@]}" --tag life_graph
    restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune
    RESTIC_RAN=true
    echo "[$(date)] Restic backup complete"
fi

record_job_run "success" \
    "{\"dump\": \"life_graph_${TIMESTAMP}.dump\", \"size_bytes\": $DUMP_SIZE, \"offsite\": $RESTIC_RAN}"

echo "[$(date)] Backup complete"
