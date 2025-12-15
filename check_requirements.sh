#!/bin/bash
# Pi Control Panel - Prerequisites Check
# Run this before installation to ensure all requirements are met

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "=========================================="
echo "  Pi Control Panel - Prerequisites Check"
echo "=========================================="
echo ""

ERRORS=0

# Check if running on Raspberry Pi (ARM)
check_architecture() {
    ARCH=$(uname -m)
    if [[ "$ARCH" == "aarch64" || "$ARCH" == "armv7l" ]]; then
        echo -e "${GREEN}✓${NC} Architecture: $ARCH (Raspberry Pi)"
    else
        echo -e "${YELLOW}⚠${NC} Architecture: $ARCH (Not a Raspberry Pi, but may still work)"
    fi
}

# Check Docker
check_docker() {
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | tr -d ',')
        echo -e "${GREEN}✓${NC} Docker: $DOCKER_VERSION"
        
        # Check if Docker daemon is running
        if docker info &> /dev/null; then
            echo -e "${GREEN}✓${NC} Docker daemon: Running"
        else
            echo -e "${RED}✗${NC} Docker daemon: Not running"
            echo "  Run: sudo systemctl start docker"
            ERRORS=$((ERRORS + 1))
        fi
        
        # Check Docker Compose
        if docker compose version &> /dev/null; then
            COMPOSE_VERSION=$(docker compose version --short)
            echo -e "${GREEN}✓${NC} Docker Compose: $COMPOSE_VERSION"
        else
            echo -e "${RED}✗${NC} Docker Compose: Not installed"
            echo "  Run: sudo apt install docker-compose-plugin"
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo -e "${RED}✗${NC} Docker: Not installed"
        echo "  Run: curl -fsSL https://get.docker.com | sh"
        ERRORS=$((ERRORS + 1))
    fi
}

# Check Tailscale
check_tailscale() {
    if command -v tailscale &> /dev/null; then
        if tailscale status &> /dev/null; then
            TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "N/A")
            echo -e "${GREEN}✓${NC} Tailscale: Connected (IP: $TAILSCALE_IP)"
        else
            echo -e "${YELLOW}⚠${NC} Tailscale: Installed but not connected"
            echo "  Run: sudo tailscale up"
        fi
    else
        echo -e "${RED}✗${NC} Tailscale: Not installed (REQUIRED for remote access)"
        echo "  Run: curl -fsSL https://tailscale.com/install.sh | sh"
        ERRORS=$((ERRORS + 1))
    fi
}

# Check Git
check_git() {
    if command -v git &> /dev/null; then
        GIT_VERSION=$(git --version | cut -d' ' -f3)
        echo -e "${GREEN}✓${NC} Git: $GIT_VERSION"
    else
        echo -e "${RED}✗${NC} Git: Not installed"
        echo "  Run: sudo apt install git"
        ERRORS=$((ERRORS + 1))
    fi
}

# Check disk space
check_disk() {
    DISK_FREE=$(df -h / | awk 'NR==2 {print $4}')
    DISK_FREE_MB=$(df -m / | awk 'NR==2 {print $4}')
    
    if [ "$DISK_FREE_MB" -gt 2000 ]; then
        echo -e "${GREEN}✓${NC} Disk space: $DISK_FREE available"
    else
        echo -e "${YELLOW}⚠${NC} Disk space: $DISK_FREE available (recommend >2GB)"
    fi
}

# Check memory
check_memory() {
    MEM_TOTAL=$(free -h | awk 'NR==2 {print $2}')
    MEM_MB=$(free -m | awk 'NR==2 {print $2}')
    
    if [ "$MEM_MB" -gt 1000 ]; then
        echo -e "${GREEN}✓${NC} Memory: $MEM_TOTAL total"
    else
        echo -e "${YELLOW}⚠${NC} Memory: $MEM_TOTAL total (recommend >1GB)"
    fi
}

# Run all checks
echo "Checking system requirements..."
echo ""

check_architecture
check_docker
check_tailscale
check_git
check_disk
check_memory

echo ""
echo "=========================================="

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}All requirements met! Ready to install.${NC}"
    echo ""
    echo "Run: ./deploy.sh"
else
    echo -e "${RED}Found $ERRORS issue(s). Fix them before installing.${NC}"
    exit 1
fi

echo "=========================================="
echo ""
