#!/bin/bash
# Pi Control Panel - Fresh Installation Script
# Run as root or with sudo

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Pi Control Panel - Fresh Installation${NC}"
echo "========================================"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root${NC}" 
   exit 1
fi

# Configuration
INSTALL_DIR="/opt"
PANEL_DIR="$INSTALL_DIR/pi-panel"
AGENT_DIR="$INSTALL_DIR/pi-agent"
CONFIG_DIR_PANEL="/etc/pi-panel"
CONFIG_DIR_AGENT="/etc/pi-agent"
DATA_DIR_PANEL="/var/lib/pi-panel"
DATA_DIR_AGENT="/var/lib/pi-agent"
BACKUP_DIR="/var/backups/pi-panel"

echo "Step 1/10: Installing dependencies..."
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv git curl

echo "Step 2/10: Creating pi-agent user..."
if ! id "pi-agent" &>/dev/null; then
    useradd --system --shell /bin/false --home-dir /nonexistent pi-agent
    echo -e "${GREEN}✓${NC} User pi-agent created"
else
    echo -e "${YELLOW}!${NC} User pi-agent already exists"
fi

echo "Step 3/10: Creating directories..."
mkdir -p "$PANEL_DIR/api"
mkdir -p "$AGENT_DIR"
mkdir -p "$CONFIG_DIR_PANEL"
mkdir -p "$CONFIG_DIR_AGENT"
mkdir -p "$DATA_DIR_PANEL"
mkdir -p "$DATA_DIR_AGENT"
mkdir -p "$BACKUP_DIR"

echo "Step 4/10: Copying application files..."
# Assuming current directory is the git repo
cp -r panel/api/* "$PANEL_DIR/api/"
cp -r agent/* "$AGENT_DIR/"

echo "Step 5/10: Installing Python dependencies..."
cd "$PANEL_DIR/api"
python3 -m pip install -q -r requirements.txt

cd "$AGENT_DIR"
python3 -m pip install -q -r requirements.txt

echo "Step 6/10: Generating secrets..."
JWT_SECRET=$(openssl rand -base64 64 | tr -d '\n')
HMAC_SECRET=$(openssl rand -hex 64)

cat > "$CONFIG_DIR_PANEL/secrets.yaml" <<EOF
# Auto-generated secrets - $(date)
# KEEP THIS FILE SECURE (600 root:root)

jwt_secret: "$JWT_SECRET"
hmac_secret: "$HMAC_SECRET"
EOF

cat > "$CONFIG_DIR_AGENT/secrets.yaml" <<EOF
# Auto-generated secrets - $(date)
# KEEP THIS FILE SECURE (600 root:root)

hmac_secret: "$HMAC_SECRET"
EOF

echo "Step 7/10: Copying configuration files..."
cp deployment/config/panel.yaml.example "$CONFIG_DIR_PANEL/config.yaml"
cp deployment/config/agent.yaml.example "$CONFIG_DIR_AGENT/config.yaml"
cp panel/api/core/actions/registry.yaml "$CONFIG_DIR_PANEL/registry.yaml"
cp agent/policy/registry.yaml "$CONFIG_DIR_AGENT/policy/registry.yaml"

echo "Step 8/10: Setting permissions..."
chmod 600 "$CONFIG_DIR_PANEL/secrets.yaml"
chmod 600 "$CONFIG_DIR_AGENT/secrets.yaml"
chmod 644 "$CONFIG_DIR_PANEL/config.yaml"
chmod 644 "$CONFIG_DIR_AGENT/config.yaml"
chown root:root "$CONFIG_DIR_PANEL"/*
chown root:root "$CONFIG_DIR_AGENT"/*

# Agent data directory
chown -R pi-agent:pi-agent "$DATA_DIR_AGENT"
chmod 755 "$DATA_DIR_AGENT"

# Panel data directory (created by DynamicUser at runtime)
chmod 755 "$DATA_DIR_PANEL"

echo "Step 9/10: Installing systemd units..."
cp deployment/systemd/pi-panel-api.service /etc/systemd/system/
cp deployment/systemd/pi-agent.service /etc/systemd/system/
systemctl daemon-reload

echo "Step 10/10: Starting services..."
systemctl enable pi-agent
systemctl enable pi-panel-api
systemctl start pi-agent
sleep 2
systemctl start pi-panel-api
sleep 2

echo ""
echo -e "${GREEN}✓ Installation complete!${NC}"
echo ""
echo "Service status:"
systemctl status pi-agent --no-pager -l || true
systemctl status pi-panel-api --no-pager -l || true

echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Configure firewall: sudo deployment/firewall/ufw-setup.sh"
echo "2. Access Panel: http://localhost:8000"
echo "3. Create owner account: http://localhost:8000/auth/first-run/create-owner"
echo "4. Review logs: sudo journalctl -u pi-panel-api -f"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "- Config files: $CONFIG_DIR_PANEL and $CONFIG_DIR_AGENT"
echo "- Secrets: $CONFIG_DIR_PANEL/secrets.yaml (600 root:root)"
echo "- Database: $DATA_DIR_PANEL/control.db"
echo ""
