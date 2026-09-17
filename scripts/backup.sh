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
#   MINIO_DATA_DIR  — If set, MinIO's data directory is archived next to the dump
#   RESTIC_REPOSITORY — If set, runs restic backup after pg_dump (best-effort)
#   RESTIC_FORGET   — 0 to skip forget/prune (append-only repositories) (default: 1)
#   RESTIC_PROBE_TIMEOUT — Seconds to wait for the repository before skipping (default: 60)

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

# ── MinIO object data (voice notes, images, documents, archives) ─
# Previously MinIO data was only ever copied by the optional restic step, so
# without an off-site repo the original uploads had no backup at all — only
# the memories derived from them did. Archived next to the dump on every run.
# The files are read while MinIO runs; an object mid-upload may be caught
# incomplete, which a personal-scale nightly run can tolerate.
MINIO_ARCHIVE=""
MINIO_SIZE=0
if [ -n "${MINIO_DATA_DIR:-}" ] && [ -d "$MINIO_DATA_DIR" ]; then
    MINIO_ARCHIVE="minio_${TIMESTAMP}.tar.gz"
    tar -czf "$BACKUP_DIR/$MINIO_ARCHIVE" -C "$MINIO_DATA_DIR" .
    MINIO_SIZE=$(stat -c%s "$BACKUP_DIR/$MINIO_ARCHIVE" 2>/dev/null || echo 0)
    echo "[$(date)] MinIO data archived: $MINIO_ARCHIVE (${MINIO_SIZE} bytes)"
fi

# ── Clean old backups ─────────────────────────────────────────
find "$BACKUP_DIR" \( -name "life_graph_*.dump" -o -name "minio_*.tar.gz" \) \
    -mtime +$RETENTION_DAYS -delete
echo "[$(date)] Cleaned backups older than $RETENTION_DAYS days"

# ── Optional: restic encrypted off-site backup ────────────────
RESTIC_RAN=false
# RESTIC_REPOSITORY_FILE is restic's own alternative to RESTIC_REPOSITORY; it
# keeps credentials embedded in a rest: URL out of compose files and env dumps.
if command -v restic &> /dev/null \
    && { [ -n "${RESTIC_REPOSITORY:-}" ] || [ -n "${RESTIC_REPOSITORY_FILE:-}" ]; }; then
    echo "[$(date)] Running restic backup..."
    # Include MinIO object data if its directory is mounted/available
    RESTIC_PATHS=("$BACKUP_DIR")
    if [ -n "${MINIO_DATA_DIR:-}" ] && [ -d "$MINIO_DATA_DIR" ]; then
        RESTIC_PATHS+=("$MINIO_DATA_DIR")
    fi
    # The raw MinIO directory deduplicates across runs; the nightly tarball
    # would re-upload in full every time, so restic skips it.
    #
    # Off-site is best-effort: the dump above already succeeded, and a remote
    # that is asleep or offline (e.g. a laptop target) must not turn that into
    # a failed job. The error is recorded instead, so a streak of off-site
    # failures is still visible in job_runs.
    #
    # restic retries an unreachable backend with backoff for ~15 minutes before
    # giving up, so probe first and skip fast when nobody answers.
    if ! timeout "${RESTIC_PROBE_TIMEOUT:-60}" restic cat config --no-lock > /dev/null 2>&1; then
        OFFSITE_ERROR="repository unreachable (no answer within ${RESTIC_PROBE_TIMEOUT:-60}s)"
        echo "[$(date)] WARNING: $OFFSITE_ERROR — skipping off-site copy; local backup is intact"
    elif restic backup "${RESTIC_PATHS[@]}" --tag life_graph --exclude 'minio_*.tar.gz'; then
        RESTIC_RAN=true
        echo "[$(date)] Restic backup complete"
        # RESTIC_FORGET=0 for an append-only repository (rest-server
        # --append-only), where this client cannot delete snapshots by design
        # and pruning runs on the repository host instead.
        if [ "${RESTIC_FORGET:-1}" = "1" ]; then
            restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune \
                || echo "[$(date)] WARNING: restic forget/prune failed"
        fi
    else
        OFFSITE_ERROR="restic backup failed"
        echo "[$(date)] WARNING: $OFFSITE_ERROR — local backup is intact"
    fi
fi

record_job_run "success" \
    "{\"dump\": \"life_graph_${TIMESTAMP}.dump\", \"size_bytes\": $DUMP_SIZE, \"minio_archive\": \"${MINIO_ARCHIVE}\", \"minio_size_bytes\": $MINIO_SIZE, \"offsite\": $RESTIC_RAN, \"offsite_error\": \"${OFFSITE_ERROR:-}\"}"

echo "[$(date)] Backup complete"
