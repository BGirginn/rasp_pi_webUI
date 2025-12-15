# 🍓 Pi Control Panel

<p align="center">
  <img src="https://img.shields.io/badge/platform-Raspberry%20Pi-c51a4a.svg" alt="Platform">
  <img src="https://img.shields.io/badge/docker-ready-2496ED.svg" alt="Docker">
  <img src="https://img.shields.io/badge/tailscale-ready-0A66C2.svg" alt="Tailscale">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License">
</p>

A **modern, beautiful web dashboard** to monitor and control your Raspberry Pi from anywhere. Features real-time metrics, service management, terminal access, and a cyberpunk dark theme.

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
| 🔐 **Auth** | JWT authentication with 2FA support |

---

## 🖥️ Screenshots

<p align="center">
  <i>Beautiful dark neon theme with glassmorphism</i>
</p>

---

## 📋 Prerequisites

Before installation, ensure you have:

- **Raspberry Pi** (3B+ or newer recommended)
- **Raspberry Pi OS** (64-bit recommended)
- **Docker & Docker Compose** installed
- **Tailscale** account (for remote access)

---

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/BGirginn/rasp_pi_webUI.git
cd rasp_pi_webUI
```

### 2. Run the Deploy Script

```bash
chmod +x deploy.sh
./deploy.sh
```

### 3. Access the Dashboard

Open your browser and go to:
```
http://<your-pi-ip>:8080
```

**Default credentials:**
- Username: `admin`
- Password: `admin123`

> ⚠️ **Change the default password immediately after first login!**

---

## 📖 Detailed Installation Guide

### Step 1: Prepare Your Raspberry Pi

#### Update the System

```bash
sudo apt update && sudo apt upgrade -y
```

#### Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose plugin
sudo apt install docker-compose-plugin -y

# Logout and login again, or run:
newgrp docker

# Verify installation
docker --version
docker compose version
```

---

### Step 2: Install Tailscale (For Remote Access)

Tailscale creates a secure private network so you can access your Pi from anywhere.

#### On Your Raspberry Pi:

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Start Tailscale and authenticate
sudo tailscale up

# Follow the link to authenticate in your browser
# Note your Tailscale IP (e.g., 100.x.x.x)
```

#### Verify Tailscale:

```bash
# Check Tailscale status
tailscale status

# Get your Tailscale IP
tailscale ip -4
```

#### On Your Local Device (Mac/Windows/Linux):

1. Download Tailscale from [tailscale.com/download](https://tailscale.com/download)
2. Install and sign in with the same account
3. Your devices are now on the same secure network!

---

### Step 3: Clone and Configure

```bash
# Clone the repository
cd ~
git clone https://github.com/BGirginn/rasp_pi_webUI.git
cd rasp_pi_webUI

# Copy environment file
cp .env.example .env

# Edit the environment file (optional)
nano .env
```

#### Environment Variables (.env):

```env
# JWT Secret (generate a random string)
JWT_SECRET=your-super-secret-key-here

# Admin password (change this!)
ADMIN_PASSWORD=admin123

# Timezone
TZ=Europe/Istanbul
```

---

### Step 4: Deploy with Docker

```bash
# Build and start all services
docker compose up -d --build

# Check if containers are running
docker compose ps

# View logs
docker compose logs -f panel
```

#### Expected Output:

```
NAME                STATUS              PORTS
pi-control-panel    Up (healthy)        8080/tcp
pi-control-caddy    Up                  80/tcp, 443/tcp
pi-control-mqtt     Up                  1883/tcp
```

---

### Step 5: Access the Dashboard

| Access Method | URL |
|--------------|-----|
| **Local Network** | `http://<raspberry-pi-ip>:8080` |
| **Tailscale** | `http://<tailscale-ip>:8080` |
| **With Caddy** | `http://<raspberry-pi-ip>` (port 80) |

---

## 🔧 Configuration

### Changing Admin Password

1. Login with default credentials
2. Go to **Settings** → **Change Password**
3. Enter new password

Or via API:
```bash
curl -X POST http://localhost:8080/api/auth/change-password \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"current_password": "admin123", "new_password": "your-new-password"}'
```

### Adding SSL (HTTPS)

Edit `caddy/Caddyfile`:

```caddyfile
your-domain.com {
    reverse_proxy panel:8080
}
```

Caddy will automatically obtain and renew SSL certificates.

---

## 🛠️ Maintenance Commands

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f panel
```

### Restart Services

```bash
# Restart all
docker compose restart

# Restart specific service
docker compose restart panel
```

### Update to Latest Version

```bash
cd ~/rasp_pi_webUI
git pull
docker compose down
docker compose up -d --build
```

### Backup Data

```bash
# Backup database
cp -r data/ data_backup_$(date +%Y%m%d)/
```

---

## 📱 Mobile App

A React Native mobile app is also available for iOS and Android.

```bash
cd mobile
npm install
npm start
```

Scan the QR code with Expo Go app on your phone.

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────┐
│                      Client                            │
│  (Browser / Mobile App)                                │
└───────────────────────┬────────────────────────────────┘
                        │ HTTPS/HTTP
                        ▼
┌────────────────────────────────────────────────────────┐
│                 Caddy (Reverse Proxy)                  │
│                    Port 80/443                         │
└───────────────────────┬────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
┌──────────────────┐           ┌──────────────────┐
│   Static UI      │           │    API Server    │
│   (React/Vite)   │           │    (FastAPI)     │
│   /srv/ui/*      │           │    /api/*        │
└──────────────────┘           └────────┬─────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
             ┌──────────┐        ┌──────────┐        ┌──────────┐
             │ SQLite   │        │  System  │        │   MQTT   │
             │ Database │        │  Metrics │        │  Broker  │
             └──────────┘        └──────────┘        └──────────┘
```

---

## 🔒 Security

- **JWT Authentication** with secure token storage
- **2FA Support** via TOTP (Google Authenticator)
- **Role-based Access** (Admin, Operator, Viewer)
- **Rate Limiting** on API endpoints
- **Tailscale VPN** for secure remote access

---

## 🐛 Troubleshooting

### Container won't start

```bash
# Check logs
docker compose logs panel

# Check system resources
free -h
df -h
```

### Can't access dashboard

1. Check if containers are running: `docker compose ps`
2. Check firewall: `sudo ufw status`
3. Check port: `curl localhost:8080/api/health`

### Tailscale connection issues

```bash
# Check Tailscale status
tailscale status

# Restart Tailscale
sudo systemctl restart tailscaled
```

### Reset to default

```bash
docker compose down -v
rm -rf data/
docker compose up -d --build
```

---

## 📄 API Documentation

API is available at `/api/docs` (Swagger UI) when running.

### Key Endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Authenticate user |
| `/api/telemetry/current` | GET | Get current metrics |
| `/api/resources` | GET | List all services |
| `/api/resources/{id}/action` | POST | Control a service |
| `/api/devices` | GET | List connected devices |
| `/api/alerts` | GET | List active alerts |

---

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines.

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

---

## 📜 License

[MIT License](LICENSE) — Free for personal and commercial use.

---

## 👨‍💻 Author

Made with ❤️ by [Bora Girgin](https://github.com/BGirginn)

---

<p align="center">
  <sub>🍓 Monitor your Pi. Control your world.</sub>
</p>
