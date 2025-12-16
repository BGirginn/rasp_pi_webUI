#!/bin/bash
# Pi Control Panel - Installation Script
# Installs all dependencies on Raspberry Pi

set -e

echo "=========================================="
echo "  Pi Control Panel - Installation"
echo "=========================================="
echo ""

# Check if running on Raspberry Pi
if [[ ! -f /etc/rpi-issue ]] && [[ ! $(uname -m) =~ ^(arm|aarch64) ]]; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
fi

echo "📦 Updating system packages..."
sudo apt-get update

echo ""
echo "🐍 Installing Python 3 and pip..."
sudo apt-get install -y python3 python3-pip python3-venv

echo ""
echo "📦 Installing Node.js 20..."
if ! command -v node &> /dev/null || [[ $(node -v | cut -d. -f1 | tr -d 'v') -lt 18 ]]; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi
echo "Node.js version: $(node -v)"
echo "npm version: $(npm -v)"

echo ""
echo "🌐 Installing Caddy web server..."
if ! command -v caddy &> /dev/null; then
    sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
    sudo apt-get update
    sudo apt-get install -y caddy
fi
echo "Caddy version: $(caddy version)"

echo ""
echo "🗃️ Installing SQLite..."
sudo apt-get install -y sqlite3

echo ""
echo "✅ All dependencies installed!"
echo ""
echo "Next steps:"
echo "  1. Run: ./deploy-native.sh"
echo "  2. Access: http://$(hostname -I | awk '{print $1}')"
