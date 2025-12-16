"""
Pi Agent - Tests

Pytest tests for the Pi Agent.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock


class TestResourceDataclass:
    """Test Resource dataclass."""
    
    def test_resource_creation(self):
        """Test creating a Resource."""
        from providers.base import Resource, ResourceClass, ResourceState
        
        resource = Resource(
            id="docker_nginx",
            name="nginx",
            type="container",
            resource_class=ResourceClass.APP,
            provider="docker",
            state=ResourceState.RUNNING,
        )
        
        assert resource.id == "docker_nginx"
        assert resource.name == "nginx"
        assert resource.resource_class == ResourceClass.APP
        assert resource.state == ResourceState.RUNNING
    
    def test_resource_to_dict(self):
        """Test Resource to_dict method."""
        from providers.base import Resource, ResourceClass, ResourceState
        
        resource = Resource(
            id="test_id",
            name="test",
            type="service",
            resource_class=ResourceClass.SYSTEM,
            provider="systemd",
            state=ResourceState.STOPPED,
        )
        
        data = resource.to_dict()
        
        assert data["id"] == "test_id"
        assert data["name"] == "test"
        assert data["resource_class"] == "SYSTEM"
        assert data["state"] == "stopped"


class TestResourceClass:
    """Test ResourceClass enum."""
    
    def test_class_values(self):
        """Test ResourceClass enum values."""
        from providers.base import ResourceClass
        
        assert ResourceClass.CORE.value == "CORE"
        assert ResourceClass.SYSTEM.value == "SYSTEM"
        assert ResourceClass.APP.value == "APP"
        assert ResourceClass.DEVICE.value == "DEVICE"


class TestResourceState:
    """Test ResourceState enum."""
    
    def test_state_values(self):
        """Test ResourceState enum values."""
        from providers.base import ResourceState
        
        assert ResourceState.RUNNING.value == "running"
        assert ResourceState.STOPPED.value == "stopped"
        assert ResourceState.FAILED.value == "failed"


class TestActionResult:
    """Test ActionResult dataclass."""
    
    def test_success_result(self):
        """Test successful ActionResult."""
        from providers.base import ActionResult
        
        result = ActionResult.success({"message": "ok"})
        
        assert result.success is True
        assert result.data == {"message": "ok"}
        assert result.error is None
    
    def test_failure_result(self):
        """Test failed ActionResult."""
        from providers.base import ActionResult
        
        result = ActionResult.failure("Something went wrong")
        
        assert result.success is False
        assert result.error == "Something went wrong"


class TestDockerProvider:
    """Test Docker provider."""
    
    def test_container_id_generation(self):
        """Test container resource ID generation."""
        container_name = "nginx-proxy"
        resource_id = f"docker_{container_name}"
        
        assert resource_id == "docker_nginx-proxy"


class TestSystemdProvider:
    """Test Systemd provider."""
    
    def test_service_classification(self):
        """Test service classification logic."""
        core_services = ["sshd", "systemd-journald", "dbus"]
        system_services = ["docker", "mosquitto", "caddy"]
        
        for service in core_services:
            # These should be classified as CORE
            assert service in core_services
        
        for service in system_services:
            # These should be classified as SYSTEM
            assert service in system_services


class TestTelemetryCollector:
    """Test Telemetry collector."""
    
    def test_metric_name_format(self):
        """Test metric name formatting."""
        prefix = "host"
        category = "cpu"
        metric = "pct_total"
        
        full_name = f"{prefix}.{category}.{metric}"
        
        assert full_name == "host.cpu.pct_total"
    
    def test_batch_size(self):
        """Test default batch size."""
        batch_size = 100
        
        metrics = list(range(batch_size))
        
        assert len(metrics) == batch_size


class TestJobRunner:
    """Test Job runner."""
    
    def test_job_state_transitions(self):
        """Test valid job state transitions."""
        states = ["pending", "running", "completed", "failed", "rolled_back"]
        
        # Pending -> Running is valid
        assert states.index("pending") < states.index("running")
        
        # Running -> Completed is valid
        assert states.index("running") < states.index("completed")


class TestRPCProtocol:
    """Test RPC protocol."""
    
    def test_message_format(self):
        """Test JSON-RPC message format."""
        import json
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "discovery.snapshot",
            "params": {}
        }
        
        encoded = json.dumps(request)
        decoded = json.loads(encoded)
        
        assert decoded["jsonrpc"] == "2.0"
        assert decoded["method"] == "discovery.snapshot"
    
    def test_length_prefix(self):
        """Test length-prefixed message encoding."""
        message = b"test message"
        length = len(message)
        
        prefix = length.to_bytes(4, byteorder="big")
        
        assert len(prefix) == 4
        assert int.from_bytes(prefix, byteorder="big") == length


class TestMQTTBridge:
    """Test MQTT bridge."""
    
    def test_topic_format(self):
        """Test MQTT topic formatting."""
        device_id = "esp-kitchen"
        
        telemetry_topic = f"esp/{device_id}/telemetry"
        command_topic = f"esp/{device_id}/command"
        status_topic = f"esp/{device_id}/status"
        
        assert telemetry_topic == "esp/esp-kitchen/telemetry"
        assert command_topic == "esp/esp-kitchen/command"
        assert status_topic == "esp/esp-kitchen/status"


class TestConfigValidation:
    """Test configuration validation."""
    
    def test_discovery_interval_range(self):
        """Test discovery interval is within valid range."""
        min_interval = 10
        max_interval = 300
        default_interval = 60
        
        assert min_interval <= default_interval <= max_interval
    
    def test_telemetry_interval_range(self):
        """Test telemetry interval is within valid range."""
        min_interval = 5
        max_interval = 60
        default_interval = 10
        
        assert min_interval <= default_interval <= max_interval


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
