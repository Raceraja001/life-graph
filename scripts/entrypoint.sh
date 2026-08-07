#!/bin/bash
# ── Life Graph Entrypoint ─────────────────────────────────────
# Runs Alembic migrations then starts the application.
# Used by Docker as the container entrypoint.

set -e

echo "╔══════════════════════════════════════════════════╗"
echo "║          Life Graph — Starting Up                ║"
echo "╚══════════════════════════════════════════════════╝"

# ── Trust the bind-mounted repo, if present ───────────────────
# git refuses to operate on a directory owned by a different UID than the
# running user (bind mounts keep host ownership) — cody-ambient's
# git-worktree isolation would silently never activate without this.
if [ -d /repo/.git ]; then
    git config --global --add safe.directory /repo
fi

# ── Wait for Postgres ─────────────────────────────────────────
echo "⏳ Waiting for database..."
MAX_RETRIES=30
RETRY=0
until python -c "
import sys
try:
    import psycopg2
    conn = psycopg2.connect('$LIFE_GRAPH_DATABASE_URL_SYNC')
    conn.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    RETRY=$((RETRY + 1))
    if [ $RETRY -ge $MAX_RETRIES ]; then
        echo "❌ Database not ready after ${MAX_RETRIES} attempts. Starting anyway..."
        break
    fi
    echo "   Attempt $RETRY/$MAX_RETRIES..."
    sleep 2
done
echo "✅ Database ready"

# ── Run Migrations ────────────────────────────────────────────
echo "🔄 Running database migrations..."
if alembic upgrade head; then
    echo "✅ Migrations complete"
else
    echo "⚠️  Migration failed — app may still start with existing schema"
fi

# ── Start Application ────────────────────────────────────────
echo "🚀 Starting Life Graph..."
exec "$@"
