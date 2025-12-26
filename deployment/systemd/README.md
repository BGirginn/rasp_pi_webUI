# Systemd Service Deployment Notes

## Service Overview

### pi-panel-api.service
- **Purpose**: Panel API server
- **User**: DynamicUser (ephemeral, no persistent home)
- **Capabilities**: None (fully restricted)
- **Network**: Binds to 127.0.0.1:8000 only
- **Database**: /var/lib/pi-panel/control.db

### pi-agent.service
- **Purpose**: System control agent
- **User**: pi-agent (persistent, created during install)
- **Capabilities**: CAP_NET_ADMIN, CAP_SYS_ADMIN (minimal for systemd/network)
- **Network**: Binds to 127.0.0.1:8001 only
- **State**: /var/lib/pi-agent/state.json

## Hardening Features

Both services implement defense-in-depth:

1. **Privilege Reduction**
   - NoNewPrivileges=yes (can't escalate)
   - Minimal capability sets
   - Non-root execution

2. **Filesystem Isolation**
   - ProtectSystem=strict/full (read-only /usr, /boot)
   - ProtectHome=yes (no /home access)
   - PrivateTmp=yes (isolated /tmp)
   - ReadWritePaths limited to data directories

3. **Network Restrictions**
   - RestrictAddressFamilies limits socket types
   - Bind to localhost only (configured separately)

4. **System Call Filtering**
   - SystemCallFilter restricts dangerous syscalls
   - Blocks @privileged, @resources for panel
   - Agent allows controlled system access

5. **Namespace Isolation**
   - PrivateDevices, ProtectKernelTunables, etc.
   - MemoryDenyWriteExecute (no runtime code gen)

6. **IPC/SUID Protection**
   - RemoveIPC=yes
   - RestrictSUIDSGID=yes

## Installation

```bash
# Copy units
sudo cp deployment/systemd/*.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable pi-panel-api
sudo systemctl enable pi-agent

# Start services
sudo systemctl start pi-agent
sudo systemctl start pi-panel-api
```

## Verification

```bash
# Check status
sudo systemctl status pi-panel-api
sudo systemctl status pi-agent

# View logs
sudo journalctl -u pi-panel-api -f
sudo journalctl -u pi-agent -f

# Verify security
sudo systemd-analyze security pi-panel-api
sudo systemd-analyze security pi-agent
# Expected: High score (9.5+/10 for panel, 7+/10 for agent)
```

## Common Commands

```bash
# Restart
sudo systemctl restart pi-panel-api
sudo systemctl restart pi-agent

# Stop
sudo systemctl stop pi-panel-api
sudo systemctl stop pi-agent

# Disable (won't start on boot)
sudo systemctl disable pi-panel-api
sudo systemctl disable pi-agent

# View environment
sudo systemctl show pi-panel-api --property=Environment
```

## Troubleshooting

### Service won't start
```bash
# Check for errors
sudo journalctl -xeu pi-panel-api

# Verify file permissions
ls -la /var/lib/pi-panel
ls -la /etc/pi-panel

# Check config syntax
cd /opt/pi-panel/api
python3 -c "from config import settings; print(settings)"
```

### Permission denied errors
- Verify StateDirectory exists
- Check ReadWritePaths in unit file
- Ensure database file is accessible

### Network binding fails
- Verify port not already in use: `sudo ss -tlnp | grep 8000`
- Check config.yaml has correct bind address
- Ensure firewall allows localhost connections
