# 🚀 Pi Control Panel - Automation Guide

Complete guide for automated deployment and management of Pi Control Panel.

## Quick Start

### One-Line Installation

```bash
git clone https://github.com/BGirginn/rasp_pi_webUI.git
cd rasp_pi_webUI

# Full profile: full system plus Tailscale setup for private remote access
sudo ./install.sh --profile full

# Local profile: same system on the LAN, with no Tailscale install or prompts
sudo ./install.sh --profile local
```

### Remote Deployment (from Mac/Linux)

```bash
# Clone locally
git clone https://github.com/BGirginn/rasp_pi_webUI.git
cd rasp_pi_webUI

# Deploy to Pi
./deploy-native.sh --profile local pi@<lan-ip>
./deploy-native.sh --profile full pi@<tailscale-ip-or-lan-ip>
```

---

## Installation Scripts

### `install.sh` - Main Installer

Automated installation with two access profiles.

```bash
# Full profile is the default
sudo ./install.sh --profile full

# Local LAN-only profile
sudo ./install.sh --profile local

# Options
sudo ./install.sh --profile full     # Full install with Tailscale setup
sudo ./install.sh --profile local    # Same app without Tailscale setup
sudo ./install.sh --profile local --web-port 8088
sudo ./install.sh --skip-preflight   # Skip system checks
sudo ./install.sh --no-tailscale     # Alias for --profile local
sudo ./install.sh --upgrade          # Run scripts/update.sh instead
sudo ./install.sh --verbose          # Verbose output
sudo DEFAULT_ADMIN_PASSWORD='strong-password' ./install.sh --profile local
```

`sudo ./install.sh` defaults to `--profile full`. Use `--profile local` when the panel only needs to run on the same LAN and should not install or invoke Tailscale.
The web UI is exposed on port `8088` by default, so the LAN URL is `http://<pi-ip>:8088`. Use `--web-port <port>` to change it.

**What it does:**
1. ✅ Validates system requirements
2. ✅ Installs Python 3, Node.js 20, Caddy, SQLite and installer prerequisites
3. ✅ Installs Tailscale only in the `full` profile
4. ✅ Copies the project into `/opt/pi-control`
5. ✅ Creates Python virtual environment
6. ✅ Builds React frontend
7. ✅ Configures systemd services
8. ✅ Sets up Caddy reverse proxy
9. ✅ Generates JWT secrets
10. ✅ Seeds the initial admin password when no admin exists yet
11. ✅ Runs health checks

If the database is empty, the first boot creates:

- username: `admin`
- password: `admin`

Use `DEFAULT_ADMIN_PASSWORD` during install to override that first password.

---

### `scripts/pre-flight-check.sh` - System Validation

Run before installation to check requirements.

```bash
./scripts/pre-flight-check.sh --profile full
./scripts/pre-flight-check.sh --profile local
```

**Checks:**
- Hardware: Pi model detection
- Memory: RAM and swap
- Disk: Free space
- OS: Version compatibility
- Network: Internet connectivity
- Tailscale: only checked in `full` profile
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
./scripts/health-check.sh --profile full
./scripts/health-check.sh --profile local
```

**Checks:**
- Service status (pi-control, Caddy)
- API endpoints
- Web interface
- Database integrity
- Configuration files
- Network and profile-specific remote access
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
sudo -u <install-user> npm install
sudo -u <install-user> npm run build

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

### Tailscale not connected (`full` profile only)

```bash
# Check status
tailscale status

# Connect
sudo tailscale up

# Get IP
tailscale ip -4
```

The `local` profile does not install, check, or require Tailscale. Use `http://<pi-ip>:8088` from a device on the same LAN.

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

# Tailscale (full profile only)
tailscale status
tailscale ip -4
```

---

## Security Notes

- Change default password (`admin`/`admin`) immediately
- JWT secret is unique per installation
- Services run as non-root user
- `full` profile uses Tailscale for encrypted private remote access
- `local` profile skips Tailscale and is intended for same-LAN access
- Consider enabling UFW firewall

---

## Support

- **GitHub Issues**: [Report problems](https://github.com/BGirginn/rasp_pi_webUI/issues)
- **Logs**: `/var/log/pi-control-install.log`
