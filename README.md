# 🍓 Pi Control Panel

<p align="center">
  <img src="https://img.shields.io/badge/platform-Raspberry%20Pi-c51a4a.svg" alt="Platform">
  <img src="https://img.shields.io/badge/docker-ready-2496ED.svg" alt="Docker">
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

> ⚠️ **Tailscale is REQUIRED** for remote access. This is not optional.

| Requirement | Version | Notes |
|-------------|---------|-------|
| Raspberry Pi | 3B+ or newer | 64-bit OS recommended |
| Docker | 20.10+ | With Docker Compose plugin |
| Tailscale | Latest | For secure remote access |
| Free disk | 2GB+ | For Docker images |
| Memory | 1GB+ | 2GB+ recommended |

---

## 🚀 Installation

### Step 1: Check Requirements

Run the requirements check first:

```bash
git clone https://github.com/BGirginn/rasp_pi_webUI.git
cd rasp_pi_webUI
chmod +x check_requirements.sh
./check_requirements.sh
```

If any requirements are missing, the script will tell you how to install them.

### Step 2: Install Tailscale (If Not Installed)

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Connect to Tailscale
sudo tailscale up

# Note your Tailscale IP
tailscale ip -4
```

**On your local device (Mac/Windows/Linux):**
1. Download Tailscale from [tailscale.com/download](https://tailscale.com/download)
2. Install and sign in with the same account
3. Both devices are now on the same secure network

### Step 3: Install Docker (If Not Installed)

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Add your user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose plugin
sudo apt install docker-compose-plugin -y

# Logout and login again
exit
```

### Step 4: Deploy

```bash
cd rasp_pi_webUI
chmod +x deploy.sh
./deploy.sh
```

### Step 5: Access Dashboard

Open your browser and go to:

```
http://<your-tailscale-ip>:8080
```

**Example:** `http://100.80.90.68:8080`

> 💡 **Note:** If `:8080` doesn't work, try without the port: `http://100.80.90.68`

**Default Login Credentials:**

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `admin123` |

> ⚠️ **Change the default password immediately after first login!**

---

## 🔧 Configuration

### Environment Variables

Copy and edit the environment file:

```bash
cp .env.example .env
nano .env
```

```env
# Security (generate a random string)
JWT_SECRET=change-this-to-random-string

# Admin password
ADMIN_PASSWORD=admin123

# Timezone
TZ=Europe/Istanbul
```

### Changing Admin Password

1. Login → Go to Settings → Change Password
2. Or via API:
```bash
curl -X POST http://localhost/api/auth/change-password \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"current_password": "admin123", "new_password": "your-new-password"}'
```

---

## 🛠️ Maintenance

### View Logs

```bash
docker compose logs -f          # All services
docker compose logs -f panel    # API only
```

### Restart Services

```bash
docker compose restart
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
cp -r data/ backup_$(date +%Y%m%d)/
```

---

## 🐛 Troubleshooting

### Can't access dashboard

**Problem:** Browser says "connection refused" or "site can't be reached"

**Solutions:**
1. Make sure both devices are on Tailscale:
   ```bash
   tailscale status
   ```
2. Try without port number: `http://100.x.x.x` instead of `http://100.x.x.x:8080`
3. Check if containers are running:
   ```bash
   docker compose ps
   ```
4. Check firewall:
   ```bash
   sudo ufw status
   ```

### Docker build fails

**Problem:** "Cannot connect to Docker daemon"

**Solution:**
```bash
sudo systemctl start docker
sudo usermod -aG docker $USER
# Logout and login again
```

### Tailscale not connecting

**Problem:** `tailscale status` shows disconnected

**Solution:**
```bash
sudo systemctl restart tailscaled
sudo tailscale up
```

### Port 80 already in use

**Problem:** "port is already allocated"

**Solution:**
```bash
# Find what's using port 80
sudo lsof -i :80

# Stop the conflicting service or edit docker-compose.yml
# Change "80:80" to "8080:80"
```

### Reset everything

```bash
docker compose down -v
rm -rf data/
docker compose up -d --build
```

---

## 🏗️ Architecture

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
│  │          Pi Control Panel API (FastAPI)       │  │
│  │              /api/* endpoints                 │  │
│  └─────────────────────┬─────────────────────────┘  │
│                        │                             │
│  ┌──────────┬──────────┼──────────┬──────────────┐  │
│  │ SQLite   │  System  │  MQTT    │  Telemetry   │  │
│  │ Database │  Metrics │  Broker  │  Collector   │  │
│  └──────────┴──────────┴──────────┴──────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## 📄 API

When running, API docs are available at:

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

---

## 📜 License

MIT License — Free for personal and commercial use.

---

Made by [BGirginn](https://github.com/BGirginn)
