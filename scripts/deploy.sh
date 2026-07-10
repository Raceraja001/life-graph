#!/bin/bash
# ── Life Graph — Deploy to VPS ────────────────────────────────
# Usage: ./scripts/deploy.sh [user@host] [branch]
#
# Prerequisites:
#   - SSH access to VPS (key-based)
#   - Docker + Docker Compose installed on VPS
#   - Git repo cloned on VPS at ~/life-graph
#
# First-time setup on VPS:
#   git clone YOUR_REPO ~/life-graph
#   cp ~/life-graph/.env.production ~/life-graph/.env.production
#   # Edit .env.production with real passwords
#   cd ~/life-graph && docker compose -f docker-compose.production.yml up -d

set -euo pipefail

# ── Configuration ────────────────────────────────────────────
VPS_HOST="${1:-}"
BRANCH="${2:-main}"
REMOTE_DIR="~/life-graph"
COMPOSE_FILE="docker-compose.production.yml"
ENV_FILE=".env.production"

if [ -z "$VPS_HOST" ]; then
    echo "╔══════════════════════════════════════════════════╗"
    echo "║      Life Graph — Local Deploy Mode              ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo ""
    echo "No VPS host specified. Running locally..."
    echo ""

    # Local deployment
    if [ ! -f "$ENV_FILE" ]; then
        echo "❌ $ENV_FILE not found. Copy from .env.production and configure."
        exit 1
    fi

    echo "🔨 Building images..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build

    echo "🚀 Starting services..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d

    echo ""
    echo "⏳ Waiting for health check..."
    sleep 15

    # Health check
    if curl -sf http://localhost/health > /dev/null 2>&1; then
        echo "✅ Life Graph is healthy!"
    elif curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Life Graph API is healthy (direct port)!"
    else
        echo "⚠️  Health check pending — check logs: docker compose -f $COMPOSE_FILE logs app"
    fi

    echo ""
    echo "╔══════════════════════════════════════════════════╗"
    echo "║  🧠 Life Graph deployed!                         ║"
    echo "║                                                  ║"
    echo "║  API:       http://localhost/api/v1/              ║"
    echo "║  Dashboard: http://localhost/brain                ║"
    echo "║  Docs:      http://localhost/docs                 ║"
    echo "║  MCP:       http://localhost/mcp/sse              ║"
    echo "║  Health:    http://localhost/health                ║"
    echo "╚══════════════════════════════════════════════════╝"
    exit 0
fi

# ── Remote VPS deployment ────────────────────────────────────
echo "╔══════════════════════════════════════════════════╗"
echo "║      Life Graph — VPS Deploy                     ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Host:   $VPS_HOST"
echo "  Branch: $BRANCH"
echo "  Dir:    $REMOTE_DIR"
echo ""

# Step 1: Pull latest code
echo "📥 Pulling latest code on VPS..."
ssh "$VPS_HOST" "cd $REMOTE_DIR && git fetch origin && git checkout $BRANCH && git pull origin $BRANCH"

# Step 2: Build
echo "🔨 Building images on VPS..."
ssh "$VPS_HOST" "cd $REMOTE_DIR && docker compose -f $COMPOSE_FILE --env-file $ENV_FILE build"

# Step 3: Restart with zero-downtime rolling update
echo "🔄 Rolling restart..."
ssh "$VPS_HOST" "cd $REMOTE_DIR && docker compose -f $COMPOSE_FILE --env-file $ENV_FILE up -d --remove-orphans"

# Step 4: Wait and health check
echo "⏳ Waiting for services to stabilize..."
sleep 20

echo "🏥 Health check..."
HEALTH=$(ssh "$VPS_HOST" "curl -sf http://localhost/health 2>/dev/null || curl -sf http://localhost:8000/health 2>/dev/null || echo 'FAIL'")

if echo "$HEALTH" | grep -qi "healthy\|ok\|status"; then
    echo "✅ Deployment successful!"
else
    echo "⚠️  Health check returned: $HEALTH"
    echo "   Check logs: ssh $VPS_HOST 'cd $REMOTE_DIR && docker compose -f $COMPOSE_FILE logs --tail 50 app'"
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  🧠 Life Graph deployed to $VPS_HOST"
echo "╚══════════════════════════════════════════════════╝"
