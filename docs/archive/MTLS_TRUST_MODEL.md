# MTLS_TRUST_MODEL.md
Version: 1.0
Scope: Panel ↔ Agent mTLS trust boundary, identity mapping, and rotation.

## 1) Trust Boundary
All Panel → Agent RPC traffic moves to mTLS over Tailscale.
The Agent rejects non‑mTLS traffic unless `security.allow_hmac_fallback` is explicitly enabled.

## 2) Identity Mapping
### 2.1 Agent (server) identity
- Verified by Panel via:
  - `AGENT_TLS_CA_FILE` (tailnet CA) + hostname verification, and
  - optional `AGENT_TLS_EXPECTED_FINGERPRINTS`.
- Expected identities are configured via `AGENT_TLS_EXPECTED_IDENTITIES` (SAN DNS / CN).

### 2.2 Panel (client) identity
- Verified by Agent via:
  - `mtls.client_ca` (tailnet CA),
  - `mtls.allowed_client_identities` (SAN DNS / CN),
  - optional `mtls.allowed_client_fingerprints`.

## 3) Trust Anchors
- Primary: Tailnet CA (recommended).
- Optional: fingerprint pinning for additional hardening.

## 4) Rotation Without Downtime
### 4.1 Identity-based (recommended)
- Keep `mtls.allowed_client_identities` stable (e.g., `panel.ts.net`).
- Issue new certs from the same CA; both old and new remain valid until expiry.
- No config changes required if identities remain constant.

### 4.2 Fingerprint pinning (stricter)
- Add new fingerprint to allowlist before rotation.
- Deploy new cert.
- Remove old fingerprint after rollout completes.

## 5) Failure Modes (Explicit)
- Missing/invalid client cert → connection rejected.
- Expired cert → connection rejected.
- Identity/fingerprint mismatch → request rejected.
- Non‑mTLS traffic → rejected unless fallback is enabled.
