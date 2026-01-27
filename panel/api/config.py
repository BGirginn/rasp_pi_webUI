"""
Pi Control Panel - API Configuration

Loads configuration from environment variables and files.
"""

import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""
    
    # API Settings
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8080, alias="API_PORT")
    api_debug: bool = Field(default=False, alias="API_DEBUG")
    
    # JWT Settings
    jwt_secret: str = Field(default="change-me-in-production", alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=15, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_token_expire_days: int = Field(default=7, alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS")
    
    # Database
    database_path: str = Field(default="/data/control.db", alias="DATABASE_PATH")
    telemetry_db_path: str = Field(default="/data/telemetry.db", alias="TELEMETRY_DB_PATH")
    
    # Agent
    agent_socket: str = Field(default="/run/pi-agent/agent.sock", alias="AGENT_SOCKET")
    
    # Security
    panel_allow_lan: bool = Field(default=False, alias="PANEL_ALLOW_LAN")
    tailscale_cidr: str = Field(default="100.64.0.0/10", alias="TAILSCALE_CIDR")
    cors_origins: str = Field(default="", alias="CORS_ORIGINS")
    
    # Rate Limiting
    rate_limit_per_minute: int = Field(default=100, alias="RATE_LIMIT_PER_MINUTE")
    rate_limit_admin_console: int = Field(default=10, alias="RATE_LIMIT_ADMIN_CONSOLE")
    
    # Terminal Security
    terminal_mode_default: str = Field(default="restricted", alias="TERMINAL_MODE_DEFAULT")
    terminal_breakglass_ttl_min: int = Field(default=10, alias="TERMINAL_BREAKGLASS_TTL_MIN")
    terminal_idle_timeout_sec: int = Field(default=90, alias="TERMINAL_IDLE_TIMEOUT_SEC")
    terminal_docker_ssh_enabled: bool = Field(default=False, alias="TERMINAL_DOCKER_SSH_ENABLED")
    terminal_max_message_size: int = Field(default=4096, alias="TERMINAL_MAX_MESSAGE_SIZE")
    terminal_allowed_commands: str = Field(default="whoami,uptime,uname -a,df -h,free -h,ip a,ip r,docker ps", alias="TERMINAL_ALLOWED_COMMANDS")
    
    @property
    def terminal_allowed_commands_list(self) -> List[str]:
        """Parse allowed commands from comma-separated string."""
        if not self.terminal_allowed_commands:
            return []
        return [cmd.strip() for cmd in self.terminal_allowed_commands.split(",")]
    
    # Telemetry Retention (all extended to 90 days)
    telemetry_raw_retention_days: int = Field(default=90, alias="TELEMETRY_RAW_RETENTION_DAYS")
    telemetry_summary_retention_days: int = Field(default=90, alias="TELEMETRY_SUMMARY_RETENTION_DAYS")
    telemetry_collection_interval: int = Field(default=30, alias="TELEMETRY_COLLECTION_INTERVAL")
    audit_log_retention_days: int = Field(default=90, alias="AUDIT_LOG_RETENTION_DAYS")
    iot_sensor_retention_days: int = Field(default=90, alias="IOT_SENSOR_RETENTION_DAYS")
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if not self.cors_origins:
            return []
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    def get_jwt_secret(self) -> str:
        """Get JWT secret, optionally from file."""
        secret_file = os.getenv("JWT_SECRET_FILE")
        if secret_file and Path(secret_file).exists():
            return Path(secret_file).read_text().strip()
        return self.jwt_secret
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
