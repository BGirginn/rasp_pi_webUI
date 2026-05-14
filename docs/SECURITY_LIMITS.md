# Security Limits - Pi Control Panel

This document defines the operational security limits and boundaries enforced by the Pi Control Panel.

## Resource Classification

Resources are classified into four tiers with different protection levels:

| Class | Description | Allowed Actions | Protected |
|-------|-------------|-----------------|-----------|
| **CORE** | Critical system services (sshd, network, kernel) | View only | ✅ Immutable |
| **SYSTEM** | Important services (mosquitto, panel) | Restart only | ✅ Limited |
| **APP** | User applications and services | Full control | ❌ Standard |
| **DEVICE** | ESP/IoT devices | Send commands | ❌ Standard |

### CORE Services (Never Modifiable)

These services cannot be stopped, restarted, or modified through the UI:

```yaml
core_services:
  - sshd             # SSH daemon
  - systemd-*        # systemd core services
  - dbus             # D-Bus message bus
  - journald         # Journal logging
  - networkd         # Network management
  - resolved         # DNS resolver
  - tailscaled       # Tailscale VPN
  - kernel           # Kernel processes
```

### SYSTEM Services (Restart Only)

These services can only be restarted by administrators:

```yaml
system_services:
  - mosquitto        # MQTT broker
  - caddy            # Reverse proxy
  - pi-agent         # Control agent
  - panel            # Control panel
```

## Role-Based Access Control

### Roles

| Role | Description | Permissions |
|------|-------------|-------------|
| **Admin** | Full system access | All operations |
| **Operator** | Day-to-day operations | APP control, view all |
| **Viewer** | Read-only monitoring | View only |

### Permission Matrix

| Action | Admin | Operator | Viewer |
|--------|:-----:|:--------:|:------:|
| View dashboard | ✅ | ✅ | ✅ |
| View resources | ✅ | ✅ | ✅ |
| View telemetry | ✅ | ✅ | ✅ |
| View logs | ✅ | ✅ | ✅ |
| View alerts | ✅ | ✅ | ✅ |
| Acknowledge alerts | ✅ | ✅ | ❌ |
| Restart APP services | ✅ | ✅ | ❌ |
| Restart SYSTEM services | ✅ | ❌ | ❌ |
| Modify CORE services | ❌ | ❌ | ❌ |
| Send device commands | ✅ | ✅ | ❌ |
| Run jobs | ✅ | ✅ | ❌ |
| Cancel jobs | ✅ | ❌ | ❌ |
| Manage users | ✅ | ❌ | ❌ |
| Modify alert rules | ✅ | ❌ | ❌ |
| Network settings | ✅ | ❌ | ❌ |
| Admin console (safe) | ✅ | ❌ | ❌ |
| Admin console (risky) | ✅ | ❌ | ❌ |
| View audit logs | ✅ | ❌ | ❌ |

## Rate Limits

### API Rate Limits

| Endpoint Category | Limit | Window |
|-------------------|-------|--------|
| Authentication | 5 requests | 1 minute |
| API (general) | 100 requests | 1 minute |
| SSE connections | 5 per user | concurrent |
| Admin console | 10 commands | 1 minute |
| Device commands | 30 commands | 1 minute |

### MQTT Rate Limits

| Limit | Value |
|-------|-------|
| Max connections per client | 1 |
| Max inflight messages | 10 |
| Max queued messages | 100 |
| Max message size | 256 KB |
| Message rate | 100/sec per client |

## Command Execution Limits

### Safe Mode (Default)

Commands in safe mode are restricted to a predefined allowlist:

```yaml
allowed_patterns:
  # Read-only system info
  - "systemctl status"
  - "journalctl"
  - "systemctl status"
  - "journalctl -u"
  - "df"
  - "free"
  - "uptime"
  - "top -bn1"
  - "ip addr"
  - "ping"
  # ... (see full list in admin_console.py)
```

### Risky Mode

Risky mode allows additional commands but still blocks dangerous patterns:

```yaml
blocked_patterns:
  - "rm -rf /"
  - "dd if=/dev/zero of=/dev/sd*"
  - "mkfs /dev/sd*"
  - ":(){ :|:& };:"  # Fork bomb
  - "chmod -R 777 /"
  - "shutdown"
  - "reboot"
  - "halt"
  - "wget * | sh"
  - "curl * | sh"
```

### Risky Mode Limits

| Limit | Value |
|-------|-------|
| Max session duration | 30 minutes |
| Default session duration | 5 minutes |
| Max command length | 1000 characters |
| Max command timeout | 60 seconds |
| Required role | Admin only |

## Network Security Limits

### Access Control

| Access Type | Default | Configurable |
|-------------|---------|--------------|
| LAN access | Allowed | ✅ |
| Tailscale access | Allowed | ✅ |
| Public internet | Blocked | ❌ |
| HTTP (port 80) | Redirect only | ❌ |
| HTTPS (port 443) | Required | ❌ |

### WiFi Toggle Safeguards

```yaml
wifi_toggle:
  # Critical interface protection
  critical_interfaces:
    - eth0
    - tailscale0
  
  # Rollback requirements
  disable_requires_rollback: true
  max_rollback_duration: 300 seconds
  auto_rollback_on_disconnect: true
```

### DNS Filtering Safeguards

```yaml
dns_filter:
  engine: AdGuard Home
  install_mode: opt-in (--with-adguard)
  dns_listener: "0.0.0.0:53"
  admin_ui_listener: "127.0.0.1:3000"
  credentials_file: "/etc/pi-control/pi-control.env"
  credentials_mode: "0600"
  router_dns_changes: manual_only
  port_53_conflict_policy: fail_fast
  dhcp_server_mode: out_of_scope_v1
  dns_hijack: out_of_scope_v1
  per_device_parental_profiles: out_of_scope_v1
```

Only administrators can change protection toggles, managed block/allow rules, view DNS query logs, or clear the DNS cache. DNS query logs are treated as browsing metadata. Viewers and operators can view service status and run single-domain checks, but cannot inspect recent LAN DNS history. Native AdGuard Home web/API access is not exposed on LAN by Caddy; the panel talks to the local API with credentials stored in `/etc/pi-control/pi-control.env`.

The installer refuses `--with-adguard` when port 53 is already owned by another process. Common conflicts include `systemd-resolved`, `dnsmasq`, and `pihole-FTL`.

### CORS Configuration

```yaml
cors:
  allowed_origins:
    - "https://*.tail-net"
    - "http://localhost:*"  # Dev only
  allowed_methods:
    - GET
    - POST
    - PUT
    - DELETE
  credentials: true
```

## Data Retention Limits

### Telemetry

| Data Type | Retention | Cleanup |
|-----------|-----------|---------|
| Raw metrics | 90 days | Hourly |
| Summary metrics | 90 days | Daily |

### Logs

| Log Type | Retention | Cleanup |
|----------|-----------|---------|
| Application logs | 7 days | Daily |
| Audit logs | 90 days | Weekly |
| Alert history | 90 days | Weekly |
| Job logs | 30 days | Daily |

### Sessions

| Session Type | Expiry |
|--------------|--------|
| Access token | 15 minutes |
| Refresh token | 7 days |
| TOTP grace period | 30 seconds |
| Account lockout | 15 minutes |

## Resource Limits

### Agent Limits

```yaml
agent:
  max_memory: 256 MB
  max_cpu: 50%
  max_worker_processes: 4
  socket_permissions: 660
  discovery_interval: 60 seconds
  telemetry_batch_size: 100
```

### Panel Limits

```yaml
panel:
  max_request_size: 10 MB
  max_upload_size: 100 MB
  websocket_connections: 100
  database_connections: 5
  worker_processes: 2
```

### Container Limits

```yaml
services:
  caddy:
    memory: 128 MB
    cpus: 0.5
  
  panel:
    memory: 512 MB
    cpus: 1.0
    read_only: true
  
  mosquitto:
    memory: 64 MB
    cpus: 0.25
```

## Backup Limits

| Limit | Value |
|-------|-------|
| Max backup size | 1 GB |
| Max concurrent backups | 1 |
| Backup timeout | 30 minutes |
| Backup file retention | 90 days local and Google Drive |
| Backup encryption | AES-256-GCM |

Google Drive backups use the `drive.file` scope and store only encrypted `pi-control_backup_*.tar.gz.enc` archives in the configured Drive folder. Plain SQLite databases and export files are never uploaded. The OAuth client file, OAuth token, and backup encryption key are stored under `/etc/pi-control` with `0600` file permissions. Administrators can upload the OAuth client, start or disconnect authorization, trigger encrypted backups, list Drive backup files, and delete Pi Control backup files from Drive.

The encryption key remains local to the Pi. If `/etc/pi-control/backup_encryption.key` is lost, existing Drive backups cannot be decrypted. If the Pi is fully compromised, an attacker with root or app-user access may be able to read the token and encryption key and should be assumed capable of accessing backup contents after decryption.

## Alert Limits

| Limit | Value |
|-------|-------|
| Max active alerts | 100 |
| Max alert rules | 50 |
| Min cooldown period | 5 minutes |
| Max notification retries | 3 |
| Alert history retention | 90 days |

## Job Limits

| Limit | Value |
|-------|-------|
| Max concurrent jobs | 3 |
| Default job timeout | 30 minutes |
| Max job timeout | 120 minutes |
| Failed job retention | 30 days |
| Max job log size | 10 MB |

---

## Violation Handling

When limits are exceeded:

1. **Rate Limits**: Return 429 Too Many Requests, retry after header
2. **Permission Denied**: Return 403 Forbidden, log attempt
3. **Resource Limits**: Graceful degradation, alert operators
4. **Command Blocked**: Return 403, log with full command

## Override Procedures

Certain limits can be overridden by administrators:

1. Create override request with justification
2. Review by second administrator (if available)
3. Apply temporary override with expiration
4. Log all override usage
5. Review at next security audit

---

*Last Updated: 2024-01-15*
