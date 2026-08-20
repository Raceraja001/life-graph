#!/bin/bash
# Life Graph Restore Script
#
# Usage:
#   ./scripts/restore.sh backups/life_graph_20260702_120000.dump
#
# Environment variables:
#   PGUSER     — PostgreSQL user    (default: life_graph)
#   PGDATABASE — Database name      (default: life_graph)
#   PGHOST     — Database host      (default: localhost)

set -euo pipefail

# ── Config ────────────────────────────────────────────────────
DB_USER=${PGUSER:-life_graph}
DB_NAME=${PGDATABASE:-life_graph}
DB_HOST=${PGHOST:-localhost}

# ── Validate arguments ────────────────────────────────────────
if [ $# -eq 0 ]; then
    echo "Usage: $0 <backup_file.dump>"
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

# ── Confirm with user ────────────────────────────────────────
echo "WARNING: This will overwrite the database '$DB_NAME' on host '$DB_HOST'"
echo "Backup file: $BACKUP_FILE"
read -p "Continue? (y/N) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "[$(date)] Restoring from $BACKUP_FILE..."
    pg_restore -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" \
        --clean --if-exists \
        "$BACKUP_FILE"
    echo "[$(date)] Restore complete"
else
    echo "Restore cancelled."
    exit 0
fi
