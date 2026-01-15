#!/bin/bash
# Pi Control Panel - Native Deployment Script
# Usage: ./deploy-native.sh [user@host]

set -e

PI_HOST="${1:-}"

if [ -z "$PI_HOST" ]; then
    echo "Usage: ./deploy-native.sh user@pi-ip-address"
    echo "Example: ./deploy-native.sh pi@192.168.1.100"
    exit 1
fi
PROJECT_DIR="/opt/pi-control"
DATA_DIR="/var/lib/pi-control"
CONFIG_DIR="/etc/pi-control"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "  Pi Control Panel - Native Deployment"
echo "=========================================="
echo ""
echo "Target: $PI_HOST"
echo "Install Dir: $PROJECT_DIR"
echo ""

# Test SSH connection
echo "🔌 Testing SSH connection..."
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$PI_HOST" "echo 'SSH OK'" 2>/dev/null; then
    echo "⚠️  SSH key auth failed. You may need to enter password."
    ssh -o ConnectTimeout=10 "$PI_HOST" "echo 'SSH OK'" || {
        echo "❌ SSH connection failed!"
        exit 1
    }
fi
echo "✅ SSH connection OK"
echo ""

# Create directories on Pi
echo "📁 Creating directories..."
ssh "$PI_HOST" "sudo mkdir -p $PROJECT_DIR $DATA_DIR $CONFIG_DIR && sudo chown -R \$(whoami):\$(whoami) $PROJECT_DIR $DATA_DIR"

# Sync files to Pi
echo "📦 Syncing files..."
rsync -avz --progress \
    --exclude 'node_modules' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.git' \
    --exclude 'venv' \
    --exclude '.env' \
    --exclude '*.db' \
    --exclude 'dist' \
    "$SCRIPT_DIR/" "$PI_HOST:$PROJECT_DIR/"

echo "✅ Files synced"
echo ""

# Run installer on remote to build and configure
echo "🚀 Running installer on remote..."
ssh -t "$PI_HOST" "cd $PROJECT_DIR && chmod +x install.sh && sudo ./install.sh --skip-preflight --no-tailscale"
echo "✅ Installation completed"
echo ""

# Wait for startup
echo "⏳ Waiting for service to start..."
sleep 5

# Health check
echo "🏥 Health check..."
if ssh "$PI_HOST" "curl -sf http://localhost:8080/api/health > /dev/null"; then
    echo "✅ API is healthy!"
else
    echo "⚠️  API not responding, checking logs..."
    ssh "$PI_HOST" "sudo journalctl -u pi-control -n 20 --no-pager"
    exit 1
fi

echo ""
echo "=========================================="
echo "  ✅ Deployment Complete!"
echo "=========================================="
echo ""
PI_IP=$(ssh "$PI_HOST" "hostname -I | awk '{print \$1}'" 2>/dev/null || echo "$PI_HOST")
echo "Access: http://$PI_IP"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status pi-control   # Service status"
echo "  sudo journalctl -u pi-control -f   # View logs"
echo "  sudo systemctl restart pi-control  # Restart"
echo ""
