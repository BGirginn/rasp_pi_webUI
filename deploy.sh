#!/bin/bash
# Pi Control Panel - Deploy Script
# Usage: ./deploy.sh [pi-user@pi-host]

set -e

PI_HOST="${1:-bgirgin@192.168.0.102}"
PROJECT_DIR="/opt/pi-control"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "  Pi Control Panel - Deployment Script"
echo "=========================================="
echo ""
echo "Target: $PI_HOST"
echo "Remote Dir: $PROJECT_DIR"
echo ""

# Check SSH connectivity
echo "🔌 Testing SSH connection..."
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$PI_HOST" "echo 'SSH OK'" 2>/dev/null; then
    echo "⚠️  SSH key auth failed. You may need to enter password."
    # Try with password prompt
    ssh -o ConnectTimeout=10 "$PI_HOST" "echo 'SSH OK'" || {
        echo "❌ SSH connection failed!"
        exit 1
    }
fi
echo "✅ SSH connection OK"
echo ""

# Create remote directory
echo "📁 Creating remote directory..."
ssh "$PI_HOST" "sudo mkdir -p $PROJECT_DIR && sudo chown \$(whoami):\$(whoami) $PROJECT_DIR"

# Sync files
echo "📦 Syncing files to Pi..."
rsync -avz --progress \
    --exclude 'node_modules' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.git' \
    --exclude 'venv' \
    --exclude '.env' \
    --exclude '*.db' \
    "$SCRIPT_DIR/" "$PI_HOST:$PROJECT_DIR/"

echo "✅ Files synced"
echo ""

# Check Docker on Pi
echo "🐳 Checking Docker on Pi..."
if ! ssh "$PI_HOST" "command -v docker &> /dev/null"; then
    echo "❌ Docker not installed on Pi!"
    echo "   Install with: curl -fsSL https://get.docker.com | sh"
    exit 1
fi
echo "✅ Docker found"

# Check Docker Compose
if ! ssh "$PI_HOST" "command -v docker-compose &> /dev/null && docker compose version &> /dev/null"; then
    echo "⚠️  Docker Compose not found, installing..."
    ssh "$PI_HOST" "sudo apt-get update && sudo apt-get install -y docker-compose-plugin"
fi
echo "✅ Docker Compose OK"
echo ""

# Create .env if not exists
echo "🔐 Setting up environment..."
ssh "$PI_HOST" "cd $PROJECT_DIR && if [ ! -f .env ]; then cp .env.example .env && echo 'Created .env from example'; fi"

# Generate JWT secret if not set
ssh "$PI_HOST" "cd $PROJECT_DIR && if ! grep -q 'JWT_SECRET=.\+' .env 2>/dev/null; then sed -i 's/JWT_SECRET=.*/JWT_SECRET='\"$(openssl rand -hex 32)\"'/' .env; echo 'Generated JWT secret'; fi"

echo ""
echo "🚀 Starting Docker Compose..."
ssh "$PI_HOST" "cd $PROJECT_DIR && docker compose up -d --build"

echo ""
echo "⏳ Waiting for services to start..."
sleep 10

# Health check
echo "🏥 Health check..."
if ssh "$PI_HOST" "curl -sf http://localhost:8080/api/health > /dev/null"; then
    echo "✅ API is healthy!"
else
    echo "⚠️  API not responding yet, checking logs..."
    ssh "$PI_HOST" "cd $PROJECT_DIR && docker compose logs --tail=20 panel"
fi

echo ""
echo "=========================================="
echo "  ✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "Access URLs:"
echo "  - Panel UI:  http://$PI_HOST:3000"
echo "  - API:       http://$PI_HOST:8080/api"
echo "  - API Docs:  http://$PI_HOST:8080/api/docs"
echo ""
echo "Default login: admin / admin123"
echo "⚠️  CHANGE THE PASSWORD IMMEDIATELY!"
echo ""
echo "Useful commands:"
echo "  ssh $PI_HOST 'cd $PROJECT_DIR && docker compose logs -f'"
echo "  ssh $PI_HOST 'cd $PROJECT_DIR && docker compose restart'"
echo "  ssh $PI_HOST 'cd $PROJECT_DIR && docker compose down'"
echo ""
