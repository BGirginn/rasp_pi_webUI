"""
Agent-side request authentication and integrity checks.
"""

import hashlib
import hmac
import json
import os
import time
from typing import Dict, List, Optional


class AuthError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def canonical_json(payload: Dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sign_envelope(secret: str, envelope: Dict) -> str:
    payload = canonical_json(envelope)
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()


def _load_shared_keys(config: dict) -> List[str]:
    keys: List[str] = []

    env_key = os.getenv("PANEL_AGENT_SHARED_KEY")
    if env_key:
        keys.append(env_key)

    env_keys = os.getenv("PANEL_AGENT_SHARED_KEYS")
    if env_keys:
        keys.extend([k.strip() for k in env_keys.split(",") if k.strip()])

    security = config.get("security", {})
    config_key = security.get("panel_shared_key")
    if config_key:
        keys.append(str(config_key))

    config_keys = security.get("panel_shared_keys", [])
    for key in config_keys:
        if key:
            keys.append(str(key))

    return list(dict.fromkeys(keys))


def verify_envelope(
    envelope: Dict,
    config: dict,
    now: Optional[float] = None,
    max_skew_seconds: Optional[int] = None,
    require_signature: bool = True,
) -> None:
    signature = envelope.get("signature")
    if require_signature:
        if not signature:
            raise AuthError("invalid_signature", "Missing signature")

    issued_at = envelope.get("issued_at")
    if not isinstance(issued_at, (int, float)):
        raise AuthError("invalid_params", "issued_at must be a unix timestamp")

    skew = max_skew_seconds
    if skew is None:
        skew = int(config.get("security", {}).get("clock_skew_seconds", 120))

    now_ts = time.time() if now is None else now
    if abs(now_ts - float(issued_at)) > skew:
        raise AuthError("expired_request", "Request timestamp outside allowed window")

    if require_signature:
        keys = _load_shared_keys(config)
        if not keys:
            raise AuthError("unauthorized", "Shared key not configured")

        unsigned = dict(envelope)
        unsigned.pop("signature", None)
        payload = canonical_json(unsigned)

        for key in keys:
            digest = hmac.new(key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
            if hmac.compare_digest(signature, digest):
                return

        raise AuthError("invalid_signature", "Invalid signature")
