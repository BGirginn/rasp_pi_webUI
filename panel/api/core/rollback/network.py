"""
Network rollback helpers.
"""

from typing import Optional, Tuple

from adapters.agent_rpc import agent_rpc


async def _get_wifi_enabled() -> Optional[bool]:
    """Determine WiFi state from agent network interfaces."""
    try:
        interfaces = await agent_rpc.get_network_interfaces()
    except Exception:
        return None

    if isinstance(interfaces, dict):
        if interfaces.get("success") is False:
            return None
        interfaces = interfaces.get("data") or []

    if not isinstance(interfaces, list):
        return None

    for iface in interfaces:
        if not isinstance(iface, dict):
            continue
        name = iface.get("name", "")
        iface_type = iface.get("type", "")
        if iface_type == "wifi" or name.startswith("wlan"):
            state = iface.get("state", "").lower()
            return state in {"running", "up", "online", "active"}

    return None


async def determine_rollback_plan(action_id: str, params: dict) -> Optional[Tuple[str, dict]]:
    """Return rollback action_id and payload for network actions."""
    if action_id == "net.toggle_wifi":
        current_state = await _get_wifi_enabled()
        if current_state is None:
            return None
        return "net.toggle_wifi", {"enabled": not current_state}

    if action_id == "net.reset_safe":
        return "emergency.rollback_last_network_change", {}

    return None
