# Threat Model - Pi Control Panel

## Overview

This document outlines the security threats, attack vectors, and mitigations for the Raspberry Pi Universal Control Panel. The system manages sensitive infrastructure and must be protected against both external and internal threats.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Attack Surface                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌───────────┐      ┌───────────┐      ┌───────────┐     │
│   │  Browser  │      │   Caddy   │      │   Panel   │     │
│   │   (Web)   │─────▶│  (Proxy)  │─────▶│   (API)   │     │
│   └───────────┘      └───────────┘      └─────┬─────┘     │
│                                                │           │
│                                          Unix Socket       │
│                                                │           │
│   ┌───────────┐      ┌───────────┐      ┌─────▼─────┐     │
│   │  ESP/IoT  │─────▶│ Mosquitto │─────▶│   Agent   │     │
│   │  Devices  │      │   (MQTT)  │      │   (Pi)    │     │
│   └───────────┘      └───────────┘      └───────────┘     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Threat Categories

### 1. Authentication & Authorization

| Threat | Severity | Mitigation |
|--------|----------|------------|
| Brute force password attacks | HIGH | Rate limiting (5 attempts/minute), account lockout |
| Session hijacking | HIGH | Secure HttpOnly cookies, short token expiry (15min) |
| Token replay attacks | MEDIUM | JWT with `iat` claim, token rotation |
| Privilege escalation | CRITICAL | RBAC enforcement at API level, role checks in middleware |
| Missing 2FA bypass | MEDIUM | TOTP required for admin actions |

### 2. API Security

| Threat | Severity | Mitigation |
|--------|----------|------------|
| SQL Injection | CRITICAL | Parameterized queries, input validation |
| XSS via API responses | HIGH | Content-Type headers, response sanitization |
| CSRF attacks | HIGH | SameSite cookies, CSRF tokens |
| API abuse/DoS | HIGH | Rate limiting (100 req/min), request size limits |
| Path traversal | CRITICAL | Input validation, allowlist file paths |

### 3. Command Execution

| Threat | Severity | Mitigation |
|--------|----------|------------|
| Command injection | CRITICAL | Allowlist commands, blacklist dangerous patterns |
| Privilege escalation via commands | CRITICAL | Safe mode by default, risky mode timeout |
| Resource exhaustion | HIGH | Command timeout, resource limits |
| Data exfiltration | HIGH | Audit logging, command output limits |

### 4. Network Security

| Threat | Severity | Mitigation |
|--------|----------|------------|
| Man-in-the-middle | CRITICAL | TLS everywhere, Tailscale for access |
| Unauthorized network access | HIGH | LAN-only by default, Tailscale ACLs |
| DNS spoofing | MEDIUM | DNSSEC, hardcoded IP fallbacks |
| DNS filter bypass | MEDIUM | Router DNS is manual, AdGuard managed locally, limitations documented |
| DNS query history exposure | HIGH | Query logs are admin-only and treated as browsing metadata |
| DNS service disruption | HIGH | Port 53 conflict checks, no automatic router/DHCP mutation |
| WiFi credential theft | HIGH | Encrypted storage, memory-only passwords |

### 5. MQTT/IoT Security

| Threat | Severity | Mitigation |
|--------|----------|------------|
| Unauthorized device access | HIGH | Client certificates, ACL per device |
| Telemetry spoofing | MEDIUM | Device authentication, message validation |
| Command injection via MQTT | CRITICAL | Payload validation, command allowlist |
| DoS via message flooding | MEDIUM | Rate limits per client, message size limits |

### 6. Data Security

| Threat | Severity | Mitigation |
|--------|----------|------------|
| Credential exposure | CRITICAL | Secrets in env vars, never in code |
| Backup theft | HIGH | AES-256-GCM encrypted backup archives, no plaintext Drive uploads |
| Cloud backup token exposure | HIGH | Google Drive `drive.file` scope, token stored locally with `0600` permissions |
| Backup encryption key loss | HIGH | Key file path documented; restore requires the local key |
| Log data leakage | MEDIUM | PII scrubbing, log rotation |
| Database tampering | HIGH | SQLite WAL mode, file permissions |

## Attack Vectors

### A1: External Web Attacker
- **Entry Point**: HTTPS via Caddy
- **Mitigations**: Tailscale-only access, rate limiting, auth required

### A2: Malicious ESP Device
- **Entry Point**: MQTT broker
- **Mitigations**: Per-device ACL, message validation, isolated topics

### A3: Compromised LAN Device
- **Entry Point**: Network broadcast, HTTP redirect
- **Mitigations**: HTTPS only, no HTTP on port 80, LAN isolation

### A3b: DNS Filtering Bypass
- **Entry Point**: Client uses hardcoded DNS, DoH/DoT, VPN, or first-party ad delivery
- **Mitigations**: Router/DHCP DNS points to the Pi, native AdGuard UI remains localhost-only, bypass limits are documented
- **Out of scope v1**: DHCP server replacement, firewall DNS hijacking, per-device parental profiles

### A3c: DNS Query Privacy Leak
- **Entry Point**: Authenticated user inspects LAN DNS query history
- **Mitigations**: Query log API and UI are admin-only, mutations are audit logged, native AdGuard UI is localhost-only
- **Residual Risk**: Admin users can still inspect DNS metadata by design; this must be treated like browsing history

### A3d: DNS Outage From Misconfiguration
- **Entry Point**: Port 53 conflict, broken upstream, or router DNS pointed to an unhealthy Pi
- **Mitigations**: Installer fails fast on port 53 conflicts, AdGuard upstream defaults to Cloudflare security DoH with bootstrap DNS, router DNS change remains manual
- **Residual Risk**: If the Pi is offline and the router only advertises the Pi as DNS, clients may lose DNS resolution until router DNS is changed or the Pi recovers

### A3e: Cloud Backup Exposure
- **Entry Point**: Google Drive account compromise, leaked OAuth token, or leaked backup archive
- **Mitigations**: Drive stores only `.tar.gz.enc` backup packages, archives are encrypted with AES-256-GCM before upload, OAuth uses the limited `drive.file` scope, panel setup and deletion endpoints are admin-only and audit logged
- **Residual Risk**: If an attacker also obtains `/etc/pi-control/backup_encryption.key`, backup databases and exports can be decrypted

### A3f: Backup Key Loss
- **Entry Point**: SD card loss, accidental deletion, or reinstall without preserving `/etc/pi-control/backup_encryption.key`
- **Mitigations**: Key path is documented in README and status API; encrypted archive format avoids server-side recovery paths by design
- **Residual Risk**: Existing Drive backups cannot be restored without the original key

### A4: Insider Threat (Operator)
- **Entry Point**: Authenticated API access
- **Mitigations**: RBAC, audit logging, CORE resource protection

### A5: Physical Access
- **Entry Point**: SD card, console access
- **Mitigations**: Disk encryption (optional), console password

## Security Controls

### Authentication
- [x] JWT with short expiry (15 minutes)
- [x] Refresh tokens with rotation
- [x] TOTP two-factor authentication
- [x] Password hashing (bcrypt)
- [x] Account lockout after failed attempts

### Authorization
- [x] Role-based access control (Admin/Operator/Viewer)
- [x] Resource class protection (CORE/SYSTEM/APP)
- [x] Per-endpoint role requirements
- [x] Action approval for sensitive operations

### Network
- [x] TLS termination at Caddy
- [x] Tailscale for secure remote access
- [x] No external ports exposed (internal service network)
- [x] Unix socket for Agent-Panel communication
- [x] Optional AdGuard Home DNS filtering with local-only management API
- [x] DNS query logs restricted to administrators

### Audit
- [x] All actions logged with user, IP, timestamp
- [x] Command execution history
- [x] Failed authentication logging
- [x] Retention policies for compliance
- [x] Backup setup, upload, disconnect, and remote delete actions are admin-only and audit logged

### Resource Protection
- [x] CORE services immutable
- [x] SYSTEM services limited to restart
- [x] Dangerous commands blacklisted
- [x] Safe mode for command execution

## Response Procedures

### Suspected Breach
1. Disable remote access (Tailscale connection)
2. Rotate JWT secret
3. Force logout all sessions
4. Review audit logs
5. Reset affected credentials

### Credential Leak
1. Rotate all secrets immediately
2. Regenerate JWT secret
3. Reset user passwords
4. Rotate MQTT passwords
5. Update ESP device credentials

### Ransomware/Malware
1. Disconnect from network
2. Boot from known-good image
3. Restore from encrypted backup using the original `/etc/pi-control/backup_encryption.key`
4. Audit all containers for tampering

### Google Drive Backup Credential Leak
1. Disconnect Google Drive from Archive > Backups
2. Revoke the app/token in the Google account security settings
3. Upload a new OAuth client if needed and re-authorize
4. Rotate the backup encryption key only after preserving any backups that must remain restorable

## Compliance Notes

- **GDPR**: Minimal PII collection, audit logs for accountability
- **SOC 2**: Audit logging, access controls, encryption
- **PCI-DSS**: Not applicable (no payment processing)

## Review Schedule

- [ ] Quarterly security review
- [ ] Annual penetration testing
- [ ] Post-incident review within 48 hours
- [ ] Dependency vulnerability scanning (CI/CD)

---

*Last Updated: 2026-05-11*
*Next Review: 2026-08-11*
