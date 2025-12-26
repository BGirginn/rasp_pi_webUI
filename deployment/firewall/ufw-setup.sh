#!/bin/bash
# UFW Firewall Setup for Pi Control Panel
# Alternative to nftables for users familiar with UFW

set -e

echo "Setting up UFW firewall..."

# Reset UFW to clean state
sudo ufw --force reset

# Default policies: deny incoming, allow outgoing
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow loopback
sudo ufw allow in on lo

# Allow SSH from Tailscale interface only
# Note: Replace 'tailscale0' with your actual Tailscale interface if different
sudo ufw allow in on tailscale0 to any port 22 proto tcp comment 'SSH via Tailscale'

# Deny direct access to Panel/Agent ports from external interfaces
# (They bind to localhost anyway, but defense in depth)
sudo ufw deny 8000/tcp comment 'Block external Panel API'
sudo ufw deny 8001/tcp comment 'Block external Agent RPC'

# Enable UFW
sudo ufw --force enable

# Show status
echo ""
echo "UFW firewall configured successfully!"
echo ""
sudo ufw status verbose

echo ""
echo "IMPORTANT: Verify you can still access SSH via Tailscale before closing this session!"
echo "Test with: ssh pi@\$(tailscale ip -4)"
