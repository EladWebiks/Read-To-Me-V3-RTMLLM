"""Application settings via pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment / `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "RTM v3"
    app_env: str = "local"
    debug: bool = False
    api_prefix: str = "/api"

    database_url: str = "postgresql+asyncpg://rtm:rtm@localhost:5432/rtm"
    redis_url: str = "redis://localhost:6379/0"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "rtm"
    minio_secret_key: str = "rtmsecret"
    minio_bucket: str = "rtm"
    minio_secure: bool = False
    # Host used inside signed URLs (browser-facing). Defaults to minio_endpoint.
    minio_public_endpoint: str | None = None

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    jwt_secret: str = "dev-only-change-me-to-a-long-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    admin_username: str = "admin"
    admin_password: str = "changeme123"

    scrape_timeout_seconds: int = 20
    scrape_max_bytes: int = 2_097_152  # 2 MB
    scrape_delay_seconds: float = 1.5

    sapi_proxy_enabled: bool = True
    signed_url_expires_seconds: int = 3600
    # How long generated MP3 jobs (and their objects) are kept before expiry.
    download_job_ttl_hours: int = 72


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
