# 🚀 Pi Control Panel - Automation Guide

Complete guide for automated deployment and management of Pi Control Panel.

## Quick Start

### One-Line Installation

```bash
# Clone and install
git clone https://github.com/BGirginn/rasp_pi_webUI.git
cd rasp_pi_webUI
sudo ./install.sh
```

### Remote Deployment (from Mac/Linux)

```bash
# Clone locally
git clone https://github.com/BGirginn/rasp_pi_webUI.git
cd rasp_pi_webUI

# Deploy to Pi
./deploy-native.sh pi@<raspberry-pi-ip>
```

---

## Installation Scripts

### `install.sh` - Main Installer

Full automated installation with all dependencies.

```bash
# Basic installation
sudo ./install.sh

# Options
sudo ./install.sh --skip-preflight   # Skip system checks
sudo ./install.sh --no-tailscale     # Skip Tailscale
sudo ./install.sh --upgrade          # Upgrade existing
sudo ./install.sh --verbose          # Verbose output
```

**What it does:**
1. ✅ Validates system requirements
2. ✅ Sets up swap for low-RAM devices
3. ✅ Installs Python 3, Node.js 20, Caddy, SQLite
4. ✅ Installs Tailscale VPN
5. ✅ Creates Python virtual environment
6. ✅ Builds React frontend
7. ✅ Configures systemd services
8. ✅ Sets up Caddy reverse proxy
9. ✅ Generates JWT secrets
10. ✅ Runs health checks

---

### `scripts/pre-flight-check.sh` - System Validation

Run before installation to check requirements.

```bash
./scripts/pre-flight-check.sh
```

**Checks:**
- Hardware: Pi model detection
- Memory: RAM and swap
- Disk: Free space
- OS: Version compatibility
- Network: Internet connectivity
- Ports: 80, 8080, 8081 availability
- Existing installation detection

---

### `scripts/update.sh` - Update Installation

Zero-downtime updates with automatic backup.

```bash
# Standard update
sudo ./scripts/update.sh

# Options
sudo ./scripts/update.sh --backup-only  # Only backup
sudo ./scripts/update.sh --no-backup    # Skip backup
sudo ./scripts/update.sh --force        # Force even if up-to-date
```

**Features:**
- Automatic database backup
- Git pull and rebuild
- Rollback on failure
- Old backup cleanup

---

### `scripts/uninstall.sh` - Clean Removal

```bash
# Standard uninstall (removes data)
sudo ./scripts/uninstall.sh

# Options
sudo ./scripts/uninstall.sh --keep-data  # Preserve databases
sudo ./scripts/uninstall.sh --purge      # Reset Caddy config
sudo ./scripts/uninstall.sh --yes        # Skip prompts
```

---

### `scripts/health-check.sh` - Validation

```bash
./scripts/health-check.sh
```

**Checks:**
- Service status (pi-control, Caddy)
- API endpoints
- Web interface
- Database integrity
- Configuration files
- Network/Tailscale
- System resources

---

## Directory Structure

```
/opt/pi-control/           # Application
├── panel/
│   ├── api/               # FastAPI backend
│   └── ui/dist/           # React frontend (built)
├── agent/                 # Pi Agent
├── scripts/               # Automation scripts
├── venv/                  # Python environment
└── caddy/                 # Caddy config

/var/lib/pi-control/       # Data
├── control.db             # Main database
└── telemetry.db           # Metrics

/etc/pi-control/           # Config
└── jwt_secret             # JWT key

/var/backups/pi-control/   # Backups
└── YYYYMMDD-HHMMSS/       # Timestamped backups
```

---

## Troubleshooting

### Service won't start

```bash
# Check status
sudo systemctl status pi-control

# View logs
sudo journalctl -u pi-control -n 50

# Restart
sudo systemctl restart pi-control
```

### API not responding

```bash
# Test locally
curl http://localhost:8080/api/health

# Check port
ss -tlnp | grep 8080
```

### Frontend not loading

```bash
# Rebuild frontend
cd /opt/pi-control/panel/ui
sudo -u pi npm install
sudo -u pi npm run build

# Restart Caddy
sudo systemctl restart caddy
```

### Database issues

```bash
# Check integrity
sqlite3 /var/lib/pi-control/control.db "PRAGMA integrity_check;"

# Reset (WARNING: loses data)
sudo systemctl stop pi-control
rm /var/lib/pi-control/*.db
sudo systemctl start pi-control
```

### Tailscale not connected

```bash
# Check status
tailscale status

# Connect
sudo tailscale up

# Get IP
tailscale ip -4
```

---

## Supported Hardware

| Model | RAM | Status |
|-------|-----|--------|
| Pi 5 | 4GB/8GB | ✅ Fully supported |
| Pi 4 | 2GB/4GB/8GB | ✅ Fully supported |
| Pi 4 | 1GB | ✅ Supported (uses swap) |
| Pi 3B+ | 1GB | ✅ Supported (uses swap) |
| Pi Zero 2 W | 512MB | ⚠️ Limited (slow builds) |

---

## Useful Commands

```bash
# Service management
sudo systemctl status pi-control
sudo systemctl restart pi-control
sudo systemctl stop pi-control

# Logs
sudo journalctl -u pi-control -f       # Live logs
sudo journalctl -u pi-control -n 100   # Last 100 lines

# Caddy
sudo systemctl status caddy
sudo systemctl reload caddy

# Tailscale
tailscale status
tailscale ip -4
```

---

## Security Notes

- Change default password (`admin`/`admin123`) immediately
- JWT secret is unique per installation
- Services run as non-root user
- Tailscale provides encrypted remote access
- Consider enabling UFW firewall

---

## Support

- **GitHub Issues**: [Report problems](https://github.com/BGirginn/rasp_pi_webUI/issues)
- **Logs**: `/var/log/pi-control-install.log`
