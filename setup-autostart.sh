#!/bin/bash
# Pi Control Panel - Auto-Start Setup Script
# This script sets up the Pi Control Panel to automatically start on any Raspberry Pi
# 
# Usage: 
#   git clone https://github.com/BGirginn/rasp_pi_webUI.git
#   cd rasp_pi_webUI
#   chmod +x setup-autostart.sh
#   ./setup-autostart.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Directories
PROJECT_DIR="/opt/pi-control"
DATA_DIR="/var/lib/pi-control"
CONFIG_DIR="/etc/pi-control"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect current user
INSTALL_USER="${SUDO_USER:-$(whoami)}"
INSTALL_GROUP="$(id -gn $INSTALL_USER)"

echo -e "${BLUE}=========================================="
echo "  🍓 Pi Control Panel - Auto Setup"
echo -e "==========================================${NC}"
echo ""
echo -e "${YELLOW}Installation User:${NC} $INSTALL_USER"
echo -e "${YELLOW}Install Directory:${NC} $PROJECT_DIR"
echo ""

# Check if running as root or with sudo
if [[ $EUID -eq 0 ]] && [[ -z "$SUDO_USER" ]]; then
    echo -e "${RED}❌ Please run this script with sudo, not as root directly${NC}"
    echo "   Usage: sudo ./setup-autostart.sh"
    exit 1
fi

# Check if running on Raspberry Pi
check_raspberry_pi() {
    if [[ ! -f /etc/rpi-issue ]] && [[ ! $(uname -m) =~ ^(arm|aarch64) ]]; then
        echo -e "${YELLOW}⚠️  Warning: This doesn't appear to be a Raspberry Pi${NC}"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
    fi
}

# Install system dependencies
install_dependencies() {
    echo -e "${BLUE}📦 Installing system dependencies...${NC}"
    
    apt-get update -qq
    
    # Python
    echo "  → Installing Python 3..."
    apt-get install -y python3 python3-pip python3-venv python3-dev > /dev/null 2>&1
    
    # Node.js 20
    echo "  → Installing Node.js..."
    if ! command -v node &> /dev/null || [[ $(node -v | cut -d. -f1 | tr -d 'v') -lt 18 ]]; then
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1
        apt-get install -y nodejs > /dev/null 2>&1
    fi
    
    # Caddy
    echo "  → Installing Caddy..."
    if ! command -v caddy &> /dev/null; then
        apt-get install -y debian-keyring debian-archive-keyring apt-transport-https > /dev/null 2>&1
        curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg 2>/dev/null
        curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list > /dev/null
        apt-get update -qq
        apt-get install -y caddy > /dev/null 2>&1
    fi
    
    # SQLite
    apt-get install -y sqlite3 > /dev/null 2>&1
    
    echo -e "${GREEN}  ✅ Dependencies installed${NC}"
}

# Create directories
create_directories() {
    echo -e "${BLUE}📁 Creating directories...${NC}"
    
    mkdir -p "$PROJECT_DIR" "$DATA_DIR" "$CONFIG_DIR"
    chown -R "$INSTALL_USER:$INSTALL_GROUP" "$PROJECT_DIR" "$DATA_DIR"
    
    echo -e "${GREEN}  ✅ Directories created${NC}"
}

# Copy project files
copy_project_files() {
    echo -e "${BLUE}📂 Copying project files...${NC}"
    
    # Copy everything except node_modules, venv, .git, etc.
    rsync -a --progress \
        --exclude 'node_modules' \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude '.git' \
        --exclude 'venv' \
        --exclude '.env' \
        --exclude '*.db' \
        "$SCRIPT_DIR/" "$PROJECT_DIR/"
    
    chown -R "$INSTALL_USER:$INSTALL_GROUP" "$PROJECT_DIR"
    
    echo -e "${GREEN}  ✅ Project files copied${NC}"
}

# Setup Python virtual environment
setup_python() {
    echo -e "${BLUE}🐍 Setting up Python environment...${NC}"
    
    cd "$PROJECT_DIR"
    
    # Create venv as the install user
    sudo -u "$INSTALL_USER" python3 -m venv venv
    
    # Install dependencies
    sudo -u "$INSTALL_USER" "$PROJECT_DIR/venv/bin/pip" install --upgrade pip > /dev/null 2>&1
    sudo -u "$INSTALL_USER" "$PROJECT_DIR/venv/bin/pip" install -r panel/api/requirements.txt > /dev/null 2>&1
    
    echo -e "${GREEN}  ✅ Python environment ready${NC}"
}

# Build UI
build_ui() {
    echo -e "${BLUE}🔨 Building UI...${NC}"
    
    cd "$PROJECT_DIR/panel/ui"
    
    # Install and build as the install user
    sudo -u "$INSTALL_USER" npm install --silent > /dev/null 2>&1
    sudo -u "$INSTALL_USER" npm run build > /dev/null 2>&1
    
    echo -e "${GREEN}  ✅ UI built${NC}"
}

# Generate secrets
generate_secrets() {
    echo -e "${BLUE}🔐 Generating secrets...${NC}"
    
    if [ ! -f "$CONFIG_DIR/jwt_secret" ]; then
        openssl rand -hex 32 > "$CONFIG_DIR/jwt_secret"
        chmod 600 "$CONFIG_DIR/jwt_secret"
        echo "  → JWT secret generated"
    else
        echo "  → JWT secret already exists"
    fi
    
    echo -e "${GREEN}  ✅ Secrets configured${NC}"
}

# Create dynamic systemd service
create_systemd_service() {
    echo -e "${BLUE}🚀 Creating systemd service...${NC}"
    
    cat > /etc/systemd/system/pi-control.service << EOF
[Unit]
Description=Pi Control Panel API
Documentation=https://github.com/BGirginn/rasp_pi_webUI
After=network.target

[Service]
Type=simple
User=$INSTALL_USER
Group=$INSTALL_GROUP
WorkingDirectory=/opt/pi-control/panel/api
Environment=PYTHONPATH=/opt/pi-control/panel/api
Environment=DATABASE_PATH=/var/lib/pi-control/control.db
Environment=TELEMETRY_DB_PATH=/var/lib/pi-control/telemetry.db
Environment=AGENT_SOCKET=/run/pi-control/agent.sock
Environment=JWT_SECRET_FILE=/etc/pi-control/jwt_secret
Environment=API_DEBUG=false
ExecStart=/opt/pi-control/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8080
Restart=always
RestartSec=5
TimeoutStopSec=5
KillMode=mixed

# Security hardening
ProtectSystem=full
ProtectHome=false
ReadWritePaths=/var/lib/pi-control /opt/pi-control
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

    echo -e "${GREEN}  ✅ Systemd service created${NC}"
}

# Configure Caddy
configure_caddy() {
    echo -e "${BLUE}🌐 Configuring Caddy...${NC}"
    
    cp "$PROJECT_DIR/caddy/Caddyfile" /etc/caddy/Caddyfile
    
    echo -e "${GREEN}  ✅ Caddy configured${NC}"
}

# Start and enable services
start_services() {
    echo -e "${BLUE}🎯 Starting services...${NC}"
    
    systemctl daemon-reload
    
    # Enable and start pi-control
    systemctl enable pi-control > /dev/null 2>&1
    systemctl restart pi-control
    
    # Enable and restart Caddy
    systemctl enable caddy > /dev/null 2>&1
    systemctl restart caddy
    
    echo -e "${GREEN}  ✅ Services started and enabled for boot${NC}"
}

# Health check
health_check() {
    echo -e "${BLUE}🏥 Running health check...${NC}"
    
    sleep 5
    
    if curl -sf http://localhost:8080/api/health > /dev/null; then
        echo -e "${GREEN}  ✅ API is healthy!${NC}"
        return 0
    else
        echo -e "${RED}  ❌ API not responding${NC}"
        echo "  Checking logs..."
        journalctl -u pi-control -n 20 --no-pager
        return 1
    fi
}

# Main installation flow
main() {
    check_raspberry_pi
    install_dependencies
    create_directories
    copy_project_files
    setup_python
    build_ui
    generate_secrets
    create_systemd_service
    configure_caddy
    start_services
    
    if health_check; then
        echo ""
        echo -e "${GREEN}=========================================="
        echo "  ✅ Installation Complete!"
        echo -e "==========================================${NC}"
        echo ""
        
        PI_IP=$(hostname -I | awk '{print $1}')
        echo -e "${BLUE}Access your Pi Control Panel:${NC}"
        echo "  → http://$PI_IP"
        echo ""
        echo -e "${BLUE}Default credentials:${NC}"
        echo "  → Username: admin"
        echo "  → Password: admin123"
        echo ""
        echo -e "${YELLOW}⚠️  Change the default password after first login!${NC}"
        echo ""
        echo -e "${BLUE}Useful commands:${NC}"
        echo "  → sudo systemctl status pi-control  # Service status"
        echo "  → sudo journalctl -u pi-control -f  # View logs"
        echo "  → sudo systemctl restart pi-control # Restart service"
        echo ""
        echo -e "${GREEN}🎉 Pi Control Panel will now auto-start on every boot!${NC}"
    else
        echo -e "${RED}Installation completed but health check failed.${NC}"
        echo "Please check the logs above for errors."
        exit 1
    fi
}

# Run main
main "$@"
