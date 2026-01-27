"""
Pi Control Panel - Terminal Security Tests

Tests for break-glass authentication, restricted mode,
and security controls.
"""

import pytest
import hashlib
import secrets
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up test environment
os.environ["JWT_SECRET"] = "test-secret-key-for-testing"
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["TERMINAL_MODE_DEFAULT"] = "restricted"
os.environ["TERMINAL_DOCKER_SSH_ENABLED"] = "false"


class TestBreakGlassTokens:
    """Test break-glass token generation and validation."""
    
    def test_token_generation(self):
        """Test that tokens are generated with sufficient entropy."""
        from routers.terminal import generate_breakglass_token
        
        token = generate_breakglass_token()
        
        # Should be URL-safe base64
        assert len(token) >= 32
        assert all(c.isalnum() or c in '-_' for c in token)
    
    def test_token_uniqueness(self):
        """Test that generated tokens are unique."""
        from routers.terminal import generate_breakglass_token
        
        tokens = [generate_breakglass_token() for _ in range(100)]
        assert len(set(tokens)) == 100
    
    def test_token_hashing(self):
        """Test token hashing for storage."""
        from routers.terminal import hash_token
        
        token = "test_token_12345"
        hashed = hash_token(token)
        
        # Should be SHA-256 hex digest
        assert len(hashed) == 64
        assert hashed == hashlib.sha256(token.encode()).hexdigest()
    
    def test_different_tokens_different_hashes(self):
        """Test that different tokens produce different hashes."""
        from routers.terminal import hash_token
        
        hash1 = hash_token("token1")
        hash2 = hash_token("token2")
        
        assert hash1 != hash2


class TestRestrictedCommandValidation:
    """Test restricted mode command validation."""
    
    def test_allowed_simple_commands(self):
        """Test that simple allowed commands pass."""
        from routers.terminal import validate_restricted_command
        
        allowed = ["whoami", "uptime", "df -h", "free -h", "ip a", "docker ps"]
        
        for cmd in allowed:
            is_valid, error = validate_restricted_command(cmd)
            assert is_valid, f"Command '{cmd}' should be allowed: {error}"
    
    def test_blocked_shell_metacharacters(self):
        """Test that shell metacharacters are blocked."""
        from routers.terminal import validate_restricted_command
        
        dangerous = [
            "whoami; rm -rf /",
            "cat /etc/passwd | grep root",
            "echo test && rm -rf /",
            "$(whoami)",
            "`whoami`",
            "echo test > /etc/passwd",
            "cat < /etc/shadow",
        ]
        
        for cmd in dangerous:
            is_valid, error = validate_restricted_command(cmd)
            assert not is_valid, f"Command '{cmd}' should be blocked"
            assert "Blocked pattern" in error
    
    def test_systemctl_with_valid_service(self):
        """Test systemctl commands with valid service names."""
        from routers.terminal import validate_restricted_command
        
        valid = [
            "systemctl status nginx",
            "systemctl restart ssh",
            "systemctl status pi-control-agent",
        ]
        
        for cmd in valid:
            is_valid, error = validate_restricted_command(cmd)
            assert is_valid, f"Command '{cmd}' should be allowed: {error}"
    
    def test_systemctl_with_invalid_service(self):
        """Test systemctl commands with invalid service names."""
        from routers.terminal import validate_restricted_command
        
        invalid = [
            "systemctl status ../../../etc/passwd",
            "systemctl restart $(whoami)",
            "systemctl status service;rm -rf /",
        ]
        
        for cmd in invalid:
            is_valid, error = validate_restricted_command(cmd)
            assert not is_valid, f"Command '{cmd}' should be blocked"
    
    def test_docker_logs_validation(self):
        """Test docker logs command validation."""
        from routers.terminal import validate_restricted_command
        
        # Valid
        is_valid, _ = validate_restricted_command("docker logs nginx")
        assert is_valid
        
        is_valid, _ = validate_restricted_command("docker logs my-container-123")
        assert is_valid
        
        # Invalid
        is_valid, _ = validate_restricted_command("docker logs $(cat /etc/passwd)")
        assert not is_valid
    
    def test_command_not_in_allowlist(self):
        """Test that arbitrary commands are rejected."""
        from routers.terminal import validate_restricted_command
        
        blocked = [
            "rm -rf /",
            "dd if=/dev/zero of=/dev/sda",
            "cat /etc/shadow",
            "sudo su",
            "python -c 'import os; os.system(\"rm -rf /\")'",
        ]
        
        for cmd in blocked:
            is_valid, error = validate_restricted_command(cmd)
            assert not is_valid, f"Command '{cmd}' should be blocked"
    
    def test_empty_command(self):
        """Test empty command handling."""
        from routers.terminal import validate_restricted_command
        
        is_valid, error = validate_restricted_command("")
        assert not is_valid
        assert "Empty command" in error


class TestModeEnforcement:
    """Test terminal mode enforcement."""
    
    def test_default_mode_is_restricted(self):
        """Test that default mode is restricted."""
        from config import settings
        
        assert settings.terminal_mode_default == "restricted"
    
    def test_docker_ssh_disabled_by_default(self):
        """Test that Docker SSH is disabled by default."""
        from config import settings
        
        assert settings.terminal_docker_ssh_enabled == False


class TestSecurityConfiguration:
    """Test security configuration settings."""
    
    def test_breakglass_ttl_capped(self):
        """Test that break-glass TTL has a maximum."""
        from config import settings
        
        # TTL should be reasonable (default 10, max 30 in code)
        assert settings.terminal_breakglass_ttl_min <= 30
        assert settings.terminal_breakglass_ttl_min >= 1
    
    def test_idle_timeout_exists(self):
        """Test that idle timeout is configured."""
        from config import settings
        
        assert settings.terminal_idle_timeout_sec > 0
        assert settings.terminal_idle_timeout_sec <= 600  # Max 10 minutes reasonable
    
    def test_message_size_limit(self):
        """Test that message size limit is configured."""
        from config import settings
        
        assert settings.terminal_max_message_size > 0
        assert settings.terminal_max_message_size <= 65536  # Reasonable max


class TestAuditLogging:
    """Test audit logging functionality."""
    
    @pytest.mark.asyncio
    async def test_log_terminal_event_format(self):
        """Test audit log event format."""
        # This would require mocking the database
        # Placeholder for integration test
        pass


class TestSecurityScenarios:
    """Integration tests for security scenarios."""
    
    def test_x001_full_shell_requires_breakglass(self):
        """X001: Full shell with only access_token should be rejected."""
        # This test validates that:
        # - WebSocket handshake with mode='full' but no breakglass_token
        # - Should return error with code 'BREAKGLASS_REQUIRED'
        
        # Placeholder - would require WebSocket testing setup
        pass
    
    def test_x002_expired_breakglass_rejected(self):
        """X002: Full shell with expired breakglass_token should be rejected."""
        # This test validates that:
        # - Tokens with past expiration are rejected
        # - Should return error with code 'BREAKGLASS_INVALID'
        
        # Placeholder - would require database setup
        pass
    
    def test_x003_audit_entries_exist(self):
        """X003: Audit entries should exist for terminal events."""
        # This test validates that:
        # - terminal_connect events are logged
        # - breakglass_open/close events are logged
        # - Command executions are logged
        
        # Placeholder - would require full integration test
        pass
    
    def test_x004_message_size_enforced(self):
        """X004: Large messages should be truncated/rejected."""
        from config import settings
        
        # Verify the limit exists
        assert settings.terminal_max_message_size == 4096


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
