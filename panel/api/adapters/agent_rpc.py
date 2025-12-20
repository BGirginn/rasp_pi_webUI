"""
Agent RPC Adapter
Thin wrapper around existing agent_client for AR handlers.
Reuses existing RPC protocol without modification per AI_RULES.md.
"""

from services.agent_client import agent_client as _agent_client


class AgentRPC:
    """
    Adapter for agent RPC communication.
    Wraps existing agent_client to provide clean interface for handlers.
    """
    
    def __init__(self):
        self._client = _agent_client
    
    async def get_system_info(self) -> dict:
        """Get system information."""
        try:
            return await self._client.get_system_info()
        except Exception as e:
            return {"error": str(e), "success": False}
    
    async def get_snapshot(self) -> dict:
        """Get metrics snapshot."""
        try:
            return await self._client.get_snapshot()
        except Exception as e:
            return {"error": str(e), "success": False}
    
    async def get_network_interfaces(self) -> dict:
        """Get network interfaces."""
        try:
            return await self._client.get_network_interfaces()
        except Exception as e:
            return {"error": str(e), "success": False}
    
    async def toggle_wifi(self, enabled: bool) -> dict:
        """Toggle WiFi on/off."""
        try:
            # Map to existing client method
            if hasattr(self._client, 'toggle_wifi'):
                return await self._client.toggle_wifi(enabled)
            else:
                # Fallback: call resource_action
                return await self._client.resource_action("wifi", "toggle", {"enabled": enabled})
        except Exception as e:
            return {"error": str(e), "success": False}
    
    async def resource_action(self, resource_id: str, action: str, params: dict = None) -> dict:
        """Execute action on a resource via agent."""
        try:
            return await self._client.resource_action(resource_id, action, params or {})
        except Exception as e:
            return {"error": str(e), "success": False}


# Singleton instance
agent_rpc = AgentRPC()
