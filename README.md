# 🍓 Pi Control Panel

<p align="center">
  <img src="https://img.shields.io/badge/platform-Raspberry%20Pi-c51a4a.svg" alt="Platform">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/tailscale-required-0A66C2.svg" alt="Tailscale">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License">
</p>

A **modern, beautiful web dashboard** to monitor and control your Raspberry Pi from anywhere via Tailscale VPN.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📊 **Dashboard** | Real-time CPU, memory, disk, temperature monitoring |
| ⚙️ **Services** | Start/stop/restart systemd services |
| 🔌 **Devices** | USB, serial, and IoT device discovery |
| 🌐 **Network** | View and manage network interfaces |
| 💻 **Terminal** | Full browser-based shell access |
| 🔔 **Alerts** | Configurable alert rules with notifications |
| 📈 **Telemetry** | Historical charts and analytics |

---

## 📋 Requirements

> ⚠️ **Tailscale is REQUIRED** for secure remote access.

| Requirement | Version | Notes |
|-------------|---------|-------|
| Raspberry Pi | 3B+ or newer | 64-bit OS recommended |
| Python | 3.11+ | For API backend |
| Node.js | 18+ | For UI build |
| Caddy | 2.7+ | Reverse proxy |
| Tailscale | Latest | For secure remote access |
| Free disk | 1GB+ | For application files |

---

## 🚀 Quick Installation

### From Your Mac (Remote Deploy)

```bash
git clone https://github.com/BGirginn/rasp_pi_webUI.git
cd rasp_pi_webUI
./deploy-native.sh user@<tailscale-ip>
```

### Manual Installation on Pi

```bash
# Clone the repository
git clone https://github.com/BGirginn/rasp_pi_webUI.git
cd rasp_pi_webUI

# Run install script
chmod +x install.sh
./install.sh
```

---

## 🔧 Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Tailscale VPN                    │
│              (Secure Remote Access)                 │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│                  Raspberry Pi                        │
│  ┌───────────────────────────────────────────────┐  │
│  │              Caddy (Port 80/443)              │  │
│  │           Reverse Proxy + Static UI           │  │
│  └─────────────────────┬─────────────────────────┘  │
│                        │                             │
│  ┌─────────────────────▼─────────────────────────┐  │
│  │     Pi Control Panel API (FastAPI:8080)       │  │
│  │         systemd: pi-control.service           │  │
│  └─────────────────────┬─────────────────────────┘  │
│                        │                             │
│  ┌──────────┬──────────┼──────────┬──────────────┐  │
│  │ SQLite   │  System  │  Agent   │  Telemetry   │  │
│  │ Database │  Metrics │  (Pi)    │  Collector   │  │
│  └──────────┴──────────┴──────────┴──────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Directory Structure

```
/opt/pi-control/           # Application root
├── panel/
│   ├── api/               # FastAPI backend
│   └── ui/dist/           # Built React frontend
├── agent/                 # Pi Agent
├── caddy/                 # Caddy config
└── venv/                  # Python virtual environment

/var/lib/pi-control/       # Data directory
├── control.db             # Main database
└── telemetry.db           # Metrics database

/etc/pi-control/           # Config directory
└── jwt_secret             # JWT signing key
```

---

## 🛠️ Maintenance

### View Logs

```bash
# API service logs
sudo journalctl -u pi-control -f

# Caddy logs
sudo journalctl -u caddy -f
```

### Restart Services

```bash
sudo systemctl restart pi-control
sudo systemctl restart caddy
```

### Update to Latest Version

```bash
cd /opt/pi-control
git pull
source venv/bin/activate
pip install -r panel/api/requirements.txt
cd panel/ui && npm install && npm run build
sudo systemctl restart pi-control
```

---

## 🔐 Configuration

### Environment Variables

The service reads configuration from systemd environment:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_PATH` | `/var/lib/pi-control/control.db` | Main database path |
| `TELEMETRY_DB_PATH` | `/var/lib/pi-control/telemetry.db` | Metrics database |
| `JWT_SECRET_FILE` | `/etc/pi-control/jwt_secret` | JWT secret key file |
| `API_DEBUG` | `false` | Enable debug mode |

### Default Credentials

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `admin123` |

> ⚠️ **Change the default password immediately after first login!**

---

## 🐛 Troubleshooting

### Service won't start

```bash
# Check status
sudo systemctl status pi-control

# View detailed logs
sudo journalctl -u pi-control -n 50 --no-pager
```

### Can't access dashboard

1. Ensure both devices are on Tailscale:
   ```bash
   tailscale status
   ```

2. Check if service is running:
   ```bash
   sudo systemctl status pi-control
   curl -s http://localhost:8080/api/health
   ```

3. Check Caddy:
   ```bash
   sudo systemctl status caddy
   ```

### Reset everything

```bash
sudo systemctl stop pi-control
rm -f /var/lib/pi-control/*.db
sudo systemctl start pi-control
```

---

## 📄 API

API documentation available at:

```
http://<tailscale-ip>/api/docs
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Login |
| `/api/telemetry/current` | GET | Current metrics |
| `/api/resources` | GET | List services |
| `/api/resources/{id}/action` | POST | Control service |
| `/api/alerts/rules` | GET/POST | Alert rules |
| `/api/health` | GET | Health check |

---

## 📜 License

MIT License — Free for personal and commercial use.

---

Made by [BGirginn](https://github.com/BGirginn)
