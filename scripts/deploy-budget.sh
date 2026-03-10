#!/bin/bash
# deploy-budget.sh — Deploy Budget Tracker to LXC 105
# Run from Mac Mini: bash scripts/deploy-budget.sh

set -euo pipefail

LXC_HOST="root@192.168.1.105"
APP_DIR="/opt/budget-tracker"
LOCAL_DIR="/Users/arnaud/mon-assistant/memory/projects/budget-tracker"

echo "🚀 Deploying Budget Tracker to LXC 105..."

# Check SSH connectivity
if ! ssh -o ConnectTimeout=5 $LXC_HOST true 2>/dev/null; then
    echo "❌ Cannot reach $LXC_HOST — is LXC 105 running?"
    exit 1
fi

# Rsync app files (exclude data, venv, git, PDFs, caches)
rsync -avz --delete \
    --exclude='.git' \
    --exclude='venv' \
    --exclude='data' \
    --exclude='__pycache__' \
    --exclude='.env' \
    --exclude='*.pdf' \
    --exclude='e2e-screenshots' \
    --exclude='test_e2e_data' \
    --exclude='.claude' \
    "$LOCAL_DIR/" "$LXC_HOST:$APP_DIR/"

# Restart service
ssh $LXC_HOST "systemctl restart budget-tracker"

# Wait + health check
sleep 2
STATUS=$(ssh $LXC_HOST "systemctl is-active budget-tracker" || true)
if [ "$STATUS" = "active" ]; then
    echo "✅ Budget Tracker deployed and running"
    echo "   Local: http://192.168.1.105:8080"
    echo "   Public: https://budget.nanoserveur.fr"
else
    echo "❌ Service not running — check logs:"
    echo "   ssh $LXC_HOST journalctl -u budget-tracker -n 20"
    exit 1
fi
