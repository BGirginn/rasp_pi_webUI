import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import sys
import os

# Add parent directory to path so we can import main
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from routers.auth import get_current_user

# Mock auth
async def mock_get_current_user():
    return {"id": 1, "role": "admin", "username": "admin"}

app.dependency_overrides[get_current_user] = mock_get_current_user

client = TestClient(app)

@pytest.mark.asyncio
async def test_service_action_calls_correct_method():
    """
    Verify that execute_action endpoint calls agent_client.resource_action
    instead of the non-existent execute_action.
    """
    # Patch the agent_client instance where it is used in resources.py
    # Note: We patch 'routers.resources.agent_client' because that's where the name is bound
    with patch("routers.resources.agent_client") as mock_agent:
        # Setup the mock to behave like the real AgentClient
        # We give it a resource_action method
        mock_agent.resource_action = AsyncMock(return_value={"success": True})
        
        # Explicitly ensure execute_action raises AttributeError if accessed,
        # mirroring the real class behavior (it doesn't have it).
        # Wrapper to simulate missing attribute
        def raise_attr_error(*args, **kwargs):
            raise AttributeError("'AgentClient' object has no attribute 'execute_action'")
        
        # If the code tries to access execute_action, we want to know (test failure in a way)
        # But actually, 'Mock' objects create attributes on access.
        # So we can just check asserts later.
        
        # Also need to mock DB because the router tries to query it
        with patch("routers.resources.get_control_db") as mock_get_db:
             mock_db = AsyncMock()
             mock_get_db.return_value = mock_db
             # fetchone for "SELECT ... FROM resources"
             # Return None to simulate resource not in DB, triggering systemd fallback logic
             mock_db.execute.return_value.fetchone = AsyncMock(return_value=None)
             
             # Also mock the commit/execute for audit log
             mock_db.commit = AsyncMock()

             response = client.post(
                 "/api/resources/systemd-testservice/action",
                 json={"action": "restart"}
             )
             
             # If the code still calls execute_action, the Mock would implicitly create it.
             # So we must verify resource_action WAS called.
             # And we can verify execute_action was NOT called.
             
             assert response.status_code == 200, f"Response: {response.text}"
             data = response.json()
             assert data["success"] is True
             
             # Verify resource_action was called
             mock_agent.resource_action.assert_called_once()
             
             # Verify arguments: service_name + .service
             args, _ = mock_agent.resource_action.call_args
             assert args[0] == "testservice.service"
             assert args[1] == "restart"
             
             # Verify checking for execute_action calls
             # By default, a Mock creates attributes when accessed.
             # If the code called execute_action, it would be a separate mock object.
             # We can check if it was attached.
             # Using spec=AgentClient would be better but we don't want to import the real class if we can avoid complex setup.
             # Simple check:
             assert not getattr(mock_agent, "execute_action", MagicMock()).called, "execute_action should not be called"

from unittest.mock import MagicMock
