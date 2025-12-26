#!/bin/bash
# Pi Control Panel - Upgrade Script
# Run as root or with sudo

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Pi Control Panel - Upgrade${NC}"
echo "============================"
echo ""

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
BACKUP_DIR="/var/backups/pi-panel"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "Step 1/9: Creating backup..."
mkdir -p "$BACKUP_DIR/$TIMESTAMP"
systemctl stop pi-panel-api
systemctl stop pi-agent

# Backup binaries
cp -r "$PANEL_DIR" "$BACKUP_DIR/$TIMESTAMP/panel"
cp -r "$AGENT_DIR" "$BACKUP_DIR/$TIMESTAMP/agent"

# Backup configs
cp -r "$CONFIG_DIR_PANEL" "$BACKUP_DIR/$TIMESTAMP/config-panel"
cp -r "$CONFIG_DIR_AGENT" "$BACKUP_DIR/$TIMESTAMP/config-agent"

# Backup database
if [ -f "$DATA_DIR_PANEL/control.db" ]; then
    cp "$DATA_DIR_PANEL/control.db" "$BACKUP_DIR/$TIMESTAMP/control.db"
    echo -e "${GREEN}✓${NC} Backup created: $BACKUP_DIR/$TIMESTAMP"
fi

echo "Step 2/9: Updating application files..."
cp -r panel/api/* "$PANEL_DIR/api/"
cp -r agent/* "$AGENT_DIR/"

echo "Step 3/9: Updating Python dependencies..."
cd "$PANEL_DIR/api"
python3 -m pip install -q --upgrade -r requirements.txt

cd "$AGENT_DIR"
python3 -m pip install -q --upgrade -r requirements.txt

echo "Step 4/9: Updating registry files..."
# Preserve custom configs, only update registry if new fields
cp panel/api/core/actions/registry.yaml "$CONFIG_DIR_PANEL/registry.yaml.new"
cp agent/policy/registry.yaml "$CONFIG_DIR_AGENT/policy/registry.yaml.new"

echo -e "${YELLOW}!${NC} Registry files updated to .new - review and merge manually if needed"

echo "Step 5/9: Running database migrations..."
cd "$PANEL_DIR/api"
python3 -c "from db.migrations import run_migrations; import asyncio; asyncio.run(run_migrations('$DATA_DIR_PANEL/control.db'))" || {
    echo -e "${RED}✗${NC} Migration failed! Rolling back..."
    bash deployment/scripts/rollback.sh "$TIMESTAMP"
    exit 1
}

echo "Step 6/9: Updating systemd units..."
cp deployment/systemd/pi-panel-api.service /etc/systemd/system/
cp deployment/systemd/pi-agent.service /etc/systemd/system/
systemctl daemon-reload

echo "Step 7/9: Starting services..."
systemctl start pi-agent
sleep 2
systemctl start pi-panel-api
sleep 2

echo "Step 8/9: Verifying health..."
for i in {1..10}; do
    if curl -sf http://127.0.0.1:8000/api/health > /dev/null; then
        echo -e "${GREEN}✓${NC} Panel API is healthy"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${RED}✗${NC} Health check failed! Rolling back..."
        bash deployment/scripts/rollback.sh "$TIMESTAMP"
        exit 1
    fi
    sleep 2
done

echo "Step 9/9: Cleanup old backups..."
# Keep last 3 backups
ls -t "$BACKUP_DIR" | tail -n +4 | xargs -I {} rm -rf "$BACKUP_DIR/{}"

echo ""
echo -e "${GREEN}✓ Upgrade complete!${NC}"
echo ""
echo "Backup location: $BACKUP_DIR/$TIMESTAMP"
echo "To rollback: sudo deployment/scripts/rollback.sh $TIMESTAMP"
echo ""
