"""
Panel ↔ Agent signing helpers.
"""

from services.agent_client import canonical_json, sign_envelope


def test_agent_signature_stable():
    envelope = {
        "action_id": "system.info",
        "params": {"count": 2, "foo": "bar"},
        "requested_by": {"user_id": 1, "username": "alice", "role": "admin"},
        "request_id": "123e4567-e89b-12d3-a456-426614174000",
        "issued_at": 1700000000,
        "nonce": "abc123",
    }
    expected_json = (
        '{"action_id":"system.info","issued_at":1700000000,'
        '"nonce":"abc123","params":{"count":2,"foo":"bar"},'
        '"request_id":"123e4567-e89b-12d3-a456-426614174000",'
        '"requested_by":{"role":"admin","user_id":1,"username":"alice"}}'
    )

    assert canonical_json(envelope) == expected_json
    assert sign_envelope("test-secret", envelope) == (
        "259b9f44610e9a035367fc8a66c5ef637457e2d44122f4bdaebe380322be3b89"
    )
