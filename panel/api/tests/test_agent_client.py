"""
Pi Control Panel - Agent Client Tests

Tests for AgentClient circuit breaker, connection handling, and RPC protocol.
"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock

import os
os.environ["JWT_SECRET"] = "test-secret-key-for-testing"
os.environ["DATABASE_PATH"] = ":memory:"

from services.agent_client import AgentClient, _CircuitState


class TestCircuitBreaker:
    """Test circuit breaker state transitions."""

    def test_initial_state_is_closed(self):
        """Test circuit breaker starts in CLOSED state."""
        client = AgentClient(socket_path="/tmp/test.sock")
        assert client._circuit_state == _CircuitState.CLOSED
        assert client._failure_count == 0

    def test_closed_allows_requests(self):
        """Test CLOSED state allows requests."""
        client = AgentClient(socket_path="/tmp/test.sock")
        assert client._check_circuit() is True

    def test_opens_after_threshold_failures(self):
        """Test circuit opens after failure_threshold failures."""
        client = AgentClient(socket_path="/tmp/test.sock")
        client._failure_threshold = 3

        for _ in range(3):
            client._record_failure()

        assert client._circuit_state == _CircuitState.OPEN

    def test_open_blocks_requests(self):
        """Test OPEN state blocks requests."""
        client = AgentClient(socket_path="/tmp/test.sock")
        client._circuit_state = _CircuitState.OPEN
        client._last_failure_time = time.monotonic()

        assert client._check_circuit() is False

    def test_open_transitions_to_half_open_after_timeout(self):
        """Test OPEN transitions to HALF_OPEN after circuit_timeout."""
        client = AgentClient(socket_path="/tmp/test.sock")
        client._circuit_state = _CircuitState.OPEN
        client._circuit_timeout = 0.1  # 100ms for test speed
        client._last_failure_time = time.monotonic() - 0.2  # 200ms ago

        assert client._check_circuit() is True
        assert client._circuit_state == _CircuitState.HALF_OPEN

    def test_half_open_allows_requests(self):
        """Test HALF_OPEN state allows requests."""
        client = AgentClient(socket_path="/tmp/test.sock")
        client._circuit_state = _CircuitState.HALF_OPEN
        assert client._check_circuit() is True

    def test_half_open_closes_after_success_threshold(self):
        """Test HALF_OPEN closes after enough successes."""
        client = AgentClient(socket_path="/tmp/test.sock")
        client._circuit_state = _CircuitState.HALF_OPEN
        client._half_open_threshold = 2

        client._record_success()
        assert client._circuit_state == _CircuitState.HALF_OPEN

        client._record_success()
        assert client._circuit_state == _CircuitState.CLOSED
        assert client._failure_count == 0

    def test_half_open_reopens_on_failure(self):
        """Test HALF_OPEN re-opens on failure."""
        client = AgentClient(socket_path="/tmp/test.sock")
        client._circuit_state = _CircuitState.HALF_OPEN

        client._record_failure()
        assert client._circuit_state == _CircuitState.OPEN

    def test_success_resets_failure_count_in_closed(self):
        """Test success resets failure count in CLOSED state."""
        client = AgentClient(socket_path="/tmp/test.sock")
        client._failure_count = 3

        client._record_success()
        assert client._failure_count == 0

    def test_failure_count_increments(self):
        """Test failure count increments correctly."""
        client = AgentClient(socket_path="/tmp/test.sock")

        client._record_failure()
        assert client._failure_count == 1

        client._record_failure()
        assert client._failure_count == 2

    def test_failure_records_timestamp(self):
        """Test failure records last_failure_time."""
        client = AgentClient(socket_path="/tmp/test.sock")

        before = time.monotonic()
        client._record_failure()
        after = time.monotonic()

        assert before <= client._last_failure_time <= after


class TestAgentClientInit:
    """Test AgentClient initialization."""

    def test_default_socket_path(self):
        """Test default socket path from settings."""
        client = AgentClient()
        assert client.socket_path is not None

    def test_custom_socket_path(self):
        """Test custom socket path."""
        client = AgentClient(socket_path="/custom/path.sock")
        assert client.socket_path == "/custom/path.sock"

    def test_initial_state(self):
        """Test initial connection state."""
        client = AgentClient(socket_path="/tmp/test.sock")
        assert client._connected is False
        assert client._reader is None
        assert client._writer is None
        assert client._request_id == 0


class TestAgentClientConnect:
    """Test AgentClient connection handling."""

    @pytest.mark.asyncio
    async def test_connect_file_not_found(self):
        """Test connect returns False when socket file doesn't exist."""
        client = AgentClient(socket_path="/tmp/nonexistent_test.sock")
        result = await client.connect()
        assert result is False
        assert client._connected is False

    @pytest.mark.asyncio
    async def test_call_raises_when_circuit_open(self):
        """Test call raises ConnectionError when circuit is open."""
        client = AgentClient(socket_path="/tmp/test.sock")
        client._circuit_state = _CircuitState.OPEN
        client._last_failure_time = time.monotonic()

        with pytest.raises(ConnectionError, match="circuit breaker open"):
            await client.call("test.method")

    @pytest.mark.asyncio
    async def test_call_raises_when_cannot_connect(self):
        """Test call raises when connection fails."""
        client = AgentClient(socket_path="/tmp/nonexistent_test.sock")

        with pytest.raises(ConnectionError, match="Cannot connect"):
            await client.call("test.method")

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnect clears state."""
        client = AgentClient(socket_path="/tmp/test.sock")
        client._connected = True
        client._reader = MagicMock()

        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        client._writer = mock_writer

        await client.disconnect()

        assert client._connected is False
        assert client._reader is None
        assert client._writer is None
        mock_writer.close.assert_called_once()


class TestAgentClientMethods:
    """Test convenience methods on AgentClient."""

    def test_has_discovery_methods(self):
        """Test client has discovery methods."""
        client = AgentClient(socket_path="/tmp/test.sock")
        assert hasattr(client, "get_snapshot")
        assert hasattr(client, "refresh_discovery")

    def test_has_telemetry_methods(self):
        """Test client has telemetry methods."""
        client = AgentClient(socket_path="/tmp/test.sock")
        assert hasattr(client, "get_current_telemetry")
        assert hasattr(client, "query_telemetry")

    def test_has_job_methods(self):
        """Test client has job methods."""
        client = AgentClient(socket_path="/tmp/test.sock")
        assert hasattr(client, "run_job")
        assert hasattr(client, "get_job_status")
        assert hasattr(client, "cancel_job")

    def test_has_device_methods(self):
        """Test client has device methods."""
        client = AgentClient(socket_path="/tmp/test.sock")
        assert hasattr(client, "get_devices")
        assert hasattr(client, "send_device_command")

    @pytest.mark.asyncio
    async def test_execute_action_alias_forwards_to_resource_action(self):
        """Test execute_action alias delegates to resource_action."""
        client = AgentClient(socket_path="/tmp/test.sock")
        client.resource_action = AsyncMock(return_value={"success": True})

        result = await client.execute_action("demo.service", "restart", {"force": True}, timeout=45.0)

        assert result == {"success": True}
        client.resource_action.assert_awaited_once_with(
            resource_id="demo.service",
            action="restart",
            params={"force": True},
            timeout=45.0,
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
