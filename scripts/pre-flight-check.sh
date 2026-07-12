#!/bin/bash
# ============================================================================
# Pi Control Panel - Pre-flight System Check
# ============================================================================
# Validates that a Raspberry Pi meets all requirements before installation.
#
# Usage: ./scripts/pre-flight-check.sh
#
# Exit codes:
#   0 - All checks passed
#   1 - Critical requirements not met
#   2 - Warnings present but can proceed
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

# Counters
ERRORS=0
WARNINGS=0

# Minimum requirements
readonly MIN_RAM_MB=900        # ~1GB with some tolerance
readonly MIN_DISK_MB=1000      # 1GB free space
readonly MIN_PYTHON_VERSION="3.9"
readonly MIN_NODE_VERSION="18"

# ============================================================================
# Utility Functions
# ============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo -e "${BLUE}${BOLD}  🔍 Pi Control Panel - System Check${NC}"
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo ""
}

print_section() {
    echo ""
    echo -e "${CYAN}▶ $1${NC}"
    echo -e "${CYAN}$(printf '%.0s─' {1..44})${NC}"
}

check_pass() {
    echo -e "  ${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "  ${RED}✗${NC} $1"
    ((ERRORS++))
}

check_warn() {
    echo -e "  ${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

check_info() {
    echo -e "  ${BLUE}ℹ${NC} $1"
}

# ============================================================================
# Hardware Checks
# ============================================================================

check_raspberry_pi() {
    print_section "Hardware Detection"
    
    # Check if running on ARM
    local arch
    arch=$(uname -m)
    
    if [[ "$arch" == "aarch64" ]]; then
        check_pass "Architecture: 64-bit ARM (aarch64)"
    elif [[ "$arch" == "armv7l" ]] || [[ "$arch" == "armv6l" ]]; then
        check_pass "Architecture: 32-bit ARM ($arch)"
    else
        check_warn "Architecture: $arch (not ARM - may not be a Raspberry Pi)"
    fi
    
    # Detect Pi model
    if [[ -f /proc/device-tree/model ]]; then
        local model
        model=$(cat /proc/device-tree/model | tr -d '\0')
        check_pass "Model: $model"
        
        # Warn about unsupported models
        if [[ "$model" == *"Pi Zero"* ]] && [[ "$model" != *"Zero 2"* ]]; then
            check_warn "Pi Zero (original) may have insufficient RAM"
        elif [[ "$model" == *"Pi 2"* ]] || [[ "$model" == *"Pi 1"* ]]; then
            check_warn "Older Pi models may have compatibility issues"
        fi
    elif [[ -f /etc/rpi-issue ]]; then
        check_pass "Raspberry Pi detected (via /etc/rpi-issue)"
    else
        check_warn "Could not detect Raspberry Pi model"
    fi
}

check_memory() {
    print_section "Memory"
    
    # Get total RAM in MB
    local total_ram_kb
    local total_ram_mb
    total_ram_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    total_ram_mb=$((total_ram_kb / 1024))
    
    # Get available RAM
    local avail_ram_kb
    local avail_ram_mb
    avail_ram_kb=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
    avail_ram_mb=$((avail_ram_kb / 1024))
    
    if [[ $total_ram_mb -ge 2048 ]]; then
        check_pass "Total RAM: ${total_ram_mb}MB (recommended: 2GB+)"
    elif [[ $total_ram_mb -ge $MIN_RAM_MB ]]; then
        check_warn "Total RAM: ${total_ram_mb}MB (minimum met, 2GB+ recommended)"
    else
        check_fail "Total RAM: ${total_ram_mb}MB (minimum: 1GB required)"
    fi
    
    check_info "Available RAM: ${avail_ram_mb}MB"
    
    # Check swap
    local swap_total_kb
    local swap_total_mb
    swap_total_kb=$(grep SwapTotal /proc/meminfo | awk '{print $2}')
    swap_total_mb=$((swap_total_kb / 1024))
    
    if [[ $swap_total_mb -lt 512 ]] && [[ $total_ram_mb -lt 2048 ]]; then
        check_warn "Swap: ${swap_total_mb}MB (consider increasing to 1GB+ for low RAM systems)"
    else
        check_pass "Swap: ${swap_total_mb}MB"
    fi
}

check_disk_space() {
    print_section "Disk Space"
    
    # Check /opt (or / if /opt doesn't exist)
    local target_mount="/"
    if mountpoint -q /opt 2>/dev/null; then
        target_mount="/opt"
    fi
    
    local free_mb
    free_mb=$(df -m "$target_mount" | tail -1 | awk '{print $4}')
    
    if [[ $free_mb -ge 2000 ]]; then
        check_pass "Free space on $target_mount: ${free_mb}MB"
    elif [[ $free_mb -ge $MIN_DISK_MB ]]; then
        check_warn "Free space on $target_mount: ${free_mb}MB (minimum met, 2GB+ recommended)"
    else
        check_fail "Free space on $target_mount: ${free_mb}MB (minimum: 1GB required)"
    fi
    
    # Check /var for databases
    local var_mount="/"
    if mountpoint -q /var 2>/dev/null; then
        var_mount="/var"
    fi
    
    local var_free_mb
    var_free_mb=$(df -m "$var_mount" | tail -1 | awk '{print $4}')
    check_info "Free space on $var_mount (for databases): ${var_free_mb}MB"
}

# ============================================================================
# OS & Software Checks
# ============================================================================

check_os() {
    print_section "Operating System"
    
    # Check for Raspberry Pi OS
    if [[ -f /etc/os-release ]]; then
        source /etc/os-release
        check_pass "OS: $PRETTY_NAME"
        
        # Check for systemd
        if command -v systemctl &>/dev/null; then
            check_pass "Init system: systemd"
        else
            check_fail "Init system: systemd not found (required)"
        fi
        
        # Detect Debian version
        if [[ -f /etc/debian_version ]]; then
            local debian_version
            debian_version=$(cat /etc/debian_version)
            
            case "$VERSION_CODENAME" in
                bookworm)
                    check_pass "Debian version: 12 (Bookworm) - Fully supported"
                    ;;
                bullseye)
                    check_pass "Debian version: 11 (Bullseye) - Supported"
                    ;;
                buster)
                    check_warn "Debian version: 10 (Buster) - May need manual Python 3.11 install"
                    ;;
                *)
                    check_info "Debian version: $debian_version ($VERSION_CODENAME)"
                    ;;
            esac
        fi
    else
        check_warn "Could not detect OS version"
    fi
    
    # Check kernel
    local kernel
    kernel=$(uname -r)
    check_info "Kernel: $kernel"
}

check_python() {
    print_section "Python"
    
    if command -v python3 &>/dev/null; then
        local python_version
        python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        local python_full
        python_full=$(python3 --version)
        
        # Compare versions
        if [[ "$(printf '%s\n' "$MIN_PYTHON_VERSION" "$python_version" | sort -V | head -n1)" == "$MIN_PYTHON_VERSION" ]]; then
            check_pass "$python_full"
        else
            check_warn "$python_full (3.11+ recommended)"
        fi
        
        # Check for venv module
        if python3 -c "import venv" 2>/dev/null; then
            check_pass "Python venv module available"
        else
            check_fail "Python venv module not available (install python3-venv)"
        fi
        
        # Check pip
        if command -v pip3 &>/dev/null || python3 -m pip --version &>/dev/null; then
            check_pass "pip available"
        else
            check_warn "pip not found (will be installed)"
        fi
    else
        check_warn "Python 3 not installed (will be installed)"
    fi
}

check_nodejs() {
    print_section "Node.js"
    
    if command -v node &>/dev/null; then
        local node_version
        node_version=$(node -v | tr -d 'v')
        local node_major
        node_major=$(echo "$node_version" | cut -d. -f1)
        
        if [[ $node_major -ge $MIN_NODE_VERSION ]]; then
            check_pass "Node.js v$node_version"
        else
            check_warn "Node.js v$node_version (v18+ required, will be upgraded)"
        fi
        
        if command -v npm &>/dev/null; then
            local npm_version
            npm_version=$(npm -v)
            check_pass "npm v$npm_version"
        else
            check_warn "npm not found (will be installed)"
        fi
    else
        check_info "Node.js not installed (will be installed)"
    fi
}

check_caddy() {
    print_section "Caddy Web Server"
    
    if command -v caddy &>/dev/null; then
        local caddy_version
        caddy_version=$(caddy version 2>/dev/null | head -1 || echo "unknown")
        check_pass "Caddy installed: $caddy_version"
        
        if systemctl is-active --quiet caddy 2>/dev/null; then
            check_pass "Caddy service is running"
        else
            check_info "Caddy service is not running"
        fi
    else
        check_info "Caddy not installed (will be installed)"
    fi
}

check_tailscale() {
    print_section "Tailscale VPN"
    
    if command -v tailscale &>/dev/null; then
        check_pass "Tailscale installed"
        
        # Check status
        if tailscale status &>/dev/null; then
            local ts_ip
            ts_ip=$(tailscale ip -4 2>/dev/null || echo "unknown")
            check_pass "Tailscale connected (IP: $ts_ip)"
        else
            check_warn "Tailscale installed but not connected"
            check_info "Run 'sudo tailscale up' after installation"
        fi
    else
        check_info "Tailscale not installed (will be installed)"
    fi
}

# ============================================================================
# Network Checks
# ============================================================================

check_network() {
    print_section "Network"
    
    # Check internet connectivity
    if ping -c 1 -W 5 8.8.8.8 &>/dev/null; then
        check_pass "Internet connectivity (ping OK)"
    else
        check_fail "No internet connectivity"
    fi
    
    # Check DNS
    if host github.com &>/dev/null 2>&1 || nslookup github.com &>/dev/null 2>&1; then
        check_pass "DNS resolution working"
    else
        check_warn "DNS resolution may have issues"
    fi
    
    # Check if we can reach GitHub
    if curl -sf --connect-timeout 10 https://github.com &>/dev/null; then
        check_pass "GitHub accessible"
    else
        check_warn "Cannot reach GitHub (may affect installation)"
    fi
}

check_ports() {
    print_section "Port Availability"
    
    local ports=("80" "8080" "8081")
    local port_names=("HTTP" "API" "Health")
    
    for i in "${!ports[@]}"; do
        local port="${ports[$i]}"
        local name="${port_names[$i]}"
        
        if ss -tlnp 2>/dev/null | grep -q ":${port} " || netstat -tlnp 2>/dev/null | grep -q ":${port} "; then
            local process
            process=$(ss -tlnp 2>/dev/null | grep ":${port} " | awk '{print $NF}' | head -1 || echo "unknown")
            
            # Check if it's our services
            if [[ "$process" == *"caddy"* ]] || [[ "$process" == *"uvicorn"* ]]; then
                check_pass "Port $port ($name): In use by Pi Control Panel"
            else
                check_warn "Port $port ($name): In use by $process"
            fi
        else
            check_pass "Port $port ($name): Available"
        fi
    done
}

# ============================================================================
# Existing Installation Check
# ============================================================================

check_existing_installation() {
    print_section "Existing Installation"
    
    if [[ -d "/opt/pi-control" ]]; then
        check_info "Existing installation found at /opt/pi-control"
        
        if [[ -f "/opt/pi-control/venv/bin/python" ]]; then
            check_info "Python virtual environment exists"
        fi
        
        if [[ -d "/opt/pi-control/panel/ui/dist" ]]; then
            check_info "Frontend build exists"
        fi
        
        if systemctl is-active --quiet pi-control 2>/dev/null; then
            check_pass "pi-control service is running"
        else
            check_warn "pi-control service is not running"
        fi
    else
        check_info "No existing installation found (fresh install)"
    fi
    
    # Check for databases
    if [[ -f "/var/lib/pi-control/control.db" ]]; then
        local db_size
        db_size=$(du -h /var/lib/pi-control/control.db | cut -f1)
        check_info "Existing database found ($db_size)"
    fi
}

# ============================================================================
# Summary
# ============================================================================

print_summary() {
    echo ""
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo -e "${BLUE}${BOLD}  Summary${NC}"
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo ""
    
    if [[ $ERRORS -gt 0 ]]; then
        echo -e "  ${RED}${BOLD}✗ $ERRORS critical issue(s) found${NC}"
        echo -e "  ${RED}Please resolve these issues before installation.${NC}"
    fi
    
    if [[ $WARNINGS -gt 0 ]]; then
        echo -e "  ${YELLOW}${BOLD}⚠ $WARNINGS warning(s)${NC}"
        echo -e "  ${YELLOW}Installation can proceed but review warnings.${NC}"
    fi
    
    if [[ $ERRORS -eq 0 ]] && [[ $WARNINGS -eq 0 ]]; then
        echo -e "  ${GREEN}${BOLD}✓ All checks passed!${NC}"
        echo -e "  ${GREEN}System is ready for Pi Control Panel installation.${NC}"
    fi
    
    echo ""
    
    if [[ $ERRORS -eq 0 ]]; then
        echo -e "  ${CYAN}To install, run:${NC}"
        echo -e "  ${BOLD}sudo ./install.sh${NC}"
        echo ""
    fi
}

# ============================================================================
# Main
# ============================================================================

main() {
    print_header
    
    # Run all checks
    check_raspberry_pi
    check_memory
    check_disk_space
    check_os
    check_python
    check_nodejs
    check_caddy
    check_tailscale
    check_network
    check_ports
    check_existing_installation
    
    # Print summary
    print_summary
    
    # Return appropriate exit code
    if [[ $ERRORS -gt 0 ]]; then
        exit 1
    elif [[ $WARNINGS -gt 0 ]]; then
        exit 2
    else
        exit 0
    fi
}

main "$@"
