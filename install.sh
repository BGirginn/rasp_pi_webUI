#!/bin/bash
# Pi Control Panel - Installation Script
#
# Usage:
#   git clone https://github.com/BGirginn/rasp_pi_webUI.git
#   cd rasp_pi_webUI
#   chmod +x install.sh
#   sudo ./install.sh

set -euo pipefail

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m'

readonly PROJECT_DIR="/opt/pi-control"
readonly DATA_DIR="/var/lib/pi-control"
readonly CONFIG_DIR="/etc/pi-control"
readonly RELEASES_DIR="$PROJECT_DIR/releases"
readonly CURRENT_LINK="$PROJECT_DIR/current"
readonly SERVICE_ENV_FILE="$CONFIG_DIR/pi-control.env"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SKIP_PREFLIGHT=false
SKIP_TAILSCALE=false
UPGRADE_MODE=false
VERBOSE=false

INSTALL_USER="${SUDO_USER:-}"
INSTALL_GROUP=""
DEFAULT_ADMIN_PASSWORD_VALUE="${DEFAULT_ADMIN_PASSWORD:-}"

print_usage() {
    cat <<'EOF'
Usage: sudo ./install.sh [OPTIONS]

Options:
  --skip-preflight   Skip scripts/pre-flight-check.sh
  --no-tailscale     Skip Tailscale installation and next-step prompts
  --upgrade          Run scripts/update.sh instead of a full install
  --verbose          Show full apt/pip/npm output
  -h, --help         Show this help text
EOF
}

print_header() {
    echo -e "${BLUE}==========================================${NC}"
    echo -e "${BLUE}  Pi Control Panel - Installer${NC}"
    echo -e "${BLUE}==========================================${NC}"
    echo ""
}

section() {
    echo -e "${CYAN}$1${NC}"
}

info() {
    echo -e "  ${BLUE}->${NC} $1"
}

success() {
    echo -e "  ${GREEN}OK${NC} $1"
}

warn() {
    echo -e "  ${YELLOW}WARN${NC} $1"
}

fail() {
    echo -e "  ${RED}ERR${NC} $1"
}

run_cmd() {
    if [[ "$VERBOSE" == true ]]; then
        "$@"
    else
        "$@" >/dev/null 2>&1
    fi
}

run_shell() {
    local command="$1"

    if [[ "$VERBOSE" == true ]]; then
        bash -euo pipefail -c "$command"
    else
        bash -euo pipefail -c "$command" >/dev/null 2>&1
    fi
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --skip-preflight)
                SKIP_PREFLIGHT=true
                ;;
            --no-tailscale)
                SKIP_TAILSCALE=true
                ;;
            --upgrade)
                UPGRADE_MODE=true
                ;;
            --verbose)
                VERBOSE=true
                ;;
            -h|--help)
                print_usage
                exit 0
                ;;
            *)
                fail "Unknown option: $1"
                echo ""
                print_usage
                exit 1
                ;;
        esac
        shift
    done
}

ensure_sudo_context() {
    if [[ $EUID -ne 0 ]]; then
        fail "This script must be run with sudo."
        echo "  Usage: sudo ./install.sh"
        exit 1
    fi

    if [[ -z "${SUDO_USER:-}" ]]; then
        fail "Please run this script with sudo, not as root directly."
        echo "  Usage: sudo ./install.sh"
        exit 1
    fi

    INSTALL_USER="$SUDO_USER"
    INSTALL_GROUP="$(id -gn "$INSTALL_USER")"
}

run_preflight_check() {
    local preflight_script="$SCRIPT_DIR/scripts/pre-flight-check.sh"
    local status=0

    if [[ "$SKIP_PREFLIGHT" == true ]]; then
        warn "Skipping pre-flight checks."
        return
    fi

    section "Running pre-flight checks..."

    if [[ ! -f "$preflight_script" ]]; then
        fail "Missing pre-flight script: $preflight_script"
        exit 1
    fi

    if bash "$preflight_script"; then
        success "Pre-flight checks passed."
        return
    fi

    status=$?
    case "$status" in
        1)
            fail "Pre-flight checks failed. Resolve the reported issues first."
            exit 1
            ;;
        2)
            warn "Pre-flight checks completed with warnings. Continuing installation."
            ;;
        *)
            fail "Pre-flight checks exited unexpectedly (status $status)."
            exit "$status"
            ;;
    esac
}

run_upgrade() {
    local update_script="$SCRIPT_DIR/scripts/update.sh"
    local update_args=()

    if [[ ! -f "$update_script" ]]; then
        fail "Missing update script: $update_script"
        exit 1
    fi

    if [[ "$VERBOSE" == true ]]; then
        update_args+=(--verbose)
    fi

    print_header
    section "Delegating to update flow..."
    info "Running scripts/update.sh ${update_args[*]:-}"
    exec bash "$update_script" "${update_args[@]}"
}

install_dependencies() {
    local node_major=0

    section "Installing system dependencies..."
    run_cmd apt-get update -qq
    info "Installing Python, curl, rsync, SQLite and base packages"
    run_cmd apt-get install -y \
        python3 python3-pip python3-venv python3-dev \
        curl rsync sqlite3 gnupg ca-certificates unattended-upgrades mosquitto mosquitto-clients \
        debian-keyring debian-archive-keyring apt-transport-https \
        util-linux dosfstools exfatprogs e2fsprogs udisks2

    info "Checking Node.js runtime"
    if command -v node >/dev/null 2>&1; then
        node_major="$(node -v | sed 's/^v//' | cut -d. -f1)"
    fi
    if [[ "$node_major" -lt 18 ]]; then
        info "Installing Node.js 20"
        run_shell "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -"
        run_cmd apt-get install -y nodejs
    else
        success "Node.js $(node -v) already satisfies the minimum version"
    fi

    info "Checking Caddy"
    if ! command -v caddy >/dev/null 2>&1; then
        info "Installing Caddy"
        run_shell "curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg"
        run_shell "curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null"
        run_cmd apt-get update -qq
        run_cmd apt-get install -y caddy
    else
        success "Caddy is already installed"
    fi

    success "System dependencies are ready."
}

install_tailscale() {
    local ts_ip=""

    if [[ "$SKIP_TAILSCALE" == true ]]; then
        warn "Skipping Tailscale installation."
        return
    fi

    section "Installing Tailscale..."

    if command -v tailscale >/dev/null 2>&1; then
        success "Tailscale is already installed."
    elif [[ -f /etc/debian_version ]]; then
        info "Installing Tailscale via the official Debian installer"
        if run_shell "curl -fsSL https://tailscale.com/install.sh | sh"; then
            success "Tailscale packages installed."
        else
            warn "Tailscale installation failed. Continue the setup and install it manually later."
            return
        fi
    else
        warn "Automatic Tailscale installation is only supported on Debian/Raspberry Pi OS."
        return
    fi

    if tailscale status >/dev/null 2>&1; then
        ts_ip="$(tailscale ip -4 2>/dev/null | head -n 1 || true)"
        if [[ -n "$ts_ip" ]]; then
            success "Tailscale is connected at $ts_ip"
        else
            success "Tailscale is connected."
        fi
    else
        info "Run 'sudo tailscale up' after installation to connect this Pi."
    fi
}

create_directories() {
    section "Creating application directories..."

    mkdir -p "$PROJECT_DIR" "$DATA_DIR" "$CONFIG_DIR" "$RELEASES_DIR" "$PROJECT_DIR/backups"
    chown -R "$INSTALL_USER:$INSTALL_GROUP" "$PROJECT_DIR" "$DATA_DIR"
    chmod 755 "$PROJECT_DIR"

    success "Application directories are ready."
}

copy_project_files() {
    section "Copying project files..."

    run_cmd rsync -a \
        --exclude 'node_modules' \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude '.git' \
        --exclude 'venv' \
        --exclude '.env' \
        --exclude '*.db' \
        --exclude 'dist' \
        "$SCRIPT_DIR/" "$PROJECT_DIR/"

    chown -R "$INSTALL_USER:$INSTALL_GROUP" "$PROJECT_DIR"

    # Caddy runs as its own user and must be able to traverse the app tree
    # to serve the built UI from /opt/pi-control/panel/ui/dist.
    find "$PROJECT_DIR/panel" -type d -exec chmod 755 {} \;
    find "$PROJECT_DIR/panel/ui/dist" -type f -exec chmod 644 {} \; 2>/dev/null || true

    success "Project files copied to $PROJECT_DIR."
}

setup_python() {
    section "Setting up Python environment..."

    cd "$PROJECT_DIR"
    run_cmd sudo -u "$INSTALL_USER" python3 -m venv venv
    run_cmd sudo -u "$INSTALL_USER" "$PROJECT_DIR/venv/bin/pip" install --upgrade pip
    run_cmd sudo -u "$INSTALL_USER" "$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/panel/api/requirements.txt"
    run_cmd sudo -u "$INSTALL_USER" "$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/agent/requirements.txt"

    success "Python virtual environment is ready."
}

build_ui() {
    section "Building the web UI..."

    cd "$PROJECT_DIR/panel/ui"
    if [[ "$VERBOSE" == true ]]; then
        sudo -u "$INSTALL_USER" npm install
        sudo -u "$INSTALL_USER" npm run build
    else
        sudo -u "$INSTALL_USER" npm install --silent >/dev/null 2>&1
        sudo -u "$INSTALL_USER" npm run build >/dev/null 2>&1
    fi

    success "Frontend build completed."
}

prepare_release_layout() {
    local release_id release_dir temporary_link
    release_id="install-$(date +%Y%m%d-%H%M%S)"
    release_dir="$RELEASES_DIR/$release_id"
    temporary_link="$PROJECT_DIR/.current-$release_id"

    section "Preparing atomic release layout..."
    mkdir -p "$release_dir"
    run_cmd rsync -a \
        --exclude '.git' \
        --exclude 'venv' \
        --exclude 'node_modules' \
        --exclude 'backups' \
        --exclude 'releases' \
        --exclude 'current' \
        "$PROJECT_DIR/" "$release_dir/"
    ln -s ../../venv "$release_dir/venv"
    chown -R "$INSTALL_USER:$INSTALL_GROUP" "$release_dir"
    ln -s "$release_dir" "$temporary_link"
    mv -Tf "$temporary_link" "$CURRENT_LINK"
    success "Release activated at $release_dir"
}

write_service_env_file() {
    local escaped_password

    if [[ -z "$DEFAULT_ADMIN_PASSWORD_VALUE" ]]; then
        DEFAULT_ADMIN_PASSWORD_VALUE="$(openssl rand -hex 18)"
        info "Generated a random initial admin password."
    else
        info "Using DEFAULT_ADMIN_PASSWORD for the initial admin seed."
    fi
    escaped_password="${DEFAULT_ADMIN_PASSWORD_VALUE//\\/\\\\}"
    escaped_password="${escaped_password//\"/\\\"}"
    printf 'DEFAULT_ADMIN_PASSWORD="%s"\n' "$escaped_password" > "$SERVICE_ENV_FILE"
    chmod 600 "$SERVICE_ENV_FILE"
}

generate_secrets() {
    section "Preparing runtime secrets..."

    if [[ ! -f "$CONFIG_DIR/jwt_secret" ]]; then
        openssl rand -hex 32 > "$CONFIG_DIR/jwt_secret"
        chmod 600 "$CONFIG_DIR/jwt_secret"
        info "Generated JWT secret."
    else
        info "JWT secret already exists."
    fi

    write_service_env_file
    success "Runtime secrets are configured."
}

create_systemd_service() {
    section "Creating systemd service..."

    cat > /etc/systemd/system/pi-control.service <<EOF
[Unit]
Description=Pi Control Panel API
Documentation=https://github.com/BGirginn/rasp_pi_webUI
After=network.target

[Service]
Type=simple
User=$INSTALL_USER
Group=$INSTALL_GROUP
WorkingDirectory=/opt/pi-control/current/panel/api
Environment=PYTHONPATH=/opt/pi-control/current/panel/api
Environment=DATABASE_PATH=/var/lib/pi-control/control.db
Environment=TELEMETRY_DB_PATH=/var/lib/pi-control/telemetry.db
Environment=AGENT_SOCKET=/run/pi-agent/agent.sock
Environment=JWT_SECRET_FILE=/etc/pi-control/jwt_secret
Environment=API_DEBUG=false
EnvironmentFile=-$SERVICE_ENV_FILE
ExecStart=/opt/pi-control/current/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8080
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

    success "Systemd service created."

    cat > /etc/systemd/system/pi-agent.service <<EOF
[Unit]
Description=Pi Control Panel Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/pi-control/current/agent
ExecStart=/opt/pi-control/current/venv/bin/python3 /opt/pi-control/current/agent/pi-agent.py --config /opt/pi-control/current/agent/config.yaml
Restart=on-failure
RestartSec=5
TimeoutStopSec=15
KillMode=mixed
RuntimeDirectory=pi-agent
RuntimeDirectoryMode=0755
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-$SERVICE_ENV_FILE
CapabilityBoundingSet=CAP_NET_ADMIN CAP_SYS_ADMIN CAP_SYS_PTRACE CAP_DAC_OVERRIDE CAP_CHOWN CAP_FOWNER
AmbientCapabilities=CAP_NET_ADMIN CAP_SYS_ADMIN CAP_SYS_PTRACE CAP_DAC_OVERRIDE CAP_CHOWN CAP_FOWNER
StandardOutput=journal
StandardError=journal
SyslogIdentifier=pi-agent

[Install]
WantedBy=multi-user.target
EOF
    success "Agent systemd service created."
}

configure_caddy() {
    section "Configuring Caddy..."

    cp "$CURRENT_LINK/caddy/Caddyfile" /etc/caddy/Caddyfile

    local hostname_value lan_addresses tailscale_dns tailscale_ip
    hostname_value="$(hostname -s 2>/dev/null || echo raspberrypi)"
    lan_addresses="$(ip -4 -o addr show scope global 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | grep -Ev '^(100\.|169\.254\.|172\.1[7-9]\.|172\.2[0-9]\.|172\.3[0-1]\.)' || true)"
    tailscale_dns=""
    tailscale_ip=""
    if command -v tailscale >/dev/null 2>&1; then
        tailscale_dns="$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("Self",{}).get("DNSName","").rstrip("."))' 2>/dev/null || true)"
        tailscale_ip="$(tailscale ip -4 2>/dev/null | head -n 1 || true)"
    fi

    {
        printf 'https://%s.local' "$hostname_value"
        while IFS= read -r address; do
            [[ -n "$address" ]] && printf ', https://%s' "$address"
        done <<< "$lan_addresses"
        printf ' {\n\ttls internal\n\timport panel_app\n}\n'
        if [[ -n "$tailscale_dns" ]]; then
            printf '\nhttps://%s {\n\ttls internal\n\timport panel_app\n}\n' "$tailscale_dns"
        fi
        if [[ -n "$tailscale_ip" ]]; then
            printf '\nhttp://%s {\n\timport panel_app\n}\n' "$tailscale_ip"
        fi
    } > /etc/caddy/pi-control-sites.caddy

    run_cmd caddy validate --config /etc/caddy/Caddyfile

    success "Caddy configuration updated."
}

start_services() {
    section "Starting services..."

    run_cmd systemctl daemon-reload
    run_cmd systemctl enable pi-control
    run_cmd systemctl enable pi-agent
    run_cmd systemctl restart pi-agent
    run_cmd systemctl restart pi-control
    run_cmd systemctl enable caddy
    run_cmd systemctl restart caddy

    success "Services started and enabled."
}

health_check() {
    section "Running health check..."

    sleep 5
    if curl -sf http://localhost:8080/api/health >/dev/null; then
        success "API health check passed."
        return 0
    fi

    fail "API is not responding on http://localhost:8080/api/health"
    echo "  Recent pi-control logs:"
    journalctl -u pi-control -n 20 --no-pager
    return 1
}

print_summary() {
    local pi_ip="localhost"

    if hostname -I >/dev/null 2>&1; then
        pi_ip="$(hostname -I | awk '{print $1}')"
    fi

    echo ""
    echo -e "${GREEN}==========================================${NC}"
    echo -e "${GREEN}  Installation Complete${NC}"
    echo -e "${GREEN}==========================================${NC}"
    echo ""
    echo -e "${BLUE}Access:${NC} https://$pi_ip"
    echo ""
    echo -e "${BLUE}Initial admin login:${NC}"
    echo "  This is used only when the database does not already contain an admin user."
    echo "  Username: admin"
    echo "  Password: $DEFAULT_ADMIN_PASSWORD_VALUE"
    echo ""
    echo -e "${YELLOW}Change the admin password after the first login.${NC}"
    if [[ "$SKIP_TAILSCALE" == false ]]; then
        echo -e "${BLUE}Tailscale:${NC}"
        echo "  If the device is not connected yet, run: sudo tailscale up"
        echo ""
    fi
    echo -e "${BLUE}Useful commands:${NC}"
    echo "  sudo systemctl status pi-control"
    echo "  sudo journalctl -u pi-control -f"
    echo "  sudo systemctl restart pi-control"
    echo ""
}

main() {
    parse_args "$@"
    ensure_sudo_context

    if [[ "$UPGRADE_MODE" == true ]]; then
        run_upgrade
    fi

    print_header
    info "Installation user: $INSTALL_USER"
    info "Install directory: $PROJECT_DIR"
    echo ""

    run_preflight_check
    install_dependencies
    install_tailscale
    create_directories
    copy_project_files
    setup_python
    build_ui
    prepare_release_layout
    generate_secrets
    create_systemd_service
    configure_caddy
    start_services

    if health_check; then
        print_summary
        rm -f "$SERVICE_ENV_FILE"
    else
        fail "Installation completed but the health check failed."
        [[ "$VERBOSE" == true ]] || echo "  Re-run with --verbose for full command output."
        exit 1
    fi
}

main "$@"
