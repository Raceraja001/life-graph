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
# Default to whatever origin actually points HEAD at, rather than assuming.
# This used to be hardcoded to "main"; this repo's default branch is master,
# so the documented no-argument form always died at `git checkout main` on
# the VM. Deriving it means the default cannot drift out of sync again.
DEFAULT_BRANCH="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')"
BRANCH="${2:-${DEFAULT_BRANCH:-master}}"
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

# ── Pre-flight ───────────────────────────────────────────────
# Everything below runs against production, so verify what we can from here
# first. A bad branch name should fail on this machine with a clear message,
# not halfway through a checkout on the live box.
echo "🔎 Pre-flight..."

if ! git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
    echo "❌ Branch '$BRANCH' does not exist on origin."
    echo "   Available:"
    git ls-remote --heads origin | sed 's|.*refs/heads/|     |'
    exit 1
fi

# Deploying a branch whose local commits were never pushed means the VM
# pulls an older tree than the one under test — silently.
if git rev-parse --verify --quiet "$BRANCH" >/dev/null 2>&1; then
    local_sha="$(git rev-parse "$BRANCH")"
    remote_sha="$(git ls-remote origin "refs/heads/$BRANCH" | cut -f1)"
    if [ "$local_sha" != "$remote_sha" ]; then
        echo "❌ Local '$BRANCH' ($(git rev-parse --short "$BRANCH")) does not match"
        echo "   origin/$BRANCH (${remote_sha:0:7}). The VM would deploy the remote's"
        echo "   version, not yours. Push (or fetch) first."
        exit 1
    fi
fi
echo "   branch '$BRANCH' exists on origin and matches local ✓"
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
HEALTH=$(ssh "$VPS_HOST" "curl -sf http://localhost/health 2>/dev/null || curl -sf http://localhost:8000/health 2>/dev/null || echo '{\"status\":\"unreachable\"}'")

# Read the top-level "status" value rather than grepping the whole body.
# The previous check was `grep -qi "healthy\|ok\|status"`, which reports
# success on almost any response: "healthy" is a substring of "unhealthy",
# and every /health body contains the literal "status" — including a
# degraded one. Splitting on commas isolates the FIRST status field, which
# is the overall verdict; the per-dependency ones nested under "checks"
# come later.
STATUS=$(printf '%s' "$HEALTH" | tr ',' '\n' \
    | grep -m1 -o '"status"[[:space:]]*:[[:space:]]*"[a-z]*"' \
    | grep -o '"[a-z]*"$' | tr -d '"')

case "$STATUS" in
    healthy)
        echo "✅ Deployment successful — /health reports healthy."
        ;;
    degraded)
        echo "⚠️  Deployed, but /health reports DEGRADED (a non-critical"
        echo "   dependency is down — usually Redis). The API is serving."
        echo "   $HEALTH"
        ;;
    *)
        echo "❌ Health check failed — /health reports '\''${STATUS:-no response}'\''."
        echo "   $HEALTH"
        echo "   Check logs: ssh $VPS_HOST '\''cd $REMOTE_DIR && docker compose -f $COMPOSE_FILE logs --tail 50 app'\''"
        exit 1
        ;;
esac

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  🧠 Life Graph deployed to $VPS_HOST"
echo "╚══════════════════════════════════════════════════╝"
