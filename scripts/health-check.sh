#!/bin/bash
# ============================================================================
# Pi Control Panel - Health Check Script
# ============================================================================
# Validates that all components of Pi Control Panel are working correctly.
#
# Usage: ./scripts/health-check.sh
#
# Exit codes:
#   0 - All checks passed
#   1 - Critical failures detected
#   2 - Warnings present but functional
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

# Endpoints
readonly API_BASE="http://127.0.0.1:8080"
readonly WEB_BASE="http://127.0.0.1"

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# ============================================================================
# Utility Functions
# ============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo -e "${BLUE}${BOLD}  🏥 Pi Control Panel - Health Check${NC}"
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
    ((PASSED++))
}

check_fail() {
    echo -e "  ${RED}✗${NC} $1"
    ((FAILED++))
}

check_warn() {
    echo -e "  ${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

check_info() {
    echo -e "  ${BLUE}ℹ${NC} $1"
}

# ============================================================================
# Service Checks
# ============================================================================

check_services() {
    print_section "Services"
    
    # Pi Control service
    if systemctl is-active --quiet pi-control 2>/dev/null; then
        check_pass "pi-control service is running"
        
        # Get uptime
        local uptime
        uptime=$(systemctl show pi-control --property=ActiveEnterTimestamp --value 2>/dev/null || echo "unknown")
        check_info "Started: $uptime"
    else
        check_fail "pi-control service is not running"
        
        # Show status
        local status
        status=$(systemctl is-enabled pi-control 2>/dev/null || echo "unknown")
        check_info "Service enabled: $status"
        
        # Show recent logs
        echo ""
        echo -e "  ${YELLOW}Recent logs:${NC}"
        journalctl -u pi-control -n 5 --no-pager 2>/dev/null | sed 's/^/    /' || true
    fi
    
    # Caddy service
    if systemctl is-active --quiet caddy 2>/dev/null; then
        check_pass "Caddy service is running"
    else
        check_fail "Caddy service is not running"
    fi
}

# ============================================================================
# API Checks
# ============================================================================

check_api() {
    print_section "API Endpoints"
    
    # Health endpoint
    local health_response
    if health_response=$(curl -sf --max-time 5 "$API_BASE/api/health" 2>/dev/null); then
        check_pass "API health endpoint responding"
        
        # Parse response if JSON
        if echo "$health_response" | grep -q "status"; then
            check_info "Response: $health_response"
        fi
    else
        check_fail "API health endpoint not responding"
        
        # Check if port is listening
        if ss -tlnp 2>/dev/null | grep -q ":8080 "; then
            check_info "Port 8080 is listening (API may be starting up)"
        else
            check_info "Port 8080 is not listening"
        fi
    fi
    
    # Docs endpoint
    if curl -sf --max-time 5 "$API_BASE/api/docs" > /dev/null 2>&1; then
        check_pass "API docs endpoint accessible"
    else
        check_warn "API docs endpoint not accessible"
    fi
    
    # Authentication endpoint
    local auth_response
    if auth_response=$(curl -sf --max-time 5 -X POST "$API_BASE/api/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"username":"test","password":"test"}' 2>/dev/null); then
        check_pass "Auth endpoint responding"
    elif curl -sf --max-time 5 -X POST "$API_BASE/api/auth/login" 2>&1 | grep -q "422\|401\|400"; then
        check_pass "Auth endpoint responding (validation working)"
    else
        # Try with GET to see if endpoint exists
        if curl -sf --max-time 5 -X OPTIONS "$API_BASE/api/auth/login" > /dev/null 2>&1; then
            check_pass "Auth endpoint exists"
        else
            check_warn "Auth endpoint not responding"
        fi
    fi
}

# ============================================================================
# Web Interface Checks
# ============================================================================

check_web() {
    print_section "Web Interface"
    
    # Main page
    local web_response
    if web_response=$(curl -sf --max-time 5 "$WEB_BASE/" 2>/dev/null); then
        if echo "$web_response" | grep -q "html"; then
            check_pass "Web interface accessible"
        else
            check_warn "Web interface returned unexpected response"
        fi
    else
        check_fail "Web interface not accessible"
    fi
    
    # Check for static assets
    if [[ -d "$PROJECT_DIR/panel/ui/dist" ]]; then
        check_pass "Frontend build exists"
        
        local file_count
        file_count=$(find "$PROJECT_DIR/panel/ui/dist" -type f | wc -l)
        check_info "Static files: $file_count"
    else
        check_fail "Frontend build missing"
    fi
}

# ============================================================================
# Database Checks
# ============================================================================

check_databases() {
    print_section "Databases"
    
    # Control database
    if [[ -f "$DATA_DIR/control.db" ]]; then
        local db_size
        db_size=$(du -h "$DATA_DIR/control.db" | cut -f1)
        check_pass "Control database exists ($db_size)"
        
        # Check integrity
        if command -v sqlite3 &>/dev/null; then
            if sqlite3 "$DATA_DIR/control.db" "PRAGMA integrity_check;" 2>/dev/null | grep -q "ok"; then
                check_pass "Control database integrity OK"
            else
                check_warn "Control database integrity check failed"
            fi
        fi
    else
        check_warn "Control database not found"
    fi
    
    # Telemetry database
    if [[ -f "$DATA_DIR/telemetry.db" ]]; then
        local tel_size
        tel_size=$(du -h "$DATA_DIR/telemetry.db" | cut -f1)
        check_pass "Telemetry database exists ($tel_size)"
    else
        check_info "Telemetry database not found (may not be initialized)"
    fi
}

# ============================================================================
# Configuration Checks
# ============================================================================

check_config() {
    print_section "Configuration"
    
    # JWT secret
    if [[ -f "$CONFIG_DIR/jwt_secret" ]]; then
        local secret_perms
        secret_perms=$(stat -c "%a" "$CONFIG_DIR/jwt_secret" 2>/dev/null || stat -f "%Lp" "$CONFIG_DIR/jwt_secret" 2>/dev/null || echo "unknown")
        
        if [[ "$secret_perms" == "600" ]]; then
            check_pass "JWT secret exists with correct permissions"
        else
            check_warn "JWT secret permissions: $secret_perms (should be 600)"
        fi
    else
        check_fail "JWT secret not found"
    fi
    
    # Caddyfile
    if [[ -f "/etc/caddy/Caddyfile" ]]; then
        if grep -q "pi-control\|opt/pi-control" /etc/caddy/Caddyfile 2>/dev/null; then
            check_pass "Caddyfile configured for Pi Control Panel"
        else
            check_warn "Caddyfile may not be configured correctly"
        fi
    else
        check_fail "Caddyfile not found"
    fi
}

# ============================================================================
# Network Checks
# ============================================================================

check_network() {
    print_section "Network"
    
    # Get IP addresses
    local local_ip
    local_ip=$(hostname -I | awk '{print $1}')
    check_info "Local IP: $local_ip"
    
    # Tailscale
    if command -v tailscale &>/dev/null; then
        if tailscale status &>/dev/null 2>&1; then
            local ts_ip
            ts_ip=$(tailscale ip -4 2>/dev/null || echo "unknown")
            check_pass "Tailscale connected (IP: $ts_ip)"
        else
            check_warn "Tailscale installed but not connected"
            check_info "Run: sudo tailscale up"
        fi
    else
        check_warn "Tailscale not installed"
    fi
    
    # Port checks
    local ports=("80" "8080")
    for port in "${ports[@]}"; do
        if ss -tlnp 2>/dev/null | grep -q ":${port} "; then
            check_pass "Port $port is listening"
        else
            check_fail "Port $port is not listening"
        fi
    done
}

# ============================================================================
# Resource Checks
# ============================================================================

check_resources() {
    print_section "System Resources"
    
    # Memory
    local mem_total mem_avail mem_percent
    mem_total=$(grep MemTotal /proc/meminfo | awk '{print int($2/1024)}')
    mem_avail=$(grep MemAvailable /proc/meminfo | awk '{print int($2/1024)}')
    mem_percent=$((100 - (mem_avail * 100 / mem_total)))
    
    if [[ $mem_percent -lt 90 ]]; then
        check_pass "Memory usage: ${mem_percent}% (${mem_avail}MB available)"
    else
        check_warn "Memory usage: ${mem_percent}% (low memory)"
    fi
    
    # Disk
    local disk_percent
    disk_percent=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
    
    if [[ $disk_percent -lt 90 ]]; then
        check_pass "Disk usage: ${disk_percent}%"
    else
        check_warn "Disk usage: ${disk_percent}% (running low)"
    fi
    
    # CPU temperature (Raspberry Pi specific)
    if [[ -f /sys/class/thermal/thermal_zone0/temp ]]; then
        local temp
        temp=$(($(cat /sys/class/thermal/thermal_zone0/temp) / 1000))
        
        if [[ $temp -lt 70 ]]; then
            check_pass "CPU temperature: ${temp}°C"
        elif [[ $temp -lt 80 ]]; then
            check_warn "CPU temperature: ${temp}°C (warm)"
        else
            check_warn "CPU temperature: ${temp}°C (hot - may throttle)"
        fi
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
    
    echo -e "  ${GREEN}Passed:${NC}   $PASSED"
    echo -e "  ${YELLOW}Warnings:${NC} $WARNINGS"
    echo -e "  ${RED}Failed:${NC}   $FAILED"
    echo ""
    
    if [[ $FAILED -gt 0 ]]; then
        echo -e "  ${RED}${BOLD}❌ Health check FAILED${NC}"
        echo -e "  ${RED}Some components are not working correctly.${NC}"
        echo ""
        echo "  Troubleshooting:"
        echo "    • Check logs: sudo journalctl -u pi-control -n 50"
        echo "    • Restart: sudo systemctl restart pi-control"
        echo "    • Reinstall: sudo ./install.sh"
    elif [[ $WARNINGS -gt 0 ]]; then
        echo -e "  ${YELLOW}${BOLD}⚠️  Health check passed with warnings${NC}"
        echo -e "  ${YELLOW}System is functional but review warnings above.${NC}"
    else
        echo -e "  ${GREEN}${BOLD}✅ All health checks passed!${NC}"
        echo -e "  ${GREEN}Pi Control Panel is running correctly.${NC}"
    fi
    
    echo ""
    
    # Access information
    local local_ip
    local_ip=$(hostname -I | awk '{print $1}')
    echo -e "  ${BOLD}🌐 Access your dashboard:${NC}"
    echo -e "     Local: ${CYAN}http://$local_ip${NC}"
    
    if command -v tailscale &>/dev/null && tailscale status &>/dev/null 2>&1; then
        local ts_ip
        ts_ip=$(tailscale ip -4 2>/dev/null || echo "")
        if [[ -n "$ts_ip" ]]; then
            echo -e "     Tailscale: ${CYAN}http://$ts_ip${NC}"
        fi
    fi
    
    echo ""
}

# ============================================================================
# Main
# ============================================================================

main() {
    print_header
    
    check_services
    check_api
    check_web
    check_databases
    check_config
    check_network
    check_resources
    
    print_summary
    
    # Exit code
    if [[ $FAILED -gt 0 ]]; then
        exit 1
    elif [[ $WARNINGS -gt 0 ]]; then
        exit 2
    else
        exit 0
    fi
}

main "$@"
