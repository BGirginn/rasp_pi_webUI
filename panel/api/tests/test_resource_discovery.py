from routers.resources import _classify_service, _state_from_systemd
from routers.auth import hash_refresh_token


def test_adguard_is_manageable_application():
    assert _classify_service("AdGuardHome") == "APP"


def test_panel_and_access_services_are_protected():
    for name in ("pi-control", "pi-agent", "caddy", "ssh", "NetworkManager"):
        assert _classify_service(name) == "CORE"


def test_systemd_states_are_normalized():
    assert _state_from_systemd("active", "running") == "running"
    assert _state_from_systemd("inactive", "dead") == "stopped"
    assert _state_from_systemd("failed", "failed") == "failed"
    assert _state_from_systemd("deactivating", "stop") == "stopping"


def test_refresh_token_hash_supports_indexed_lookup():
    token = "high-entropy-refresh-token"
    assert hash_refresh_token(token) == hash_refresh_token(token)
    assert hash_refresh_token(token) != token
    assert len(hash_refresh_token(token)) == 64
