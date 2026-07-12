#!/bin/bash
# ============================================================================
# Pi Control Panel - Uninstall Script
# ============================================================================
# Cleanly removes Pi Control Panel from the system.
#
# Usage: sudo ./scripts/uninstall.sh [OPTIONS]
#
# Options:
#   --keep-data       Keep databases and configuration
#   --purge           Remove everything including Caddy and Tailscale
#   --yes             Skip confirmation prompts
# ============================================================================

set -euo pipefail

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

# Directories
readonly PROJECT_DIR="/opt/pi-control"
readonly DATA_DIR="/var/lib/pi-control"
readonly CONFIG_DIR="/etc/pi-control"
readonly BACKUP_DIR="/var/backups/pi-control"
readonly LOG_FILE="/var/log/pi-control-uninstall.log"

# Options
KEEP_DATA=false
PURGE=false
YES=false

# ============================================================================
# Utility Functions
# ============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
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

print_header() {
    echo ""
    echo -e "${RED}${BOLD}============================================${NC}"
    echo -e "${RED}${BOLD}  🗑️  Pi Control Panel - Uninstall${NC}"
    echo -e "${RED}${BOLD}============================================${NC}"
    echo ""
}

# ============================================================================
# Argument Parsing
# ============================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --keep-data)
                KEEP_DATA=true
                shift
                ;;
            --purge)
                PURGE=true
                shift
                ;;
            --yes|-y)
                YES=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --keep-data       Keep databases and configuration"
                echo "  --purge           Remove everything including Caddy/Tailscale"
                echo "  --yes, -y         Skip confirmation prompts"
                echo "  -h, --help        Show this help"
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
# Pre-checks
# ============================================================================

check_prerequisites() {
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        fail "This script must be run with sudo"
        exit 1
    fi
    
    # Check if installation exists
    if [[ ! -d "$PROJECT_DIR" ]] && [[ ! -f "/etc/systemd/system/pi-control.service" ]]; then
        warn "Pi Control Panel does not appear to be installed"
        if ! $YES; then
            read -p "Continue anyway? (y/N) " -n 1 -r
            echo
            [[ ! $REPLY =~ ^[Yy]$ ]] && exit 0
        fi
    fi
}

confirm_uninstall() {
    if $YES; then
        return 0
    fi
    
    echo -e "${YELLOW}${BOLD}This will remove Pi Control Panel from your system.${NC}"
    echo ""
    
    if $KEEP_DATA; then
        info "Databases and configuration will be preserved"
    else
        warn "Databases and configuration will be DELETED"
    fi
    
    if $PURGE; then
        warn "Caddy configuration will be reset"
    fi
    
    echo ""
    read -p "Are you sure you want to continue? (y/N) " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Uninstall cancelled."
        exit 0
    fi
}

# ============================================================================
# Uninstall Steps
# ============================================================================

stop_services() {
    echo ""
    echo -e "${CYAN}▶ Stopping services${NC}"
    
    # Stop pi-control
    if systemctl is-active --quiet pi-control 2>/dev/null; then
        systemctl stop pi-control
        success "pi-control service stopped"
    else
        info "pi-control service not running"
    fi
    
    # Disable pi-control
    if systemctl is-enabled --quiet pi-control 2>/dev/null; then
        systemctl disable pi-control
        success "pi-control service disabled"
    fi
    
    # Stop pi-agent if exists
    if systemctl is-active --quiet pi-agent 2>/dev/null; then
        systemctl stop pi-agent
        systemctl disable pi-agent
        success "pi-agent service stopped and disabled"
    fi
}

remove_systemd_services() {
    echo ""
    echo -e "${CYAN}▶ Removing systemd services${NC}"
    
    # Remove service files
    if [[ -f "/etc/systemd/system/pi-control.service" ]]; then
        rm -f /etc/systemd/system/pi-control.service
        success "pi-control.service removed"
    fi
    
    if [[ -f "/etc/systemd/system/pi-agent.service" ]]; then
        rm -f /etc/systemd/system/pi-agent.service
        success "pi-agent.service removed"
    fi
    
    # Reload systemd
    systemctl daemon-reload
    success "Systemd daemon reloaded"
}

remove_application() {
    echo ""
    echo -e "${CYAN}▶ Removing application files${NC}"
    
    if [[ -d "$PROJECT_DIR" ]]; then
        rm -rf "$PROJECT_DIR"
        success "Removed $PROJECT_DIR"
    else
        info "$PROJECT_DIR not found"
    fi
}

remove_data() {
    echo ""
    echo -e "${CYAN}▶ Removing data files${NC}"
    
    if $KEEP_DATA; then
        info "Keeping data at $DATA_DIR"
        info "Keeping config at $CONFIG_DIR"
        return
    fi
    
    # Remove data directory
    if [[ -d "$DATA_DIR" ]]; then
        rm -rf "$DATA_DIR"
        success "Removed $DATA_DIR"
    else
        info "$DATA_DIR not found"
    fi
    
    # Remove config directory
    if [[ -d "$CONFIG_DIR" ]]; then
        rm -rf "$CONFIG_DIR"
        success "Removed $CONFIG_DIR"
    else
        info "$CONFIG_DIR not found"
    fi
    
    # Remove backups
    if [[ -d "$BACKUP_DIR" ]]; then
        rm -rf "$BACKUP_DIR"
        success "Removed $BACKUP_DIR"
    fi
}

reset_caddy() {
    echo ""
    echo -e "${CYAN}▶ Resetting Caddy configuration${NC}"
    
    if $PURGE; then
        # Reset to default Caddyfile
        if [[ -f "/etc/caddy/Caddyfile" ]]; then
            cat > /etc/caddy/Caddyfile << 'EOF'
# Default Caddy configuration
# Pi Control Panel has been uninstalled
:80 {
    respond "Welcome to Caddy!" 200
}
EOF
            systemctl reload caddy 2>/dev/null || true
            success "Caddy configuration reset to default"
        fi
    else
        # Just check if Caddy has our config
        if [[ -f "/etc/caddy/Caddyfile" ]] && grep -q "pi-control" /etc/caddy/Caddyfile 2>/dev/null; then
            warn "Caddy still has Pi Control Panel config"
            info "Edit /etc/caddy/Caddyfile to remove it"
        fi
    fi
}

cleanup_logs() {
    echo ""
    echo -e "${CYAN}▶ Cleaning up logs${NC}"
    
    # Remove install log
    if [[ -f "/var/log/pi-control-install.log" ]]; then
        rm -f /var/log/pi-control-install.log
        success "Removed install log"
    fi
    
    # Remove update log
    if [[ -f "/var/log/pi-control-update.log" ]]; then
        rm -f /var/log/pi-control-update.log
        success "Removed update log"
    fi
    
    # Clear journald logs for pi-control
    journalctl --rotate 2>/dev/null || true
    journalctl --vacuum-time=1s -u pi-control 2>/dev/null || true
    success "Cleared pi-control journal logs"
}

print_summary() {
    echo ""
    echo -e "${GREEN}${BOLD}============================================${NC}"
    echo -e "${GREEN}${BOLD}  ✅ Uninstall Complete${NC}"
    echo -e "${GREEN}${BOLD}============================================${NC}"
    echo ""
    
    echo -e "  ${BOLD}Removed:${NC}"
    echo "    • Pi Control Panel application"
    echo "    • Systemd services"
    
    if ! $KEEP_DATA; then
        echo "    • Databases and configuration"
    fi
    
    echo ""
    
    if $KEEP_DATA; then
        echo -e "  ${BOLD}Preserved:${NC}"
        echo "    • $DATA_DIR (databases)"
        echo "    • $CONFIG_DIR (configuration)"
        echo ""
        info "To remove data: sudo rm -rf $DATA_DIR $CONFIG_DIR"
    fi
    
    echo ""
    echo -e "  ${BOLD}Still installed (use --purge to remove):${NC}"
    echo "    • Caddy web server"
    echo "    • Tailscale VPN"
    echo "    • Node.js"
    echo ""
    
    success "Thank you for using Pi Control Panel!"
    echo ""
}

# ============================================================================
# Main
# ============================================================================

main() {
    parse_args "$@"
    
    # Initialize log
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "=== Pi Control Panel Uninstall $(date) ===" >> "$LOG_FILE"
    
    print_header
    check_prerequisites
    confirm_uninstall
    
    stop_services
    remove_systemd_services
    remove_application
    remove_data
    reset_caddy
    cleanup_logs
    
    print_summary
}

main "$@"
