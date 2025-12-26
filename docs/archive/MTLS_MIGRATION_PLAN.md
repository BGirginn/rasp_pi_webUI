# MTLS_MIGRATION_PLAN.md
Version: 1.0
Scope: Migration from HMAC → mTLS (with temporary fallback).

## Phase 0: Preconditions
- Tailscale installed and up on Panel + Agent.
- Tailnet CA available (e.g., `tailscale cert` outputs).

## Phase 1: Provision Certificates
1. Generate Agent server cert/key:
   - `tailscale cert --cert-file /var/lib/tailscale/certs/agent.crt --key-file /var/lib/tailscale/certs/agent.key agent.ts.net`
2. Generate Panel client cert/key:
   - `tailscale cert --cert-file /var/lib/tailscale/certs/panel.crt --key-file /var/lib/tailscale/certs/panel.key panel.ts.net`
3. Capture tailnet CA:
   - Use tailnet CA file supplied by Tailscale (path varies by OS).

## Phase 2: Configure Agent (mTLS + fallback on)
1. Set `rpc.transport: tls`, `rpc.host` to a Tailscale IP, and `rpc.port`.
2. Set mTLS config:
   - `mtls.server_cert`, `mtls.server_key`, `mtls.client_ca`
   - `mtls.allowed_client_identities: ["panel.ts.net"]`
3. Keep fallback enabled for transition:
   - `security.allow_hmac_fallback: true`

## Phase 3: Configure Panel
1. Set env vars:
   - `AGENT_RPC_HOST=<agent-ts-ip>`
   - `AGENT_RPC_PORT=9443`
   - `AGENT_RPC_USE_TLS=true`
   - `AGENT_TLS_CA_FILE=/path/to/tailnet-ca.crt`
   - `AGENT_TLS_CLIENT_CERT=/path/to/panel.crt`
   - `AGENT_TLS_CLIENT_KEY=/path/to/panel.key`
   - `AGENT_TLS_SERVER_NAME=agent.ts.net`
   - `AGENT_TLS_EXPECTED_IDENTITIES=agent.ts.net`
2. Keep `PANEL_AGENT_SHARED_KEY` configured until cutover completes.

## Phase 4: Validate
- Confirm Panel connects via TLS and Agent logs show `mtls_authenticated: true`.
- Run security tests and verify audit consistency.

## Phase 5: Cutover (Disable HMAC)
1. Set `security.allow_hmac_fallback: false` on Agent.
2. Restart Agent, ensure Panel still connects.
3. Remove `PANEL_AGENT_SHARED_KEY` from Panel environment.

## Phase 6: Rotation Plan
- Identity-based rotation: issue new cert with same SAN and roll without downtime.
- Fingerprint pinning: add new fingerprint → deploy new cert → remove old.
