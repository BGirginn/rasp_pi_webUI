"""
Panel TLS validation helpers.
"""

import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from services.agent_tls import TLSValidationError, fingerprint_sha256, validate_server_certificate


FIXTURES_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "mtls"


def _load_cert(path: Path) -> dict:
    return ssl._ssl._test_decode_cert(str(path))


def _fingerprint(path: Path) -> str:
    pem_bytes = path.read_bytes()
    der = ssl.PEM_cert_to_DER_cert(pem_bytes.decode("utf-8"))
    return fingerprint_sha256(der)


def test_server_identity_allowed():
    cert = _load_cert(FIXTURES_DIR / "agent.crt")
    fp = _fingerprint(FIXTURES_DIR / "agent.crt")

    validate_server_certificate(
        cert,
        fp,
        expected_identities=["agent.ts.net"],
    )


def test_server_identity_rejected():
    cert = _load_cert(FIXTURES_DIR / "agent.crt")
    fp = _fingerprint(FIXTURES_DIR / "agent.crt")

    with pytest.raises(TLSValidationError):
        validate_server_certificate(
            cert,
            fp,
            expected_identities=["other.ts.net"],
        )


def test_server_certificate_expired():
    cert = _load_cert(FIXTURES_DIR / "agent.crt")
    fp = _fingerprint(FIXTURES_DIR / "agent.crt")

    not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    future = not_after + timedelta(seconds=1)

    with pytest.raises(TLSValidationError):
        validate_server_certificate(
            cert,
            fp,
            expected_identities=["agent.ts.net"],
            now=future,
        )
