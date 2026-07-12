#!/bin/bash
# ============================================================================
# Pi Control Panel - Update Script
# ============================================================================
# Updates an existing Pi Control Panel installation with zero-downtime.
# Creates backup before updating.
#
# Usage: sudo ./scripts/update.sh [OPTIONS]
#
# Options:
#   --backup-only     Only create backup without updating
#   --no-backup       Skip backup (not recommended)
#   --force           Force update even if already up to date
#   -v, --verbose     Verbose output
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
readonly LOG_FILE="/var/log/pi-control-update.log"

# Options
BACKUP_ONLY=false
NO_BACKUP=false
FORCE=false
VERBOSE=false

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
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo -e "${BLUE}${BOLD}  🔄 Pi Control Panel - Update${NC}"
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo ""
}

# ============================================================================
# Argument Parsing
# ============================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --backup-only)
                BACKUP_ONLY=true
                shift
                ;;
            --no-backup)
                NO_BACKUP=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --backup-only     Only create backup without updating"
                echo "  --no-backup       Skip backup (not recommended)"
                echo "  --force           Force update even if already up to date"
                echo "  -v, --verbose     Verbose output"
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
    echo -e "${CYAN}▶ Checking prerequisites${NC}"
    
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        fail "This script must be run with sudo"
        exit 1
    fi
    success "Running as root"
    
    # Check if installation exists
    if [[ ! -d "$PROJECT_DIR" ]]; then
        fail "Pi Control Panel not installed at $PROJECT_DIR"
        echo ""
        echo "To install, run: sudo ./install.sh"
        exit 1
    fi
    success "Installation found at $PROJECT_DIR"
    
    # Check if it's a git repository
    if [[ ! -d "$PROJECT_DIR/.git" ]]; then
        warn "Not a git repository - will reinstall from source"
    else
        success "Git repository detected"
    fi
}

# ============================================================================
# Backup
# ============================================================================

create_backup() {
    echo ""
    echo -e "${CYAN}▶ Creating backup${NC}"
    
    local timestamp
    timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_path="$BACKUP_DIR/$timestamp"
    
    mkdir -p "$backup_path"
    
    # Backup databases
    if [[ -f "$DATA_DIR/control.db" ]]; then
        cp "$DATA_DIR/control.db" "$backup_path/"
        success "Database backed up"
    fi
    
    if [[ -f "$DATA_DIR/telemetry.db" ]]; then
        cp "$DATA_DIR/telemetry.db" "$backup_path/"
        success "Telemetry database backed up"
    fi
    
    # Backup config
    if [[ -d "$CONFIG_DIR" ]]; then
        cp -r "$CONFIG_DIR" "$backup_path/config"
        success "Configuration backed up"
    fi
    
    # Store current git hash
    if [[ -d "$PROJECT_DIR/.git" ]]; then
        cd "$PROJECT_DIR"
        git rev-parse HEAD > "$backup_path/git-hash.txt" 2>/dev/null || true
        success "Git commit hash saved"
    fi
    
    # Cleanup old backups (keep last 5)
    local backup_count
    backup_count=$(find "$BACKUP_DIR" -maxdepth 1 -type d -name "20*" | wc -l)
    if [[ $backup_count -gt 5 ]]; then
        info "Cleaning up old backups..."
        find "$BACKUP_DIR" -maxdepth 1 -type d -name "20*" | sort | head -n -5 | xargs rm -rf
        success "Old backups removed"
    fi
    
    success "Backup created: $backup_path"
    echo "$backup_path"
}

# ============================================================================
# Update Process
# ============================================================================

check_for_updates() {
    echo ""
    echo -e "${CYAN}▶ Checking for updates${NC}"
    
    if [[ ! -d "$PROJECT_DIR/.git" ]]; then
        warn "Not a git repository, will pull fresh"
        return 0
    fi
    
    cd "$PROJECT_DIR"
    
    # Fetch latest
    git fetch origin >> "$LOG_FILE" 2>&1
    
    local local_hash remote_hash
    local_hash=$(git rev-parse HEAD)
    remote_hash=$(git rev-parse origin/main 2>/dev/null || git rev-parse origin/master 2>/dev/null || echo "")
    
    if [[ -z "$remote_hash" ]]; then
        warn "Could not determine remote hash"
        return 0
    fi
    
    if [[ "$local_hash" == "$remote_hash" ]] && ! $FORCE; then
        success "Already up to date"
        echo ""
        info "Current version: ${local_hash:0:8}"
        info "Use --force to update anyway"
        return 1
    fi
    
    info "Current: ${local_hash:0:8}"
    info "Latest:  ${remote_hash:0:8}"
    success "Updates available"
    return 0
}

stop_services() {
    echo ""
    echo -e "${CYAN}▶ Stopping services${NC}"
    
    if systemctl is-active --quiet pi-control; then
        systemctl stop pi-control
        success "pi-control service stopped"
    else
        info "pi-control service not running"
    fi
}

update_code() {
    echo ""
    echo -e "${CYAN}▶ Updating code${NC}"
    
    cd "$PROJECT_DIR"
    
    if [[ -d ".git" ]]; then
        # Git pull
        git reset --hard >> "$LOG_FILE" 2>&1
        git pull origin main >> "$LOG_FILE" 2>&1 || git pull >> "$LOG_FILE" 2>&1
        success "Code updated from git"
    else
        # Re-clone (shouldn't normally happen)
        local temp_dir
        temp_dir=$(mktemp -d)
        git clone https://github.com/BGirginn/rasp_pi_webUI.git "$temp_dir" >> "$LOG_FILE" 2>&1
        rsync -a --delete \
            --exclude 'node_modules' \
            --exclude 'venv' \
            --exclude '.env' \
            "$temp_dir/" "$PROJECT_DIR/"
        rm -rf "$temp_dir"
        success "Code reinstalled"
    fi
}

update_python_deps() {
    echo ""
    echo -e "${CYAN}▶ Updating Python dependencies${NC}"
    
    cd "$PROJECT_DIR"
    
    # Activate and upgrade
    "$PROJECT_DIR/venv/bin/pip" install --upgrade pip >> "$LOG_FILE" 2>&1
    "$PROJECT_DIR/venv/bin/pip" install -r panel/api/requirements.txt >> "$LOG_FILE" 2>&1
    
    success "Python dependencies updated"
}

rebuild_frontend() {
    echo ""
    echo -e "${CYAN}▶ Rebuilding frontend${NC}"
    
    cd "$PROJECT_DIR/panel/ui"
    
    # Detect user
    local install_user="${SUDO_USER:-pi}"
    
    # Install and build
    export NODE_OPTIONS="--max-old-space-size=512"
    
    info "Installing npm packages..."
    sudo -u "$install_user" npm install --prefer-offline --no-audit >> "$LOG_FILE" 2>&1
    success "npm packages updated"
    
    info "Building production bundle..."
    sudo -u "$install_user" npm run build >> "$LOG_FILE" 2>&1
    success "Frontend rebuilt"
}

start_services() {
    echo ""
    echo -e "${CYAN}▶ Starting services${NC}"
    
    systemctl daemon-reload
    systemctl start pi-control
    success "pi-control service started"
    
    # Reload Caddy config
    systemctl reload caddy 2>/dev/null || systemctl restart caddy
    success "Caddy reloaded"
}

# ============================================================================
# Health Check
# ============================================================================

verify_update() {
    echo ""
    echo -e "${CYAN}▶ Verifying update${NC}"
    
    sleep 3
    
    local health_ok=true
    
    # Check service
    if systemctl is-active --quiet pi-control; then
        success "pi-control service is running"
    else
        fail "pi-control service failed to start"
        health_ok=false
    fi
    
    # Check API
    local retries=3
    for ((i=1; i<=retries; i++)); do
        if curl -sf http://localhost:8080/api/health > /dev/null; then
            success "API health check passed"
            break
        fi
        if [[ $i -eq $retries ]]; then
            fail "API health check failed"
            health_ok=false
        fi
        sleep 2
    done
    
    if ! $health_ok; then
        echo ""
        warn "Update completed but health checks failed"
        echo "Check logs: sudo journalctl -u pi-control -n 30"
        return 1
    fi
    
    return 0
}

# ============================================================================
# Rollback
# ============================================================================

rollback() {
    local backup_path="$1"
    
    echo ""
    echo -e "${YELLOW}▶ Rolling back to backup${NC}"
    
    # Restore databases
    if [[ -f "$backup_path/control.db" ]]; then
        cp "$backup_path/control.db" "$DATA_DIR/"
        success "Database restored"
    fi
    
    if [[ -f "$backup_path/telemetry.db" ]]; then
        cp "$backup_path/telemetry.db" "$DATA_DIR/"
        success "Telemetry database restored"
    fi
    
    # Restore git state
    if [[ -f "$backup_path/git-hash.txt" ]]; then
        local old_hash
        old_hash=$(cat "$backup_path/git-hash.txt")
        cd "$PROJECT_DIR"
        git reset --hard "$old_hash" >> "$LOG_FILE" 2>&1
        success "Code reverted to $old_hash"
    fi
    
    # Restart services
    systemctl restart pi-control
    success "Services restarted"
}

# ============================================================================
# Main
# ============================================================================

main() {
    parse_args "$@"
    
    # Initialize log
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "=== Pi Control Panel Update $(date) ===" >> "$LOG_FILE"
    
    print_header
    check_prerequisites
    
    # Backup
    local backup_path=""
    if ! $NO_BACKUP; then
        backup_path=$(create_backup)
    fi
    
    if $BACKUP_ONLY; then
        echo ""
        success "Backup complete. No updates performed."
        exit 0
    fi
    
    # Check for updates
    if ! check_for_updates; then
        exit 0
    fi
    
    # Perform update
    stop_services
    update_code
    update_python_deps
    rebuild_frontend
    start_services
    
    # Verify
    if verify_update; then
        echo ""
        echo -e "${GREEN}${BOLD}✅ Update completed successfully!${NC}"
        echo ""
        
        if [[ -d "$PROJECT_DIR/.git" ]]; then
            cd "$PROJECT_DIR"
            local new_hash
            new_hash=$(git rev-parse HEAD)
            info "Now running version: ${new_hash:0:8}"
        fi
    else
        if [[ -n "$backup_path" ]]; then
            echo ""
            read -p "Update failed. Rollback to previous version? (y/N) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                rollback "$backup_path"
                success "Rollback complete"
            fi
        fi
        exit 1
    fi
}

main "$@"
