# AGENT_TRUST_MODEL.md
Version: 1.0
Scope: Panel ↔ Agent trust boundary, policy enforcement, replay/abuse resistance.

## 0) Non-goals
- Terminal/Raw exec geri gelmeyecek.
- Agent “genel amaçlı komut çalıştırıcı” olmayacak.
- Panel compromise durumunda “agent ile full kontrol” kabul edilmeyecek.

## 1) Threat Model (Agent Boundary)
### 1.1 Assumptions
- Panel WebUI/API compromise mümkündür.
- Network attacker (MITM) ihtimali vardır (özellikle LAN).
- Agent host üzerinde çalışır ve OS-level etkiler yaratabilir.
- Action-first model panelde enforced; agent tarafında da enforce edilmelidir.

### 1.2 Adversaries
A1) Compromised Panel (API key/JWT stolen, UI injected, admin browser hijacked)  
A2) Network attacker (replay/mitm)  
A3) Malicious/buggy client (API misuse)  
A4) Compromised Agent host (bu durumda containment hedeflenir, tam güvenlik değil)

### 1.3 Security Goals
G1) Panel compromise → agent üzerinde sınırsız etki üretmesin.  
G2) Agent yalnız allowlist aksiyonları uygulasın (deny-by-default).  
G3) Replay ve “aynı isteği tekrar oynatma” engellensin.  
G4) Audit zinciri kopmasın (en azından panel tarafında).  
G5) Fail-safe: doğrulanamayan istekler side-effect yaratmadan reddedilsin.

## 2) Trust Boundary: High-level Design
### 2.1 Principle
Agent, panelden gelen talepleri "talimat" değil "öneri" olarak görür.
Uygulama kararı agent policy’sine bağlıdır.

### 2.2 Required Properties
- Agent kendi registry/policy setine sahip olmalı.
- Agent, request’i schema ile doğrulamalı.
- Agent, kimlik doğrulaması + bütünlük doğrulaması yapmalı.
- Agent, replay koruması uygulamalı.
- Agent, minimum yetki ile çalışmalı.

## 3) Protocol: Panel → Agent Request Contract
### 3.1 Request Envelope (logical)
- action_id: string
- params: object
- requested_by: { user_id, username, role }
- request_id: uuid (panel üretir)
- issued_at: unix_ts
- nonce: random (agent replay cache için)
- signature: HMAC or mTLS identity (see 4)

### 3.2 Response Contract (logical)
- request_id
- status: success|failure
- error_code: stable enum
- message: human readable (safe)
- data: object (sanitized)
- agent_time: unix_ts

## 4) Authentication & Integrity
This repo is Tailscale-first; prefer transport that gives identity.

### 4.1 Phase A (Minimum): HMAC Signed Requests
- Shared secret: PANEL_AGENT_SHARED_KEY
- signature = HMAC_SHA256(secret, canonical_json(envelope_without_signature))
- Agent rejects:
  - missing/invalid signature
  - issued_at too old (clock skew window)
  - nonce reused (replay)

Pros: easy, works without TLS termination complexity  
Cons: shared secret management, rotation needed

### 4.2 Phase B (Preferred): mTLS (Pinned Certs)
- Agent exposes RPC only over localhost/tailscale interface
- Panel uses client cert pinned to agent
- Agent verifies client cert CN/OU mapped to “panel”

Pros: strong identity, no shared-secret replay issues  
Cons: cert lifecycle management

### 4.3 Rotation Policy
- HMAC secret rotation: add versioned keys (k1/k2 overlap window).
- mTLS rotation: overlapping validity, pinned fingerprint update step.

## 5) Replay & Abuse Protections
### 5.1 Replay
Agent maintains an in-memory (and optionally disk) cache:
- key: nonce
- ttl: 2–5 minutes
Reject if nonce exists.

Also validate:
- issued_at within ±(skew_window) (e.g., 120s)

### 5.2 Rate limiting
Per action_id + per caller identity (panel identity) rate limit:
- low-risk actions: higher
- high-risk actions: lower
- confirm-required: agent enforces its own cooldown too

### 5.3 Size limits
- params size cap (e.g., 16KB)
- deny deep nesting beyond N levels

## 6) Agent-side Policy Enforcement (Deny by Default)
### 6.1 Agent Registry
Agent contains its own registry (could mirror panel registry but must be independent):
- action_id
- schema (params)
- risk: low|med|high
- confirm_required: bool (agent respects this too)
- handler mapping (explicit)

### 6.2 Enforcement Rules
- If action_id not in agent registry → reject (404/unknown_action)
- If schema validation fails → reject (400/invalid_params)
- If risk=high and confirm_required and confirm token missing/invalid → reject
- If action is disabled/stub (e.g., updates.apply) → reject (403/disabled)

### 6.3 Confirm Token (Optional but recommended)
For high-risk actions:
- Panel performs /confirm flow and sends a short-lived confirm_token
- Agent validates confirm_token signature + scope:
  - action_id bound
  - params hash bound
  - expiry

This prevents “panel compromised later” from replaying old confirms.

## 7) Error Codes (Stable)
- unknown_action
- invalid_params
- unauthorized
- invalid_signature
- replay_detected
- expired_request
- action_disabled
- rate_limited
- internal_error

## 8) Observability & Audit
### 8.1 Minimal logging (agent)
Agent logs:
- request_id
- action_id
- result status
- error_code
No secrets, no raw sensitive params.

### 8.2 Correlation
Panel audit log stores:
- request_id
- action_id
- masked params
- user identity
Agent returns request_id back so logs correlate.

## 9) Network Binding Rules
- Agent RPC binds to:
  - localhost only OR
  - tailscale interface only
Never 0.0.0.0.

Firewall must block non-tailscale inbound.

## 10) Least Privilege
- Agent runs as dedicated user.
- Use sudoers with explicit allowlist if root actions are required.
- Prefer systemd dbus / polkit scoped rules over blanket sudo.

## 11) Implementation Plan (Concrete)
### 11.1 Agent
- Add `agent/policy/registry.yaml` (agent allowlist)
- Add `agent/policy/validate.py` (schema validation)
- Add `agent/security/auth.py` (HMAC/mTLS verification)
- Add `agent/security/replay.py` (nonce cache)
- Enforce in the RPC entrypoint: auth → replay → validate → handler

### 11.2 Panel
- Add envelope fields: request_id, issued_at, nonce, signature
- Add shared key config & rotation mechanism (Phase A)
- Add confirm_token binding to action_id+params hash (optional)

### 11.3 Tests
- Panel unit tests:
  - signature generation stable
- Agent unit tests:
  - invalid signature rejected
  - replay rejected
  - unknown_action rejected
  - invalid params rejected
  - confirm_required w/out confirm_token rejected
- Integration test:
  - end-to-end execute action via panel adapter to agent stub

## 12) Exit Criteria
Agent boundary is considered “done” when:
- All deny-by-default enforcement is present
- Replay + auth is enforced
- At least 10 security-focused tests exist and pass
- Agent is not reachable from non-local/non-tailscale interfaces
