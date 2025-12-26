"""
Mutual TLS helpers for Panel ↔ Agent identity validation.
"""

import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .auth import AuthError


def fingerprint_sha256(cert_der: bytes) -> str:
    return hashlib.sha256(cert_der).hexdigest()


def extract_identities(peer_cert: Dict) -> List[str]:
    identities: List[str] = []

    for entry in peer_cert.get("subjectAltName", []):
        if len(entry) != 2:
            continue
        kind, value = entry
        if kind in ("DNS", "IP Address"):
            identities.append(value)

    for subject in peer_cert.get("subject", []):
        for key, value in subject:
            if key == "commonName":
                identities.append(value)

    return identities


def _parse_cert_time(value: str) -> datetime:
    # Example: "Jun 20 12:00:00 2025 GMT"
    return datetime.strptime(value, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)


def validate_cert_dates(peer_cert: Dict, now: Optional[datetime] = None) -> None:
    if not peer_cert:
        raise AuthError("unauthorized", "Client certificate required")

    not_before = peer_cert.get("notBefore")
    not_after = peer_cert.get("notAfter")
    if not not_before or not not_after:
        raise AuthError("unauthorized", "Client certificate missing validity window")

    now_dt = now or datetime.now(timezone.utc)
    nb = _parse_cert_time(not_before)
    na = _parse_cert_time(not_after)

    if now_dt < nb:
        raise AuthError("unauthorized", "Client certificate not yet valid")
    if now_dt > na:
        raise AuthError("unauthorized", "Client certificate expired")


def _normalize_list(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    return [v.strip() for v in values if v and v.strip()]


def validate_client_certificate(
    peer_cert: Dict,
    fingerprint: str,
    *,
    allowed_identities: Optional[List[str]] = None,
    allowed_fingerprints: Optional[List[str]] = None,
    now: Optional[datetime] = None,
) -> None:
    validate_cert_dates(peer_cert, now=now)

    identities = extract_identities(peer_cert)
    allowed_identities = _normalize_list(allowed_identities)
    allowed_fingerprints = [fp.lower() for fp in _normalize_list(allowed_fingerprints)]

    if not allowed_identities and not allowed_fingerprints:
        raise AuthError("unauthorized", "No allowed client identities configured")

    if allowed_identities:
        if not any(identity in allowed_identities for identity in identities):
            raise AuthError("unauthorized", "Client identity not allowed")

    if allowed_fingerprints:
        if fingerprint.lower() not in allowed_fingerprints:
            raise AuthError("unauthorized", "Client fingerprint not allowed")


def validate_server_certificate(
    peer_cert: Dict,
    fingerprint: str,
    *,
    expected_identities: Optional[List[str]] = None,
    expected_fingerprints: Optional[List[str]] = None,
    now: Optional[datetime] = None,
) -> None:
    validate_cert_dates(peer_cert, now=now)

    identities = extract_identities(peer_cert)
    expected_identities = _normalize_list(expected_identities)
    expected_fingerprints = [fp.lower() for fp in _normalize_list(expected_fingerprints)]

    if expected_identities:
        if not any(identity in expected_identities for identity in identities):
            raise AuthError("unauthorized", "Server identity not allowed")

    if expected_fingerprints:
        if fingerprint.lower() not in expected_fingerprints:
            raise AuthError("unauthorized", "Server fingerprint not allowed")
