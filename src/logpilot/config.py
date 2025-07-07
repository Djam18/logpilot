"""Configuration via pydantic-settings — 12-factor app style."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Logpilot configuration — loaded from env vars / .env file."""

    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis URL for caching")
    cache_ttl: int = Field(default=300, description="Cache TTL in seconds")
    default_format: str = Field(default="auto", description="Default log format (auto|json|apache|syslog)")
    max_workers: int = Field(default=4, description="Worker processes for large files")
    alert_slack_webhook: str = Field(default="", description="Slack webhook URL for alerts")
    alert_email_smtp: str = Field(default="", description="SMTP server for email alerts")

    class Config:
        env_prefix = "LOGPILOT_"
        env_file = ".env"


settings = Settings()
