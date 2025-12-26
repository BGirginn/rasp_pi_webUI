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
    agent_socket: str = Field(default="/run/agent.sock", alias="AGENT_SOCKET")
    panel_agent_shared_key: str = Field(default="change-me-agent-key", alias="PANEL_AGENT_SHARED_KEY")
    panel_agent_shared_key_file: Optional[str] = Field(default=None, alias="PANEL_AGENT_SHARED_KEY_FILE")
    agent_rpc_host: Optional[str] = Field(default=None, alias="AGENT_RPC_HOST")
    agent_rpc_port: int = Field(default=9443, alias="AGENT_RPC_PORT")
    agent_rpc_use_tls: bool = Field(default=False, alias="AGENT_RPC_USE_TLS")
    agent_tls_ca_file: Optional[str] = Field(default=None, alias="AGENT_TLS_CA_FILE")
    agent_tls_client_cert: Optional[str] = Field(default=None, alias="AGENT_TLS_CLIENT_CERT")
    agent_tls_client_key: Optional[str] = Field(default=None, alias="AGENT_TLS_CLIENT_KEY")
    agent_tls_expected_identities: str = Field(default="", alias="AGENT_TLS_EXPECTED_IDENTITIES")
    agent_tls_expected_fingerprints: str = Field(default="", alias="AGENT_TLS_EXPECTED_FINGERPRINTS")
    agent_tls_server_name: Optional[str] = Field(default=None, alias="AGENT_TLS_SERVER_NAME")
    
    # Security
    panel_allow_lan: bool = Field(default=False, alias="PANEL_ALLOW_LAN")
    tailscale_cidr: str = Field(default="100.64.0.0/10", alias="TAILSCALE_CIDR")
    cors_origins: str = Field(default="", alias="CORS_ORIGINS")
    
    # Rate Limiting
    rate_limit_per_minute: int = Field(default=100, alias="RATE_LIMIT_PER_MINUTE")
    rate_limit_admin_console: int = Field(default=10, alias="RATE_LIMIT_ADMIN_CONSOLE")
    
    # Telemetry Retention
    telemetry_raw_retention_hours: int = Field(default=24, alias="TELEMETRY_RAW_RETENTION_HOURS")
    telemetry_summary_retention_days: int = Field(default=7, alias="TELEMETRY_SUMMARY_RETENTION_DAYS")
    telemetry_collection_interval: int = Field(default=30, alias="TELEMETRY_COLLECTION_INTERVAL")
    audit_log_retention_days: int = Field(default=90, alias="AUDIT_LOG_RETENTION_DAYS")
    
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

    def get_panel_agent_shared_key(self) -> str:
        """Get Panel ↔ Agent shared key, optionally from file."""
        if self.panel_agent_shared_key_file and Path(self.panel_agent_shared_key_file).exists():
            return Path(self.panel_agent_shared_key_file).read_text().strip()
        return self.panel_agent_shared_key

    def agent_tls_expected_identities_list(self) -> List[str]:
        if not self.agent_tls_expected_identities:
            return []
        return [value.strip() for value in self.agent_tls_expected_identities.split(",") if value.strip()]

    def agent_tls_expected_fingerprints_list(self) -> List[str]:
        if not self.agent_tls_expected_fingerprints:
            return []
        return [value.strip() for value in self.agent_tls_expected_fingerprints.split(",") if value.strip()]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
