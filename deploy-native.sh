#!/bin/bash
# Pi Control Panel - Native Deployment Script
# Usage: ./deploy-native.sh [user@host]

set -e

PI_HOST="${1:-bgirgin@100.80.90.68}"
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

# Build UI on Pi
echo "🔨 Building UI..."
ssh "$PI_HOST" "cd $PROJECT_DIR/panel/ui && npm install && npm run build"
echo "✅ UI built"
echo ""

# Setup Python virtual environment
echo "🐍 Setting up Python environment..."
ssh "$PI_HOST" "cd $PROJECT_DIR && python3 -m venv venv && source venv/bin/activate && pip install -r panel/api/requirements.txt"
echo "✅ Python environment ready"
echo ""

# Generate JWT secret if not exists
echo "🔐 Setting up secrets..."
ssh "$PI_HOST" "if [ ! -f $CONFIG_DIR/jwt_secret ]; then openssl rand -hex 32 | sudo tee $CONFIG_DIR/jwt_secret > /dev/null && sudo chmod 600 $CONFIG_DIR/jwt_secret; echo 'JWT secret generated'; fi"

# Install and configure Caddy
echo "🌐 Configuring Caddy..."
ssh "$PI_HOST" "sudo cp $PROJECT_DIR/caddy/Caddyfile /etc/caddy/Caddyfile && sudo systemctl reload caddy || sudo systemctl start caddy"
echo "✅ Caddy configured"
echo ""

# Install and start systemd service
echo "🚀 Installing systemd service..."
ssh "$PI_HOST" "sudo cp $PROJECT_DIR/pi-control.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable pi-control && sudo systemctl restart pi-control"
echo "✅ Service installed"
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
