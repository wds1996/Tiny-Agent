from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    """Environment-driven service configuration.

    SecretStr reduces accidental repr/log leakage; it is not a secret manager.
    Production secrets should be injected by the deployment platform.
    """

    environment: Literal["dev", "test", "prod"] = "dev"
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    max_concurrency: int = Field(default=8, ge=1, le=10_000)
    queue_timeout_seconds: float = Field(default=0.25, gt=0)
    request_timeout_seconds: float = Field(default=30.0, gt=0)
    database_url: str | None = None
    redis_url: str | None = None
    model_api_key: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_prefix="TINY_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def safe_summary(self) -> dict[str, object]:
        return {
            "environment": self.environment,
            "host": self.host,
            "port": self.port,
            "max_concurrency": self.max_concurrency,
            "queue_timeout_seconds": self.queue_timeout_seconds,
            "request_timeout_seconds": self.request_timeout_seconds,
            "database_configured": self.database_url is not None,
            "redis_configured": self.redis_url is not None,
            "model_api_key_configured": self.model_api_key is not None,
        }
