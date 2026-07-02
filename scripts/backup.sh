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

# ── pg_dump ───────────────────────────────────────────────────
echo "[$(date)] Starting backup..."
pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" \
    --format=custom \
    --compress=9 \
    --file="$BACKUP_DIR/life_graph_${TIMESTAMP}.dump"

echo "[$(date)] Backup created: life_graph_${TIMESTAMP}.dump"

# ── Clean old backups ─────────────────────────────────────────
find "$BACKUP_DIR" -name "life_graph_*.dump" -mtime +$RETENTION_DAYS -delete
echo "[$(date)] Cleaned backups older than $RETENTION_DAYS days"

# ── Optional: restic encrypted off-site backup ────────────────
if command -v restic &> /dev/null && [ -n "${RESTIC_REPOSITORY:-}" ]; then
    echo "[$(date)] Running restic backup..."
    restic backup "$BACKUP_DIR" --tag life_graph
    restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune
    echo "[$(date)] Restic backup complete"
fi

echo "[$(date)] Backup complete"
