# Pi Control Panel

<p align="center">
  <strong>Raspberry Pi icin modern, guvenli ve operasyon odakli yonetim paneli</strong><br/>
  FastAPI + React + Agent + Telemetry + Backup
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Raspberry%20Pi-C51A4A" alt="Platform">
  <img src="https://img.shields.io/badge/backend-FastAPI-009688" alt="Backend">
  <img src="https://img.shields.io/badge/frontend-React%20%2B%20Vite-4F46E5" alt="Frontend">
  <img src="https://img.shields.io/badge/security-Tailscale%20First-0A66C2" alt="Security">
  <img src="https://img.shields.io/badge/license-MIT-2563EB" alt="License">
</p>

---

## Genel Bakis

Pi Control Panel, Raspberry Pi cihazlarini tek noktadan izlemenizi ve yonetmenizi saglayan production-ready bir web platformudur.

- Gercek zamanli sistem telemetrisi (CPU, RAM, disk, sicaklik, load, RX/TX)
- systemd servis yonetimi ve temel operasyon komutlari
- USB/Serial/IoT cihaz kesfi ve kontrolu
- Tarayici uzerinden terminal (guvenlik katmanlariyla)
- Alarm kurallari, audit izleri, arsiv ve yedekleme
- Lokal gunluk export ve retention arsivleme akisi

> Guvenlik modeli: varsayilan olarak Tailscale-first ve internete dogrudan acik degil.

---

## Ekran Goruntuleri

<p align="center">
  <img src="./ReadMePhotos/Screenshot%202026-03-27%20at%2014.25.48.png" alt="Screenshot 01" width="48%">
  <img src="./ReadMePhotos/Screenshot%202026-03-27%20at%2014.25.55.png" alt="Screenshot 02" width="48%">
</p>
<p align="center">
  <img src="./ReadMePhotos/Screenshot%202026-03-27%20at%2014.26.04.png" alt="Screenshot 03" width="48%">
  <img src="./ReadMePhotos/Screenshot%202026-03-27%20at%2014.26.09.png" alt="Screenshot 04" width="48%">
</p>
<p align="center">
  <img src="./ReadMePhotos/Screenshot%202026-03-27%20at%2014.26.19.png" alt="Screenshot 05" width="48%">
  <img src="./ReadMePhotos/Screenshot%202026-03-27%20at%2014.28.05.png" alt="Screenshot 06" width="48%">
</p>
<p align="center">
  <img src="./ReadMePhotos/Screenshot%202026-03-27%20at%2014.28.10.png" alt="Screenshot 07" width="48%">
  <img src="./ReadMePhotos/Screenshot%202026-03-27%20at%2014.28.21.png" alt="Screenshot 08" width="48%">
</p>
<p align="center">
  <img src="./ReadMePhotos/Screenshot%202026-03-27%20at%2014.28.25.png" alt="Screenshot 09" width="48%">
  <img src="./ReadMePhotos/Screenshot%202026-03-27%20at%2014.28.48.png" alt="Screenshot 10" width="48%">
</p>

---

## Teknoloji Yigini

| Katman | Teknolojiler |
|---|---|
| UI | React 18, Vite 5, Tailwind CSS, Recharts, Radix UI, XTerm |
| API | FastAPI, Uvicorn, Pydantic v2, aiosqlite, slowapi, SSE |
| Agent | Python tabanli sistem agenti, Unix socket RPC, psutil, docker, MQTT |
| Veri | SQLite (`control.db`, `telemetry.db`) |
| Reverse Proxy | Caddy |
| Test ve Kalite | Vitest, Testing Library, Pytest, Ruff, Black, MyPy, ESLint |
| Altyapi | systemd servisleri, Tailscale erisimi, script tabanli deployment |

---

## Mimari

```mermaid
flowchart TD
    A[Client Browser] --> B[Caddy :80]
    B --> C[FastAPI API :8080]
    C --> D[(control.db)]
    C --> E[(telemetry.db)]
    C --> F[Pi Agent via Unix Socket]
    C --> G[SSE Stream]
    F --> H[System / Devices / Docker / MQTT]
```

Temel calisma modeli:

1. UI, Caddy uzerinden servis edilir.
2. `/api/*` istekleri FastAPI'ye proxylenir.
3. API; DB, background joblar, agent RPC ve SSE akislarini yonetir.
4. Agent, host seviyesinde cihaz/servis/sistem bilgilerini toplar ve komut uygular.

---

## Proje Yapisi

```text
.
|-- panel/
|   |-- ui/                    # React + Vite frontend
|   `-- api/                   # FastAPI backend
|-- agent/                     # Pi agent (RPC, telemetry, providers)
|-- esp/                       # ESP32 ornek firmware dosyalari
|-- scripts/                   # Kurulum, guncelleme, dogrulama scriptleri
|-- caddy/                     # Caddy config
|-- docs/                      # API, guvenlik ve operasyon dokumanlari
|-- install.sh                 # Pi uzerinde native kurulum
`-- deploy-native.sh           # Uzak hosta tek komut deploy
```

---

## Kurulum

### 1) Uzak Deployment (Mac/Linux -> Pi)

```bash
git clone https://github.com/BGirginn/rasp_pi_webUI.git
cd rasp_pi_webUI
./deploy-native.sh pi@<tailscale-ip-veya-lan-ip>
```

Bu akista script:

- SSH baglantisini test eder
- proje dosyalarini rsync ile hedefe tasir
- hedefte `install.sh` calistirir
- API health kontrolu yapar

### 2) Pi Uzerinde Dogrudan Kurulum

```bash
git clone https://github.com/BGirginn/rasp_pi_webUI.git
cd rasp_pi_webUI
chmod +x install.sh
sudo ./install.sh
```

Sik kullanilan opsiyonlar:

```bash
sudo ./install.sh --skip-preflight
sudo ./install.sh --no-tailscale
sudo ./install.sh --upgrade
```

Kurulum sonrasi:

- UI: `http://<pi-ip>`
- API health: `http://<pi-ip>/api/health`
- API docs (debug aciksa): `http://<pi-ip>/api/docs`

---

## Yerel Gelistirme

### API (FastAPI)

```bash
cd panel/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### UI (React + Vite)

```bash
cd panel/ui
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

### Testler

```bash
# API
cd panel/api && pytest

# UI
cd panel/ui && npm test
```

---

## Konfigurasyon

Ornek env dosyasi: [`.env.example`](./.env.example)

Sik kullanilan degiskenler:

| Degisken | Varsayilan | Amac |
|---|---|---|
| `DATABASE_PATH` | `/var/lib/pi-control/control.db` | Ana uygulama veritabani |
| `TELEMETRY_DB_PATH` | `/var/lib/pi-control/telemetry.db` | Telemetry veritabani |
| `AGENT_SOCKET` | `/run/pi-agent/agent.sock` | API-Agent RPC socket yolu |
| `JWT_SECRET_FILE` | `/etc/pi-control/jwt_secret` | JWT secret dosyasi |
| `API_DEBUG` | `false` | Debug ve docs aktivasyonu |
| `PANEL_ALLOW_LAN` | `false` | LAN erisim modu |
| `BACKUP_DAILY_EXPORT_HOUR` | `0` | Gunluk export saati |
| `BACKUP_DAILY_EXPORT_MINUTE` | `5` | Gunluk export dakikasi |

Ilk acilista varsayilan admin:

- kullanici: `admin`
- sifre: `admin123`

Kurulumda sifre override:

```bash
sudo DEFAULT_ADMIN_PASSWORD='guclu-bir-sifre' ./install.sh
```

---

## Operasyon ve Bakim

```bash
# Servis durumlari
sudo systemctl status pi-control
sudo systemctl status pi-agent
sudo systemctl status caddy

# Loglar
sudo journalctl -u pi-control -f
sudo journalctl -u pi-agent -f
sudo journalctl -u caddy -f

# Servis restart
sudo systemctl restart pi-control
sudo systemctl restart pi-agent
sudo systemctl restart caddy

# Guncelleme akisi
sudo ./scripts/update.sh
```

Not: Google Drive backup entegrasyonu gecici olarak devre disidir.

---

## Son Guncelleme Notlari

**Guncel tarih:** 2026-03-27

- Telemetry history ekraninda metrik bazli secim/filtre akisi iyilestirildi.
- Canli metrik yenilemelerinde gereksiz UI resetlerini azaltan stabilizasyonlar eklendi.
- Devices ekraninda kategori tabanli stil yapisi netlestirildi ve tekrar eden kayitlara karsi dedupe mantigi guclendirildi.
- API tarafinda background servis baslatma ve loglama akislarinda dayaniklilik artirildi.
- Kurulum/guncelleme scriptleri operasyonel kullanim icin sadelestirildi ve hizlandirildi.
- Google Drive backup sistemi gecici olarak kaldirildi (local backup aktif).

---

## TODO

- [ ] Google Drive backup entegrasyonunu yeni akisla tekrar devreye almak.

---

## Sorun Giderme

```bash
# API ayakta mi?
curl -s http://127.0.0.1:8080/api/health

# Son 100 log
sudo journalctl -u pi-control -n 100 --no-pager

# Caddy config dogrulama
sudo caddy validate --config /etc/caddy/Caddyfile
```

Dashboard acilmiyorsa:

1. `tailscale status` ile baglantiyi kontrol edin.
2. `sudo systemctl status pi-control caddy` ile servis durumlarini dogrulayin.
3. `http://<pi-ip>/api/health` yanitini test edin.

---

## Lisans

MIT License - detaylar icin [LICENSE](./LICENSE).

---

## Not

Bu README proje deposundaki scriptler ve mevcut kod yapisiyla uyumlu olacak sekilde yeniden duzenlenmistir.
