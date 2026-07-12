#!/bin/bash
# Pi Control Panel - Native Deployment Script
#
# Usage:
#   ./deploy-native.sh user@host

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
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PI_HOST="${1:-}"
SSH_PASSWORD="${SSH_PASS:-}"

SSH_OPTIONS=(-o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)
SSH_BATCH_OPTIONS=(-o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
INSTALL_FLAGS=(--skip-preflight --no-tailscale)

SSH_CMD=()
SSH_TTY_CMD=()
RSYNC_CMD=()
RSYNC_RSH=()
RSYNC_RSH_STRING=""

print_usage() {
    cat <<'EOF'
Usage: ./deploy-native.sh user@pi-ip-address

Examples:
  ./deploy-native.sh pi@192.168.1.100
  SSH_PASS='secret' ./deploy-native.sh pi@100.x.y.z
EOF
}

print_header() {
    echo -e "${BLUE}==========================================${NC}"
    echo -e "${BLUE}  Pi Control Panel - Remote Deploy${NC}"
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

setup_transport() {
    if [[ -n "$SSH_PASSWORD" ]]; then
        if ! command -v sshpass >/dev/null 2>&1; then
            fail "SSH_PASS is set but sshpass is not installed."
            exit 1
        fi

        SSH_CMD=(sshpass -p "$SSH_PASSWORD" ssh)
        SSH_TTY_CMD=(sshpass -p "$SSH_PASSWORD" ssh -tt)
        RSYNC_CMD=(rsync)
        RSYNC_RSH=(sshpass -p "$SSH_PASSWORD" ssh "${SSH_OPTIONS[@]}")
    else
        SSH_CMD=(ssh)
        SSH_TTY_CMD=(ssh -tt)
        RSYNC_CMD=(rsync)
        RSYNC_RSH=(ssh "${SSH_OPTIONS[@]}")
    fi

    printf -v RSYNC_RSH_STRING '%q ' "${RSYNC_RSH[@]}"
    RSYNC_RSH_STRING="${RSYNC_RSH_STRING% }"
}

run_remote() {
    local command="$1"
    "${SSH_CMD[@]}" "${SSH_OPTIONS[@]}" "$PI_HOST" "$command"
}

run_remote_tty() {
    local command="$1"
    "${SSH_TTY_CMD[@]}" "${SSH_OPTIONS[@]}" "$PI_HOST" "$command"
}

run_remote_batch() {
    local command="$1"
    "${SSH_CMD[@]}" "${SSH_BATCH_OPTIONS[@]}" "$PI_HOST" "$command"
}

run_remote_sudo() {
    local command="$1"
    local quoted_command=""

    printf -v quoted_command '%q' "$command"

    if [[ -n "$SSH_PASSWORD" ]]; then
        local quoted_password=""
        printf -v quoted_password '%q' "$SSH_PASSWORD"
        run_remote "REMOTE_SUDO_PASS=${quoted_password}; printf '%s\n' \"\$REMOTE_SUDO_PASS\" | sudo -S -p '' bash -lc ${quoted_command}"
    else
        run_remote_tty "sudo bash -lc ${quoted_command}"
    fi
}

test_ssh_connection() {
    section "Testing SSH connection..."

    if [[ -n "$SSH_PASSWORD" ]]; then
        run_remote "echo SSH OK" >/dev/null
    else
        if run_remote_batch "echo SSH OK" >/dev/null 2>&1; then
            :
        else
            warn "SSH key auth did not complete in batch mode. Falling back to interactive SSH."
            run_remote_tty "echo SSH OK" >/dev/null
        fi
    fi

    success "SSH connection established."
}

create_remote_directories() {
    section "Preparing remote directories..."

    run_remote_sudo "mkdir -p '$PROJECT_DIR' '$DATA_DIR' '$CONFIG_DIR' && chown -R \"\$SUDO_USER\":\"\$(id -gn \"\$SUDO_USER\")\" '$PROJECT_DIR' '$DATA_DIR'"

    success "Remote directories are ready."
}

sync_project_files() {
    section "Syncing project files..."

    "${RSYNC_CMD[@]}" -avz --progress \
        -e "$RSYNC_RSH_STRING" \
        --exclude 'node_modules' \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude '.git' \
        --exclude 'venv' \
        --exclude '.env' \
        --exclude '*.db' \
        --exclude 'dist' \
        "$SCRIPT_DIR/" "$PI_HOST:$PROJECT_DIR/"

    success "Project files synced to $PI_HOST."
}

run_remote_install() {
    local installer_command=""

    printf -v installer_command "cd '%s' && chmod +x install.sh && ./install.sh %s" "$PROJECT_DIR" "${INSTALL_FLAGS[*]}"

    section "Running remote installer..."
    run_remote_sudo "$installer_command"
    success "Remote installation finished."
}

check_remote_health() {
    section "Checking remote API health..."

    if run_remote "curl -sf http://localhost:8080/api/health >/dev/null"; then
        success "Remote API is healthy."
        return
    fi

    warn "Remote API health check failed. Showing recent pi-control logs."
    run_remote_sudo "journalctl -u pi-control -n 20 --no-pager"
    exit 1
}

print_summary() {
    local remote_ip=""

    remote_ip="$(run_remote "hostname -I | awk '{print \$1}'" 2>/dev/null || true)"
    remote_ip="${remote_ip:-$PI_HOST}"

    echo ""
    echo -e "${GREEN}==========================================${NC}"
    echo -e "${GREEN}  Remote Deployment Complete${NC}"
    echo -e "${GREEN}==========================================${NC}"
    echo ""
    echo -e "${BLUE}Access:${NC} http://$remote_ip"
    echo -e "${BLUE}Useful commands:${NC}"
    echo "  ssh $PI_HOST"
    echo "  sudo systemctl status pi-control"
    echo "  sudo journalctl -u pi-control -f"
    echo "  sudo systemctl restart pi-control"
    echo ""
}

main() {
    if [[ -z "$PI_HOST" ]]; then
        print_usage
        exit 1
    fi

    setup_transport

    print_header
    info "Target host: $PI_HOST"
    info "Install directory: $PROJECT_DIR"
    info "Remote installer flags: ${INSTALL_FLAGS[*]}"
    echo ""

    test_ssh_connection
    create_remote_directories
    sync_project_files
    run_remote_install
    check_remote_health
    print_summary
}

main "$@"
