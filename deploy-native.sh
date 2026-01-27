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

# Check if SSH_PASS is set for non-interactive login
if [ -n "$SSH_PASS" ]; then
    if ! command -v sshpass &> /dev/null; then
        echo "Authentication with password requires 'sshpass' but it is not installed."
        exit 1
    fi
    SSH_CMD="sshpass -p $SSH_PASS ssh"
    SCP_CMD="sshpass -p $SSH_PASS scp"
    RSYNC_CMD="sshpass -p $SSH_PASS rsync"
else
    SSH_CMD="ssh"
    SCP_CMD="scp"
    RSYNC_CMD="rsync"
fi

# Test SSH connection
echo "🔌 Testing SSH connection..."
if ! $SSH_CMD -o ConnectTimeout=5 -o BatchMode=yes "$PI_HOST" "echo 'SSH OK'" 2>/dev/null; then
    echo "⚠️  SSH key auth failed. You may need to enter password."
    $SSH_CMD -o ConnectTimeout=10 "$PI_HOST" "echo 'SSH OK'" || {
        echo "❌ SSH connection failed!"
        exit 1
    }
fi
echo "✅ SSH connection OK"
echo ""

# Create directories on Pi
echo "📁 Creating directories..."
if [ -n "$SSH_PASS" ]; then
    $SSH_CMD "$PI_HOST" "echo '$SSH_PASS' | sudo -S mkdir -p $PROJECT_DIR $DATA_DIR $CONFIG_DIR && echo '$SSH_PASS' | sudo -S chown -R \$(whoami):\$(whoami) $PROJECT_DIR $DATA_DIR"
else
    $SSH_CMD "$PI_HOST" "sudo mkdir -p $PROJECT_DIR $DATA_DIR $CONFIG_DIR && sudo chown -R \$(whoami):\$(whoami) $PROJECT_DIR $DATA_DIR"
fi

# Sync files to Pi
echo "📦 Syncing files..."
$RSYNC_CMD -avz --progress \
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
if [ -n "$SSH_PASS" ]; then
    # sshpass with -t can be tricky, so we use non-interactive mode with sudo -S
    $SSH_CMD "$PI_HOST" "cd $PROJECT_DIR && chmod +x install.sh && echo '$SSH_PASS' | sudo -S ./install.sh --skip-preflight --no-tailscale"
else
    $SSH_CMD -t "$PI_HOST" "cd $PROJECT_DIR && chmod +x install.sh && sudo ./install.sh --skip-preflight --no-tailscale"
fi
echo "✅ Installation completed"
echo ""

# Wait for startup
echo "⏳ Waiting for service to start..."
sleep 5

# Health check
echo "🏥 Health check..."
if $SSH_CMD "$PI_HOST" "curl -sf http://localhost:8080/api/health > /dev/null"; then
    echo "✅ API is healthy!"
else
    echo "⚠️  API not responding, checking logs..."
    if [ -n "$SSH_PASS" ]; then
        $SSH_CMD "$PI_HOST" "echo '$SSH_PASS' | sudo -S journalctl -u pi-control -n 20 --no-pager"
    else
        $SSH_CMD "$PI_HOST" "sudo journalctl -u pi-control -n 20 --no-pager"
    fi
    exit 1
fi

echo ""
echo "=========================================="
echo "  ✅ Deployment Complete!"
echo "=========================================="
echo ""
PI_IP=$($SSH_CMD "$PI_HOST" "hostname -I | awk '{print \$1}'" 2>/dev/null || echo "$PI_HOST")
echo "Access: http://$PI_IP"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status pi-control   # Service status"
echo "  sudo journalctl -u pi-control -f   # View logs"
echo "  sudo systemctl restart pi-control  # Restart"
echo ""
