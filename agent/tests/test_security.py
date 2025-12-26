"""
Agent security and policy enforcement tests.
"""

import importlib.util
import time
from pathlib import Path

import pytest

from policy.validate import PolicyError, enforce_action
from security.auth import AuthError, sign_envelope, verify_envelope
from security.replay import ReplayCache, ReplayError

pytestmark = pytest.mark.invariant


TEST_REGISTRY = {
    "actions": [
        {"id": "system.health", "params_schema": {}, "confirm_required": False},
        {"id": "test.params", "params_schema": {"count": {"type": "integer"}}, "confirm_required": False},
        {"id": "test.confirm", "params_schema": {}, "confirm_required": True},
    ],
    "targets": {},
}


def _make_envelope():
    envelope = {
        "action_id": "system.health",
        "params": {},
        "requested_by": {"user_id": "1", "username": "alice", "role": "admin"},
        "request_id": "req-123",
        "issued_at": 1700000000,
        "nonce": "nonce-abc",
    }
    envelope["signature"] = sign_envelope("test-secret", envelope)
    return envelope


def test_invalid_signature_rejected():
    envelope = _make_envelope()
    envelope["signature"] = "bad-signature"
    with pytest.raises(AuthError) as exc:
        verify_envelope(
            envelope,
            {"security": {"panel_shared_key": "test-secret"}},
            now=1700000000,
            max_skew_seconds=120,
        )
    assert exc.value.code == "invalid_signature"


@pytest.mark.asyncio
async def test_replay_rejected():
    cache = ReplayCache(ttl_seconds=300)
    await cache.check_and_store("nonce-1", now=1700000000)
    with pytest.raises(ReplayError) as exc:
        await cache.check_and_store("nonce-1", now=1700000001)
    assert exc.value.code == "replay_detected"


def test_unknown_action_rejected():
    with pytest.raises(PolicyError) as exc:
        enforce_action(TEST_REGISTRY, "missing.action", params={}, confirm_token=None)
    assert exc.value.code == "unknown_action"


def test_invalid_params_rejected():
    with pytest.raises(PolicyError) as exc:
        enforce_action(TEST_REGISTRY, "test.params", params={"count": "nope"}, confirm_token=None)
    assert exc.value.code == "invalid_params"


def test_confirm_required_without_token_rejected():
    with pytest.raises(PolicyError) as exc:
        enforce_action(TEST_REGISTRY, "test.confirm", params={}, confirm_token=None)
    assert exc.value.code == "unauthorized"


@pytest.mark.asyncio
async def test_replay_enforced_with_mtls():
    agent_path = Path(__file__).resolve().parents[1] / "pi-agent.py"
    spec = importlib.util.spec_from_file_location("pi_agent_module", agent_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    agent = module.PiAgent(config_path="missing-agent-config.yaml")
    agent.allow_hmac_fallback = False

    envelope = {
        "action_id": "system.health",
        "params": {},
        "requested_by": {"user_id": "1", "username": "alice", "role": "admin"},
        "request_id": "req-1",
        "issued_at": int(time.time()),
        "nonce": "nonce-1",
    }

    first = await agent._handle_rpc("system.health", envelope, client_info={"mtls_authenticated": True})
    assert "result" in first

    envelope["request_id"] = "req-2"
    second = await agent._handle_rpc("system.health", envelope, client_info={"mtls_authenticated": True})
    assert second["error"]["code"] == "replay_detected"
