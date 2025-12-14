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
| Backup theft | HIGH | Encrypted backups, secure storage |
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
- [x] No external ports exposed (Docker internal network)
- [x] Unix socket for Agent-Panel communication

### Audit
- [x] All actions logged with user, IP, timestamp
- [x] Command execution history
- [x] Failed authentication logging
- [x] Retention policies for compliance

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
3. Restore from encrypted backup
4. Audit all containers for tampering

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

*Last Updated: 2024-01-15*
*Next Review: 2024-04-15*
