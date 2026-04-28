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
readonly SERVICE_ENV_FILE="$CONFIG_DIR/pi-control.env"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

readonly PROJECT_RSYNC_EXCLUDES=(
    --exclude 'node_modules'
    --exclude '__pycache__'
    --exclude '.mypy_cache'
    --exclude '.pytest_cache'
    --exclude '*.pyc'
    --exclude '.DS_Store'
    --exclude '.git'
    --exclude '.venv'
    --exclude 'venv'
    --exclude '.env'
    --exclude '*.db'
    --exclude '*.db-shm'
    --exclude '*.db-wal'
    --exclude 'dist'
)

SKIP_PREFLIGHT=false
UPGRADE_MODE=false
VERBOSE=false
INSTALL_PROFILE="full"
WEB_PORT="${WEB_PORT:-8088}"

INSTALL_USER="${SUDO_USER:-}"
INSTALL_GROUP=""
DEFAULT_ADMIN_PASSWORD_VALUE="${DEFAULT_ADMIN_PASSWORD:-admin}"

print_usage() {
    cat <<'EOF'
Usage: sudo ./install.sh [OPTIONS]

Options:
  --profile MODE      Installation profile: full or local (default: full)
  --web-port PORT     Web UI port exposed by Caddy (default: 8088)
  --skip-preflight   Skip scripts/pre-flight-check.sh
  --no-tailscale     Alias for --profile local
  --upgrade          Run scripts/update.sh instead of a full install
  --verbose          Show full apt/pip/npm output
  -h, --help         Show this help text

Profiles:
  full               Install the full system and include Tailscale setup
  local              Install the same system for LAN access only, without Tailscale

Environment:
  DEFAULT_ADMIN_PASSWORD    Initial admin password (default: admin)
  WEB_PORT                  Default value for --web-port
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

set_install_profile() {
    local profile="$1"

    case "$profile" in
        full)
            INSTALL_PROFILE="full"
            ;;
        local)
            INSTALL_PROFILE="local"
            ;;
        *)
            fail "Invalid profile: $profile"
            echo "  Valid profiles: full, local"
            exit 1
            ;;
    esac
}

set_web_port() {
    local port="$1"

    if [[ ! "$port" =~ ^[0-9]+$ ]] || [[ "$port" -lt 1 ]] || [[ "$port" -gt 65535 ]]; then
        fail "Invalid web port: $port"
        echo "  Use a port number between 1 and 65535."
        exit 1
    fi

    WEB_PORT="$port"
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --profile)
                if [[ $# -lt 2 ]]; then
                    fail "--profile requires a value: full or local"
                    exit 1
                fi
                set_install_profile "$2"
                shift
                ;;
            --profile=*)
                set_install_profile "${1#*=}"
                ;;
            --web-port)
                if [[ $# -lt 2 ]]; then
                    fail "--web-port requires a numeric value"
                    exit 1
                fi
                set_web_port "$2"
                shift
                ;;
            --web-port=*)
                set_web_port "${1#*=}"
                ;;
            --skip-preflight)
                SKIP_PREFLIGHT=true
                ;;
            --no-tailscale)
                set_install_profile "local"
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

    if bash "$preflight_script" --profile "$INSTALL_PROFILE" --web-port "$WEB_PORT"; then
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
        curl rsync sqlite3 gnupg ca-certificates \
        debian-keyring debian-archive-keyring apt-transport-https

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

    if [[ "$INSTALL_PROFILE" == "local" ]]; then
        info "Local profile selected; skipping remote access setup."
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

    mkdir -p "$PROJECT_DIR" "$DATA_DIR" "$CONFIG_DIR"
    chown -R "$INSTALL_USER:$INSTALL_GROUP" "$PROJECT_DIR" "$DATA_DIR"
    chmod 755 "$PROJECT_DIR"

    success "Application directories are ready."
}

copy_project_files() {
    section "Copying project files..."

    run_cmd rsync -a "${PROJECT_RSYNC_EXCLUDES[@]}" "$SCRIPT_DIR/" "$PROJECT_DIR/"

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

    success "Python virtual environment is ready."
}

build_ui() {
    section "Building the web UI..."

    cd "$PROJECT_DIR/panel/ui"
    if [[ "$VERBOSE" == true ]]; then
        sudo -u "$INSTALL_USER" npm install --no-audit --no-fund
        sudo -u "$INSTALL_USER" npm run build
    else
        sudo -u "$INSTALL_USER" npm install --no-audit --no-fund --silent >/dev/null 2>&1
        sudo -u "$INSTALL_USER" npm run build >/dev/null 2>&1
    fi

    success "Frontend build completed."
}

write_service_env_file() {
    local escaped_password=""

    if [[ -n "$DEFAULT_ADMIN_PASSWORD_VALUE" ]]; then
        escaped_password="${DEFAULT_ADMIN_PASSWORD_VALUE//\\/\\\\}"
        escaped_password="${escaped_password//\"/\\\"}"
        printf 'DEFAULT_ADMIN_PASSWORD="%s"\n' "$escaped_password" > "$SERVICE_ENV_FILE"
        chmod 600 "$SERVICE_ENV_FILE"
        info "Using DEFAULT_ADMIN_PASSWORD for the initial admin seed."
    else
        rm -f "$SERVICE_ENV_FILE"
    fi
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
WorkingDirectory=/opt/pi-control/panel/api
Environment=PYTHONPATH=/opt/pi-control/panel/api
Environment=DATABASE_PATH=/var/lib/pi-control/control.db
Environment=TELEMETRY_DB_PATH=/var/lib/pi-control/telemetry.db
Environment=AGENT_SOCKET=/run/pi-agent/agent.sock
Environment=JWT_SECRET_FILE=/etc/pi-control/jwt_secret
Environment=API_DEBUG=false
EnvironmentFile=-$SERVICE_ENV_FILE
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

    success "Systemd service created."
}

configure_caddy() {
    section "Configuring Caddy..."

    sed "0,/^:[0-9][0-9]* {/s//:${WEB_PORT} {/" "$PROJECT_DIR/caddy/Caddyfile" > /etc/caddy/Caddyfile

    success "Caddy configuration updated."
}

start_services() {
    section "Starting services..."

    run_cmd systemctl daemon-reload
    run_cmd systemctl enable pi-control
    run_cmd systemctl restart pi-control
    run_cmd systemctl enable caddy
    run_cmd systemctl restart caddy

    success "Services started and enabled."
}

health_check() {
    section "Running health check..."

    for _ in {1..30}; do
        if curl -sf http://localhost:8080/api/health >/dev/null; then
            success "API health check passed."
            return 0
        fi
        sleep 2
    done

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
    echo -e "${BLUE}Profile:${NC} $INSTALL_PROFILE"
    echo ""
    echo -e "${BLUE}Connection:${NC}"
    echo "  Open this link from a device on the same network:"
    echo "  http://$pi_ip:$WEB_PORT"
    echo ""
    echo -e "${BLUE}Initial admin login:${NC}"
    echo "  This is used only when the database does not already contain an admin user."
    echo "  Username: admin"
    echo "  Password: $DEFAULT_ADMIN_PASSWORD_VALUE"
    echo ""
    echo "  You can sign in with the username and password above."
    echo ""
    echo -e "${YELLOW}Change the admin password after the first login.${NC}"
    if [[ "$INSTALL_PROFILE" == "full" ]]; then
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
    info "Install profile: $INSTALL_PROFILE"
    info "Web port: $WEB_PORT"
    info "Install directory: $PROJECT_DIR"
    echo ""

    run_preflight_check
    install_dependencies
    install_tailscale
    create_directories
    copy_project_files
    setup_python
    build_ui
    generate_secrets
    create_systemd_service
    configure_caddy
    start_services

    if health_check; then
        print_summary
    else
        fail "Installation completed but the health check failed."
        [[ "$VERBOSE" == true ]] || echo "  Re-run with --verbose for full command output."
        exit 1
    fi
}

main "$@"
