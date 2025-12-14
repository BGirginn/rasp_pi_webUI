# API Reference - Pi Control Panel

## Base URL

```
https://<your-pi-hostname>/api
```

## Authentication

All endpoints except `/api/auth/login` require a valid JWT token.

### Headers

```http
Authorization: Bearer <access_token>
```

---

## Authentication (`/api/auth`)

### Login

```http
POST /api/auth/login
```

**Request Body:**
```json
{
  "username": "admin",
  "password": "yourpassword",
  "totp_code": "123456"  // Optional, required if 2FA enabled
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": 1,
    "username": "admin",
    "role": "admin",
    "has_totp": true
  }
}
```

### Refresh Token

```http
POST /api/auth/refresh
```

Uses HttpOnly cookie `refresh_token`.

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "expires_in": 900
}
```

### Logout

```http
POST /api/auth/logout
```

### Current User

```http
GET /api/auth/me
```

---

## Resources (`/api/resources`)

### List Resources

```http
GET /api/resources
```

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| provider | string | Filter by provider (docker, systemd) |
| resource_class | string | Filter by class (CORE, SYSTEM, APP, DEVICE) |
| managed | boolean | Filter by managed status |

**Response:**
```json
[
  {
    "id": "docker_nginx",
    "name": "nginx",
    "type": "container",
    "resource_class": "APP",
    "provider": "docker",
    "state": "running",
    "health_score": 95,
    "managed": true,
    "updated_at": "2024-01-15T10:30:00Z"
  }
]
```

### Get Resource

```http
GET /api/resources/{resource_id}
```

### Execute Action

```http
POST /api/resources/{resource_id}/action
```

**Request Body:**
```json
{
  "action": "restart",
  "params": {}
}
```

**Available Actions:**
| Provider | Action | Roles |
|----------|--------|-------|
| docker | start, stop, restart, pause, unpause | admin, operator |
| systemd | restart, reload | admin (SYSTEM), admin/operator (APP) |

### Manage Resource

```http
POST /api/resources/{resource_id}/manage?resource_class=APP
```

Moves unmanaged resource to managed status.

---

## Telemetry (`/api/telemetry`)

### Current Metrics

```http
GET /api/telemetry/current
```

**Response:**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "metrics": {
    "host.cpu.pct_total": 35.5,
    "host.mem.pct": 62.3,
    "host.temp.cpu_c": 48.5
  }
}
```

### Dashboard Data

```http
GET /api/telemetry/dashboard
```

### Query Historical Metrics

```http
GET /api/telemetry/metrics?metrics=host.cpu.pct_total,host.mem.pct&start=1705300000&end=1705310000
```

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| metrics | string | Comma-separated metric names |
| start | int | Start timestamp (epoch) |
| end | int | End timestamp (epoch) |
| step | int | Step size in seconds (default: 60) |

### Available Metrics

```http
GET /api/telemetry/metrics/available
```

---

## Logs (`/api/logs`)

### Get Resource Logs

```http
GET /api/logs/{resource_id}?tail=100&level=error
```

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| tail | int | Number of lines (default: 100, max: 10000) |
| since | string | ISO timestamp |
| until | string | ISO timestamp |
| level | string | Filter by level (error, warning, info) |

### Search Logs

```http
GET /api/logs/{resource_id}/search?query=error&context_lines=2
```

### Stream Logs (SSE)

```http
GET /api/logs/{resource_id}/stream
```

---

## Jobs (`/api/jobs`)

### List Job Types

```http
GET /api/jobs/types
```

### List Jobs

```http
GET /api/jobs?state=running&limit=50
```

### Create Job

```http
POST /api/jobs
```

**Request Body:**
```json
{
  "name": "Daily Backup",
  "type": "backup",
  "config": {
    "include_docker_volumes": true,
    "destination": "/backups"
  }
}
```

### Run Job

```http
POST /api/jobs/{job_id}/run
```

### Cancel Job

```http
POST /api/jobs/{job_id}/cancel
```

### Get Job Logs

```http
GET /api/jobs/{job_id}/logs
```

---

## Alerts (`/api/alerts`)

### List Active Alerts

```http
GET /api/alerts?state=firing&severity=critical
```

### Alert Count

```http
GET /api/alerts/active/count
```

### Acknowledge Alert

```http
POST /api/alerts/{alert_id}/acknowledge
```

### Resolve Alert

```http
POST /api/alerts/{alert_id}/resolve
```

### List Alert Rules

```http
GET /api/alerts/rules
```

### Create Alert Rule

```http
POST /api/alerts/rules
```

**Request Body:**
```json
{
  "name": "High CPU Usage",
  "metric": "host.cpu.pct_total",
  "condition": "gt",
  "threshold": 90,
  "severity": "warning",
  "cooldown_minutes": 15
}
```

---

## Network (`/api/network`)

### List Interfaces

```http
GET /api/network/interfaces
```

### WiFi Networks

```http
GET /api/network/wifi/networks
```

### Connect WiFi

```http
POST /api/network/wifi/connect
```

**Request Body:**
```json
{
  "ssid": "MyNetwork",
  "password": "secret",
  "hidden": false
}
```

### Toggle WiFi

```http
POST /api/network/wifi/toggle?enable=false&rollback_seconds=120
```

---

## Devices (`/api/devices`)

### List All Devices

```http
GET /api/devices?type=esp
```

### List ESP Devices

```http
GET /api/devices/esp/list
```

### Send Command

```http
POST /api/devices/{device_id}/command
```

**Request Body:**
```json
{
  "command": "set_relay",
  "payload": {"state": true}
}
```

### GPIO Pins

```http
GET /api/devices/gpio/pins
```

### Write GPIO

```http
POST /api/devices/gpio/{pin}/write?value=1
```

---

## Admin Console (`/api/admin`)

### Execute Command

```http
POST /api/admin/console
```

**Request Body:**
```json
{
  "command": "docker ps",
  "mode": "safe",
  "timeout": 30
}
```

**Response:**
```json
{
  "success": true,
  "command": "docker ps",
  "output": "CONTAINER ID   IMAGE...",
  "exit_code": 0,
  "execution_time_ms": 125
}
```

### Enable Risky Mode

```http
POST /api/admin/risky/enable?duration_minutes=5
```

### Risky Mode Status

```http
GET /api/admin/risky/status
```

### Command History

```http
GET /api/admin/history?limit=50
```

### Quick Commands

```http
GET /api/admin/quick/system-info
GET /api/admin/quick/disk-usage
GET /api/admin/quick/docker-status
GET /api/admin/quick/service-status?service=nginx
```

---

## SSE Endpoints (`/api/sse`)

### Main Stream

```http
GET /api/sse/stream?channels=telemetry,resources,alerts
```

### Telemetry Stream

```http
GET /api/sse/telemetry
```

### Resource Updates

```http
GET /api/sse/resources
```

### Log Stream

```http
GET /api/sse/logs/{resource_id}
```

### Job Updates

```http
GET /api/sse/jobs/{job_id}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message here"
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing or invalid token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |
| 503 | Service Unavailable - Agent not connected |

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/api/auth/login` | 5/minute |
| `/api/*` (general) | 100/minute |
| `/api/admin/console` | 10/minute |
| `/api/devices/*/command` | 30/minute |

---

*Last Updated: 2024-01-15*
