"""Application settings via pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class _GroupSettings(BaseSettings):
    """Shared loading behavior for every settings group."""

    model_config = SettingsConfigDict(
        # Repo-root `.env` (native dev / secrets) plus optional `backend/.env`.
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


class DatabaseSettings(_GroupSettings):
    """Postgres connection. Supplied by docker-compose in containers."""

    url: str = Field(validation_alias="database_url")


class RedisSettings(_GroupSettings):
    """Redis / arq connection. Supplied by docker-compose in containers."""

    url: str = Field(validation_alias="redis_url")


class StorageSettings(_GroupSettings):
    """MinIO object storage + blob retention.

    `endpoint` is compose-supplied and required. The credentials keep dev
    defaults that match the compose-provisioned MinIO server; override both
    together (compose interpolates the same two variables into the server).
    """

    endpoint: str = Field(validation_alias="minio_endpoint")
    access_key: str = Field(default="rtm", validation_alias="minio_access_key")
    secret_key: str = Field(default="rtmsecret", validation_alias="minio_secret_key")
    bucket: str = Field(default="rtm", validation_alias="minio_bucket")
    secure: bool = Field(default=False, validation_alias="minio_secure")
    # Host used inside signed URLs (browser-facing). Defaults to endpoint.
    public_endpoint: str | None = Field(default=None, validation_alias="minio_public_endpoint")
    signed_url_expires_seconds: int = 3600
    # Retention for generated MP3 jobs and MinIO objects (hours).
    download_job_ttl_hours: int = 24


class AuthSettings(_GroupSettings):
    """Session JWT, cookie flags, seeded admin account.

    Dev-correct defaults: a real deployment overrides JWT_SECRET,
    ADMIN_PASSWORD and COOKIE_SECURE through real environment variables.
    """

    jwt_secret: str = "dev-only-change-me-to-a-long-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    admin_username: str = "admin"
    admin_password: str = "changeme123"


class GoogleSsoSettings(_GroupSettings):
    """Google SSO (server-side authorization-code flow).

    `.env` only — never in docker-compose.yml. All three are required for
    login to work; the endpoints return 503 while any is unset.
    """

    client_id: str | None = Field(default=None, validation_alias="google_client_id")
    client_secret: str | None = Field(default=None, validation_alias="google_client_secret")
    # Browser-facing callback, e.g. http://localhost:5173/api/auth/google/callback
    redirect_uri: str | None = Field(default=None, validation_alias="google_redirect_uri")


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

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    auth: AuthSettings = Field(default_factory=AuthSettings)
    google: GoogleSsoSettings = Field(default_factory=GoogleSsoSettings)

    scrape_timeout_seconds: int = 20
    scrape_max_bytes: int = 2_097_152  # 2 MB
    scrape_delay_seconds: float = 1.5

    sapi_proxy_enabled: bool = True

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
