#!/bin/bash
# ============================================================================
# Pi Control Panel - Comprehensive Installation Script
# ============================================================================
# Fully automated, idempotent installer for Pi Control Panel.
# Works on Raspberry Pi 3B+, 4, 5, and Zero 2 W.
# Supports both 32-bit and 64-bit Raspberry Pi OS (Bullseye/Bookworm).
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/BGirginn/rasp_pi_webUI/main/install.sh | sudo bash
#   
#   Or locally:
#   git clone https://github.com/BGirginn/rasp_pi_webUI.git
#   cd rasp_pi_webUI
#   sudo ./install.sh
#
# Options:
#   --skip-preflight    Skip pre-flight checks
#   --no-tailscale      Skip Tailscale installation
#   --upgrade           Upgrade existing installation
#   --verbose           Show verbose output
#
# ============================================================================

set -euo pipefail

# Version
readonly VERSION="2.0.0"
readonly SCRIPT_NAME="Pi Control Panel Installer"

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly MAGENTA='\033[0;35m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

# Directories
readonly PROJECT_DIR="/opt/pi-control"
readonly DATA_DIR="/var/lib/pi-control"
readonly CONFIG_DIR="/etc/pi-control"
readonly LOG_FILE="/var/log/pi-control-install.log"
readonly BACKUP_DIR="/var/backups/pi-control"

# URLs
readonly GITHUB_REPO="https://github.com/BGirginn/rasp_pi_webUI.git"
readonly NODESOURCE_URL="https://deb.nodesource.com/setup_20.x"
readonly CADDY_GPG_URL="https://dl.cloudsmith.io/public/caddy/stable/gpg.key"
readonly CADDY_REPO_URL="https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt"
readonly TAILSCALE_INSTALL_URL="https://tailscale.com/install.sh"

# User detection
INSTALL_USER="${SUDO_USER:-$(whoami)}"
INSTALL_GROUP="$(id -gn "$INSTALL_USER" 2>/dev/null || echo "$INSTALL_USER")"

# Options
SKIP_PREFLIGHT=false
NO_TAILSCALE=false
UPGRADE_MODE=false
VERBOSE=false

# State
STEP=0
TOTAL_STEPS=14
START_TIME=$(date +%s)

# ============================================================================
# Utility Functions
# ============================================================================

log() {
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $*" >> "$LOG_FILE"
}

log_and_print() {
    log "$*"
    echo -e "$*"
}

print_banner() {
    echo ""
    echo -e "${MAGENTA}${BOLD}"
    echo "  ╔═══════════════════════════════════════════════════════════╗"
    echo "  ║                                                           ║"
    echo "  ║   🍓 Pi Control Panel - Installation v${VERSION}           ║"
    echo "  ║                                                           ║"
    echo "  ╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
}

print_step() {
    STEP=$((STEP + 1))
    echo ""
    echo -e "${BLUE}${BOLD}[$STEP/$TOTAL_STEPS] $1${NC}"
    echo -e "${BLUE}$(printf '%.0s─' {1..60})${NC}"
    log "STEP $STEP: $1"
}

success() {
    echo -e "  ${GREEN}✓${NC} $1"
    log "SUCCESS: $1"
}

warn() {
    echo -e "  ${YELLOW}⚠${NC} $1"
    log "WARNING: $1"
}

fail() {
    echo -e "  ${RED}✗${NC} $1"
    log "ERROR: $1"
}

info() {
    echo -e "  ${CYAN}ℹ${NC} $1"
    log "INFO: $1"
}

run_cmd() {
    local description="$1"
    shift
    
    if $VERBOSE; then
        info "Running: $*"
        if "$@" 2>&1 | tee -a "$LOG_FILE"; then
            success "$description"
            return 0
        else
            fail "$description"
            return 1
        fi
    else
        if "$@" >> "$LOG_FILE" 2>&1; then
            success "$description"
            return 0
        else
            fail "$description"
            return 1
        fi
    fi
}

run_silent() {
    "$@" >> "$LOG_FILE" 2>&1 || true
}

spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local i=0
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  ${CYAN}%s${NC} " "${spinstr:i++%${#spinstr}:1}"
        sleep $delay
    done
    printf "\r"
}

cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        echo ""
        echo -e "${RED}${BOLD}Installation failed!${NC}"
        echo -e "${RED}Check the log file: $LOG_FILE${NC}"
        echo ""
        echo "Last 20 lines of log:"
        tail -20 "$LOG_FILE" 2>/dev/null || true
    fi
}

trap cleanup EXIT

# ============================================================================
# Argument Parsing
# ============================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-preflight)
                SKIP_PREFLIGHT=true
                shift
                ;;
            --no-tailscale)
                NO_TAILSCALE=true
                shift
                ;;
            --upgrade)
                UPGRADE_MODE=true
                shift
                ;;
            --verbose|-v)
                VERBOSE=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --skip-preflight    Skip system requirement checks"
                echo "  --no-tailscale      Skip Tailscale installation"
                echo "  --upgrade           Upgrade existing installation"
                echo "  --verbose, -v       Show verbose output"
                echo "  --help, -h          Show this help message"
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done
}

# ============================================================================
# Pre-flight Checks
# ============================================================================

run_preflight() {
    print_step "Running pre-flight checks"
    
    # Check if root
    if [[ $EUID -ne 0 ]]; then
        fail "This script must be run with sudo"
        echo ""
        echo "Usage: sudo $0"
        exit 1
    fi
    
    # Check if running as root directly (not via sudo)
    if [[ -z "${SUDO_USER:-}" ]]; then
        warn "Running as root directly. Will use 'pi' as install user if available."
        if id "pi" &>/dev/null; then
            INSTALL_USER="pi"
            INSTALL_GROUP="pi"
        fi
    fi
    
    success "Running as root with sudo"
    info "Install user: $INSTALL_USER"
    info "Install group: $INSTALL_GROUP"
    
    # Check architecture
    local arch
    arch=$(uname -m)
    if [[ "$arch" == "aarch64" ]]; then
        success "Architecture: 64-bit ARM"
    elif [[ "$arch" == "armv7l" ]] || [[ "$arch" == "armv6l" ]]; then
        success "Architecture: 32-bit ARM"
    else
        warn "Architecture: $arch (not a typical Raspberry Pi)"
    fi
    
    # Check RAM and potentially setup swap
    local total_ram_kb
    total_ram_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    local total_ram_mb=$((total_ram_kb / 1024))
    
    if [[ $total_ram_mb -lt 900 ]]; then
        fail "Insufficient RAM: ${total_ram_mb}MB (minimum 1GB required)"
        exit 1
    elif [[ $total_ram_mb -lt 2048 ]]; then
        warn "Low RAM: ${total_ram_mb}MB. Will configure swap."
        setup_swap
    else
        success "RAM: ${total_ram_mb}MB"
    fi
    
    # Check disk space
    local free_mb
    free_mb=$(df -m / | tail -1 | awk '{print $4}')
    if [[ $free_mb -lt 1000 ]]; then
        fail "Insufficient disk space: ${free_mb}MB (minimum 1GB required)"
        exit 1
    else
        success "Free disk space: ${free_mb}MB"
    fi
    
    # Check internet
    if ! ping -c 1 -W 5 8.8.8.8 &>/dev/null; then
        fail "No internet connectivity"
        exit 1
    fi
    success "Internet connectivity OK"
}

setup_swap() {
    info "Checking swap configuration..."
    
    local swap_total_kb
    swap_total_kb=$(grep SwapTotal /proc/meminfo | awk '{print $2}')
    local swap_total_mb=$((swap_total_kb / 1024))
    
    if [[ $swap_total_mb -lt 1024 ]]; then
        info "Increasing swap to 1GB for npm builds..."
        
        # Using dphys-swapfile if available (Raspberry Pi OS default)
        if [[ -f /etc/dphys-swapfile ]]; then
            sed -i 's/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=1024/' /etc/dphys-swapfile
            systemctl restart dphys-swapfile 2>/dev/null || true
            success "Swap increased to 1GB via dphys-swapfile"
        else
            # Fallback: create swap file manually
            if [[ ! -f /swapfile ]]; then
                dd if=/dev/zero of=/swapfile bs=1M count=1024 status=none
                chmod 600 /swapfile
                mkswap /swapfile >/dev/null
                swapon /swapfile
                echo '/swapfile none swap sw 0 0' >> /etc/fstab
                success "Created 1GB swap file"
            fi
        fi
    else
        success "Swap already adequate: ${swap_total_mb}MB"
    fi
}

# ============================================================================
# Dependency Installation
# ============================================================================

update_system() {
    print_step "Updating system packages"
    
    info "Updating package lists..."
    run_cmd "Package lists updated" apt-get update -qq
    
    info "Installing essential tools..."
    run_cmd "Essential tools installed" apt-get install -y \
        git curl wget gnupg2 ca-certificates lsb-release \
        build-essential sqlite3 openssl rsync
}

install_python() {
    print_step "Installing Python"
    
    # Check current Python version
    local python_version=""
    if command -v python3 &>/dev/null; then
        python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "")
    fi
    
    # Install Python packages
    info "Installing Python 3 and dev packages..."
    run_cmd "Python packages installed" apt-get install -y \
        python3 python3-pip python3-venv python3-dev \
        python3-setuptools python3-wheel
    
    # For D-Bus support (agent needs this)
    info "Installing Python D-Bus bindings..."
    run_silent apt-get install -y python3-dbus python3-gi libdbus-1-dev libgirepository1.0-dev
    success "Python D-Bus bindings installed"
    
    # Verify Python version
    python_version=$(python3 --version)
    success "Python installed: $python_version"
}

install_nodejs() {
    print_step "Installing Node.js"
    
    local current_node_version=""
    if command -v node &>/dev/null; then
        current_node_version=$(node -v | tr -d 'v' | cut -d. -f1)
    fi
    
    # Check if we need to install/upgrade
    if [[ -z "$current_node_version" ]] || [[ "$current_node_version" -lt 18 ]]; then
        info "Setting up NodeSource repository..."
        curl -fsSL "$NODESOURCE_URL" | bash - >> "$LOG_FILE" 2>&1
        
        info "Installing Node.js 20..."
        run_cmd "Node.js installed" apt-get install -y nodejs
    else
        success "Node.js already installed (v$current_node_version)"
    fi
    
    # Verify
    local node_v npm_v
    node_v=$(node -v)
    npm_v=$(npm -v)
    success "Node.js $node_v with npm $npm_v"
    
    # Configure npm for low memory
    info "Configuring npm for ARM..."
    run_silent npm config set jobs 1
}

install_caddy() {
    print_step "Installing Caddy"
    
    if command -v caddy &>/dev/null; then
        local caddy_v
        caddy_v=$(caddy version 2>/dev/null | head -1 || echo "installed")
        success "Caddy already installed: $caddy_v"
    else
        info "Adding Caddy repository..."
        apt-get install -y debian-keyring debian-archive-keyring apt-transport-https >> "$LOG_FILE" 2>&1
        
        curl -1sLf "$CADDY_GPG_URL" | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg 2>/dev/null
        curl -1sLf "$CADDY_REPO_URL" | tee /etc/apt/sources.list.d/caddy-stable.list > /dev/null
        
        apt-get update -qq >> "$LOG_FILE" 2>&1
        run_cmd "Caddy installed" apt-get install -y caddy
    fi
    
    # Verify Caddy
    caddy version >> "$LOG_FILE" 2>&1 || true
}

install_tailscale() {
    print_step "Installing Tailscale"
    
    if $NO_TAILSCALE; then
        warn "Tailscale installation skipped (--no-tailscale)"
        return
    fi
    
    if command -v tailscale &>/dev/null; then
        success "Tailscale already installed"
        
        # Check if connected
        if tailscale status &>/dev/null; then
            local ts_ip
            ts_ip=$(tailscale ip -4 2>/dev/null || echo "connected")
            success "Tailscale connected (IP: $ts_ip)"
        else
            warn "Tailscale not connected - run 'sudo tailscale up' after installation"
        fi
    else
        info "Installing Tailscale..."
        curl -fsSL "$TAILSCALE_INSTALL_URL" | sh >> "$LOG_FILE" 2>&1
        success "Tailscale installed"
        warn "Run 'sudo tailscale up' to connect"
    fi
}

# ============================================================================
# Project Setup
# ============================================================================

clone_or_update_project() {
    print_step "Setting up project files"
    
    # Create directories
    mkdir -p "$PROJECT_DIR" "$DATA_DIR" "$CONFIG_DIR" "$BACKUP_DIR"
    
    # Check if we're running from repo
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    if [[ -f "$script_dir/panel/api/main.py" ]]; then
        info "Installing from local repository..."
        
        # Backup existing if upgrading
        if [[ -d "$PROJECT_DIR/panel" ]] && $UPGRADE_MODE; then
            info "Backing up existing installation..."
            local backup_name="backup-$(date +%Y%m%d-%H%M%S)"
            cp -r "$PROJECT_DIR" "$BACKUP_DIR/$backup_name" 2>/dev/null || true
            success "Backup created: $BACKUP_DIR/$backup_name"
        fi
        
        # Sync files
        rsync -a --delete \
            --exclude 'node_modules' \
            --exclude '__pycache__' \
            --exclude '*.pyc' \
            --exclude '.git' \
            --exclude 'venv' \
            --exclude '.env' \
            --exclude '*.db' \
            --exclude 'dist' \
            "$script_dir/" "$PROJECT_DIR/"
        
        success "Project files synced from local directory"
    elif [[ -d "$PROJECT_DIR/.git" ]]; then
        info "Updating existing git repository..."
        cd "$PROJECT_DIR"
        git pull origin main >> "$LOG_FILE" 2>&1 || git pull >> "$LOG_FILE" 2>&1
        success "Repository updated"
    else
        info "Cloning from GitHub..."
        rm -rf "$PROJECT_DIR"
        git clone "$GITHUB_REPO" "$PROJECT_DIR" >> "$LOG_FILE" 2>&1
        success "Repository cloned"
    fi
    
    # Set ownership
    chown -R "$INSTALL_USER:$INSTALL_GROUP" "$PROJECT_DIR" "$DATA_DIR"
    success "Permissions set for $INSTALL_USER"
}

setup_python_env() {
    print_step "Setting up Python environment"
    
    cd "$PROJECT_DIR"
    
    # Create virtual environment
    if [[ ! -d "venv" ]]; then
        info "Creating virtual environment..."
        sudo -u "$INSTALL_USER" python3 -m venv venv
        success "Virtual environment created"
    else
        success "Virtual environment exists"
    fi
    
    # Upgrade pip
    info "Upgrading pip..."
    sudo -u "$INSTALL_USER" "$PROJECT_DIR/venv/bin/pip" install --upgrade pip >> "$LOG_FILE" 2>&1
    
    # Install requirements
    info "Installing Python dependencies (this may take a few minutes)..."
    sudo -u "$INSTALL_USER" "$PROJECT_DIR/venv/bin/pip" install -r panel/api/requirements.txt >> "$LOG_FILE" 2>&1 &
    spinner $!
    wait $!
    success "Python dependencies installed"
    
    # Also install agent requirements if present
    if [[ -f "agent/requirements.txt" ]]; then
        info "Installing agent dependencies..."
        sudo -u "$INSTALL_USER" "$PROJECT_DIR/venv/bin/pip" install -r agent/requirements.txt >> "$LOG_FILE" 2>&1 || warn "Some agent deps may have failed"
    fi
}

build_frontend() {
    print_step "Building frontend"
    
    cd "$PROJECT_DIR/panel/ui"
    
    # Check if build already exists and we're not upgrading
    if [[ -d "dist" ]] && [[ -f "dist/index.html" ]] && ! $UPGRADE_MODE; then
        success "Frontend already built"
        return
    fi
    
    # Install npm dependencies
    info "Installing npm packages (this may take 5-10 minutes on slow devices)..."
    
    # Configure npm for low memory devices
    export NODE_OPTIONS="--max-old-space-size=512"
    
    sudo -u "$INSTALL_USER" npm install --prefer-offline --no-audit --progress=false >> "$LOG_FILE" 2>&1 &
    spinner $!
    wait $!
    success "npm packages installed"
    
    # Build
    info "Building production bundle..."
    sudo -u "$INSTALL_USER" npm run build >> "$LOG_FILE" 2>&1 &
    spinner $!
    wait $!
    
    if [[ -d "dist" ]] && [[ -f "dist/index.html" ]]; then
        success "Frontend built successfully"
    else
        fail "Frontend build failed - check logs"
        exit 1
    fi
}

# ============================================================================
# Configuration
# ============================================================================

generate_secrets() {
    print_step "Generating secrets"
    
    # JWT secret
    if [[ ! -f "$CONFIG_DIR/jwt_secret" ]]; then
        openssl rand -hex 32 > "$CONFIG_DIR/jwt_secret"
        chmod 600 "$CONFIG_DIR/jwt_secret"
        success "JWT secret generated"
    else
        success "JWT secret exists"
    fi
    
    # Sudoers for systemctl (required for service control from web UI)
    local sudoers_file="/etc/sudoers.d/pi-control"
    if [[ ! -f "$sudoers_file" ]]; then
        echo "$INSTALL_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl" > "$sudoers_file"
        chmod 440 "$sudoers_file"
        success "Sudoers configured for systemctl"
    else
        success "Sudoers already configured"
    fi
}

configure_systemd() {
    print_step "Configuring systemd services"
    
    # Create pi-control service
    cat > /etc/systemd/system/pi-control.service << EOF
[Unit]
Description=Pi Control Panel API
Documentation=https://github.com/BGirginn/rasp_pi_webUI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$INSTALL_USER
Group=$INSTALL_GROUP
WorkingDirectory=$PROJECT_DIR/panel/api

# Environment
Environment=PYTHONPATH=$PROJECT_DIR/panel/api
Environment=DATABASE_PATH=$DATA_DIR/control.db
Environment=TELEMETRY_DB_PATH=$DATA_DIR/telemetry.db
Environment=JWT_SECRET_FILE=$CONFIG_DIR/jwt_secret
Environment=API_DEBUG=false

# Start command
ExecStart=$PROJECT_DIR/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8080

# Restart policy
Restart=always
RestartSec=10
TimeoutStartSec=60
TimeoutStopSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=pi-control

# Security hardening
ProtectSystem=full
ProtectHome=read-only
ReadWritePaths=$DATA_DIR $PROJECT_DIR
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

    success "pi-control.service created"
    
    # Reload systemd
    systemctl daemon-reload
    success "Systemd reloaded"
}

configure_caddy() {
    print_step "Configuring Caddy"
    
    # Copy Caddyfile
    if [[ -f "$PROJECT_DIR/caddy/Caddyfile" ]]; then
        cp "$PROJECT_DIR/caddy/Caddyfile" /etc/caddy/Caddyfile
        success "Caddyfile installed"
    else
        # Create default Caddyfile
        cat > /etc/caddy/Caddyfile << 'EOF'
# Pi Control Panel - Caddy Configuration

:80 {
    # WebSocket for terminal
    handle /api/terminal/ws {
        reverse_proxy 127.0.0.1:8080
    }
    
    # Server-Sent Events
    handle /api/*/stream {
        reverse_proxy 127.0.0.1:8080 {
            flush_interval -1
        }
    }
    
    # API proxy
    handle /api/* {
        reverse_proxy 127.0.0.1:8080
    }
    
    # Static files
    handle {
        root * /opt/pi-control/panel/ui/dist
        try_files {path} /index.html
        file_server
    }
    
    # Security headers
    header {
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        X-XSS-Protection "1; mode=block"
        -Server
    }
    
    # Gzip compression
    encode gzip
    
    log {
        output stdout
        format console
    }
}
EOF
        success "Default Caddyfile created"
    fi
}

# ============================================================================
# Service Start
# ============================================================================

start_services() {
    print_step "Starting services"
    
    # Stop any existing services first
    systemctl stop pi-control 2>/dev/null || true
    
    # Enable and start pi-control
    systemctl enable pi-control >> "$LOG_FILE" 2>&1
    systemctl start pi-control
    success "pi-control service started and enabled"
    
    # Restart Caddy
    systemctl enable caddy >> "$LOG_FILE" 2>&1
    systemctl restart caddy
    success "Caddy service started and enabled"
    
    # Wait for services to start
    info "Waiting for services to initialize..."
    sleep 5
}

# ============================================================================
# Health Check
# ============================================================================

run_health_check() {
    print_step "Running health checks"
    
    local health_ok=true
    
    # Check pi-control service
    if systemctl is-active --quiet pi-control; then
        success "pi-control service is running"
    else
        fail "pi-control service is not running"
        health_ok=false
    fi
    
    # Check Caddy service
    if systemctl is-active --quiet caddy; then
        success "Caddy service is running"
    else
        fail "Caddy service is not running"
        health_ok=false
    fi
    
    # Check API endpoint
    local retries=3
    local api_ok=false
    for ((i=1; i<=retries; i++)); do
        if curl -sf http://localhost:8080/api/health > /dev/null 2>&1; then
            api_ok=true
            break
        fi
        sleep 2
    done
    
    if $api_ok; then
        success "API health check passed"
    else
        fail "API health check failed"
        health_ok=false
    fi
    
    # Check web interface
    if curl -sf http://localhost/ > /dev/null 2>&1; then
        success "Web interface accessible"
    else
        warn "Web interface not responding (may need a moment)"
    fi
    
    # Check Tailscale
    if ! $NO_TAILSCALE && command -v tailscale &>/dev/null; then
        if tailscale status &>/dev/null; then
            local ts_ip
            ts_ip=$(tailscale ip -4 2>/dev/null || echo "unknown")
            success "Tailscale connected: $ts_ip"
        else
            warn "Tailscale not connected"
        fi
    fi
    
    if ! $health_ok; then
        echo ""
        warn "Some health checks failed. Displaying recent logs:"
        echo ""
        journalctl -u pi-control -n 15 --no-pager 2>/dev/null || true
        return 1
    fi
    
    return 0
}

# ============================================================================
# Success Message
# ============================================================================

print_success() {
    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - START_TIME))
    local minutes=$((duration / 60))
    local seconds=$((duration % 60))
    
    # Get IP addresses
    local local_ip
    local_ip=$(hostname -I | awk '{print $1}')
    
    local tailscale_ip=""
    if command -v tailscale &>/dev/null && tailscale status &>/dev/null; then
        tailscale_ip=$(tailscale ip -4 2>/dev/null || echo "")
    fi
    
    echo ""
    echo -e "${GREEN}${BOLD}"
    echo "  ╔═══════════════════════════════════════════════════════════╗"
    echo "  ║                                                           ║"
    echo "  ║   🎉 Installation Complete!                               ║"
    echo "  ║                                                           ║"
    echo "  ╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo -e "  ${CYAN}Installation completed in ${minutes}m ${seconds}s${NC}"
    echo ""
    echo -e "  ${BOLD}📱 Access your Pi Control Panel:${NC}"
    echo -e "     Local:     ${GREEN}http://$local_ip${NC}"
    if [[ -n "$tailscale_ip" ]]; then
        echo -e "     Tailscale: ${GREEN}http://$tailscale_ip${NC}"
    fi
    echo ""
    echo -e "  ${BOLD}🔐 Default Credentials:${NC}"
    echo -e "     Username: ${CYAN}admin${NC}"
    echo -e "     Password: ${CYAN}admin123${NC}"
    echo ""
    echo -e "  ${YELLOW}${BOLD}⚠️  IMPORTANT: Change the default password immediately!${NC}"
    echo ""
    
    if ! command -v tailscale &>/dev/null || ! tailscale status &>/dev/null; then
        echo -e "  ${BOLD}📡 Setup Tailscale for remote access:${NC}"
        echo -e "     ${CYAN}sudo tailscale up${NC}"
        echo ""
    fi
    
    echo -e "  ${BOLD}📝 Useful Commands:${NC}"
    echo -e "     ${CYAN}sudo systemctl status pi-control${NC}  # Service status"
    echo -e "     ${CYAN}sudo journalctl -u pi-control -f${NC}  # Live logs"
    echo -e "     ${CYAN}sudo systemctl restart pi-control${NC} # Restart"
    echo ""
    echo -e "  ${BOLD}📂 Installation Details:${NC}"
    echo -e "     Application: $PROJECT_DIR"
    echo -e "     Data:        $DATA_DIR"
    echo -e "     Config:      $CONFIG_DIR"
    echo -e "     Logs:        $LOG_FILE"
    echo ""
    echo -e "  ${GREEN}🚀 Pi Control Panel will auto-start on every boot!${NC}"
    echo ""
}

# ============================================================================
# Main
# ============================================================================

main() {
    parse_args "$@"
    
    # Initialize log
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "=== Pi Control Panel Installation $(date) ===" > "$LOG_FILE"
    log "Version: $VERSION"
    log "User: $INSTALL_USER"
    log "Options: skip_preflight=$SKIP_PREFLIGHT, no_tailscale=$NO_TAILSCALE, upgrade=$UPGRADE_MODE, verbose=$VERBOSE"
    
    # Print banner
    print_banner
    
    # Pre-flight checks
    if ! $SKIP_PREFLIGHT; then
        run_preflight
    fi
    
    # Installation steps
    update_system
    install_python
    install_nodejs
    install_caddy
    install_tailscale
    clone_or_update_project
    setup_python_env
    build_frontend
    generate_secrets
    configure_systemd
    configure_caddy
    start_services
    
    # Health check
    if run_health_check; then
        print_success
    else
        echo ""
        echo -e "${YELLOW}Installation completed with warnings.${NC}"
        echo -e "${YELLOW}Please check the logs and service status.${NC}"
        echo ""
        exit 1
    fi
}

main "$@"
