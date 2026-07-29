"""Application settings via pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment / `.env`."""

    model_config = SettingsConfigDict(
        # Repo-root `.env` (compose / local) plus optional `backend/.env` override.
        env_file=("../.env", ".env"),
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
    # Retention for generated MP3 jobs and MinIO objects (hours).
    download_job_ttl_hours: int = 24

    # LLM (Milestone B). Off by default so Milestone A stays LLM-free.
    llm_enabled: bool = False
    llm_provider: str = "gemini"
    llm_model: str = "gemini-3.5-flash-lite"
    gemini_api_key: str | None = None
    llm_timeout_seconds: int = 30
    llm_max_output_tokens: int = 2048
    llm_max_retries: int = 2
    langfuse_enabled: bool = False
    # Orchestration budgets (B3). Exceeding any one ends the run.
    # Caps are cumulative across all LLM rounds in one user turn (tool loop).
    llm_max_tool_iters: int = 6
    llm_max_external_calls: int = 3
    llm_max_turn_tokens_in: int = 64_000
    llm_max_turn_tokens_out: int = 8_192
    llm_max_turn_cost_usd: float = 0.05
    llm_run_deadline_seconds: int = 60
    llm_context_recent_messages: int = 10
    llm_summary_trigger_tokens: int = 12_000
    llm_summary_max_output_tokens: int = 1_200
    llm_assistant_mode: str = "internal_only"
    # HITL: how long a pending confirmation stays valid; max pauses per turn.
    llm_hitl_ttl_seconds: int = 900
    llm_max_hitl_rounds: int = 3


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
