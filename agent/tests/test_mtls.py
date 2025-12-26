"""
Agent mTLS validation tests.
"""

import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from security.auth import AuthError
from security.mtls import fingerprint_sha256, validate_client_certificate

pytestmark = pytest.mark.invariant


FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "mtls"


def _load_cert(path: Path) -> dict:
    return ssl._ssl._test_decode_cert(str(path))


def _fingerprint(path: Path) -> str:
    pem_bytes = path.read_bytes()
    der = ssl.PEM_cert_to_DER_cert(pem_bytes.decode("utf-8"))
    return fingerprint_sha256(der)


def test_client_identity_allowed():
    cert = _load_cert(FIXTURES_DIR / "panel.crt")
    fp = _fingerprint(FIXTURES_DIR / "panel.crt")

    validate_client_certificate(
        cert,
        fp,
        allowed_identities=["panel.ts.net"],
    )


def test_client_identity_rejected():
    cert = _load_cert(FIXTURES_DIR / "intruder.crt")
    fp = _fingerprint(FIXTURES_DIR / "intruder.crt")

    with pytest.raises(AuthError):
        validate_client_certificate(
            cert,
            fp,
            allowed_identities=["panel.ts.net"],
        )


def test_client_fingerprint_rejected():
    cert = _load_cert(FIXTURES_DIR / "panel-rotated.crt")
    fp = _fingerprint(FIXTURES_DIR / "panel-rotated.crt")
    allowed_fp = _fingerprint(FIXTURES_DIR / "panel.crt")

    with pytest.raises(AuthError):
        validate_client_certificate(
            cert,
            fp,
            allowed_fingerprints=[allowed_fp],
        )


def test_client_certificate_expired():
    cert = _load_cert(FIXTURES_DIR / "panel.crt")
    fp = _fingerprint(FIXTURES_DIR / "panel.crt")

    not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    future = not_after + timedelta(seconds=1)

    with pytest.raises(AuthError):
        validate_client_certificate(
            cert,
            fp,
            allowed_identities=["panel.ts.net"],
            now=future,
        )
