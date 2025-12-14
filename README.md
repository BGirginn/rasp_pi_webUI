# 🍓 Pi Control Panel

A modern, feature-rich web-based control panel for Raspberry Pi. Monitor system resources, manage services, control devices, and access your Pi from anywhere via Tailscale.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-green.svg)
![React](https://img.shields.io/badge/react-18+-61DAFB.svg)

## ✨ Features

### 📊 Real-Time Monitoring
- **Dashboard** - CPU, Memory, Disk usage with live updates
- **Telemetry** - Historical data visualization with charts
- **System Info** - Hostname, OS, uptime, temperature

### 🌐 Network Management
- View all network interfaces (Ethernet, WiFi, Tailscale, Docker)
- Real-time traffic statistics (RX/TX bytes)
- Interface status monitoring

### ⚙️ Service Management
- List running systemd services
- Start, stop, restart services
- Health monitoring with status indicators

### 🔌 Device Discovery
- USB device detection
- Serial port enumeration
- ESP32/IoT device integration

### 💻 Web Terminal
- Browser-based shell access via xterm.js
- Full PTY support with 256 colors
- Terminal resize support

### 🔐 Security
- JWT authentication
- Role-based access control (Admin, Operator, Viewer)
- CORS protection
- Rate limiting

## 🚀 Quick Start

### Prerequisites
- Raspberry Pi 4/5 with Debian/Raspberry Pi OS
- Python 3.11+
- Node.js 18+ (for development)

### Installation

```bash
# Clone the repository
git clone https://github.com/BGirginn/rasp_pi_webUI.git
cd rasp_pi_webUI

# Setup API
cd panel/api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
mkdir -p data

# Create .env file
cat > .env << EOF
DATABASE_PATH=./data/control.db
TELEMETRY_DB_PATH=./data/telemetry.db
JWT_SECRET=your-secret-key-here
CORS_ORIGINS=*
EOF

# Start the API
python -m uvicorn main:app --host 0.0.0.0 --port 8080
```

### Production Deployment

```bash
# Install as systemd service
sudo cp pi-control.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pi-control
sudo systemctl start pi-control
```

## 📁 Project Structure

```
rasp_pi_webui/
├── agent/                 # Pi Agent (background service)
│   ├── providers/         # Resource providers (devices, network, systemd)
│   ├── telemetry/         # System metrics collection
│   └── jobs/              # Scheduled job runner
├── panel/
│   ├── api/               # FastAPI backend
│   │   ├── routers/       # API endpoints
│   │   ├── db/            # Database migrations
│   │   └── services/      # Business logic
│   └── ui/                # React frontend
│       ├── src/pages/     # Page components
│       └── src/components/ # Reusable components
├── docs/                  # Documentation
└── docker-compose.yml     # Container orchestration
```

## 🔧 Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 18, Vite, TailwindCSS, Recharts, xterm.js |
| **Backend** | FastAPI, Uvicorn, SQLite, Pydantic |
| **System** | Python, psutil, systemctl, PTY |
| **DevOps** | Docker, systemd, Caddy |

## 🌐 Access

| Method | URL |
|--------|-----|
| Local Network | `http://<pi-ip>:8080` |
| Tailscale | `http://<tailscale-ip>:8080` |

### Default Credentials
- **Username:** `admin`
- **Password:** `admin123`

> ⚠️ Change the default password in production!

## 📸 Screenshots

*Coming soon*

## 🛣️ Roadmap

- [ ] GPIO Manager
- [ ] Docker container management
- [ ] MQTT integration for IoT devices
- [ ] Mobile-responsive improvements
- [ ] Dark/Light theme toggle
- [ ] Multi-language support

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 👨‍💻 Author

**Bora Girgin** - [@BGirginn](https://github.com/BGirginn)

---

<p align="center">
  Made with ❤️ for Raspberry Pi enthusiasts
</p>
