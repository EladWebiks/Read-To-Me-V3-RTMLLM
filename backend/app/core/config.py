"""Application settings via pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class _GroupSettings(BaseSettings):
    """Shared loading behavior for every settings group."""

    model_config = SettingsConfigDict(
        # Repo-root `.env` (native dev / secrets) plus optional `backend/.env`.
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


class AppSettings(_GroupSettings):
    """App identity and HTTP surface."""

    name: str = Field(default="RTM v3", validation_alias="app_name")
    env: str = Field(default="local", validation_alias="app_env")
    debug: bool = False
    api_prefix: str = "/api"
    # Native dev (:5173), dockerized frontend (:3000), and port-80 host.
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost",
    ]


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


class ScrapeSettings(_GroupSettings):
    """Outbound fetch limits (central fetch service / SSRF guard)."""

    timeout_seconds: int = Field(default=20, validation_alias="scrape_timeout_seconds")
    max_bytes: int = Field(default=2_097_152, validation_alias="scrape_max_bytes")  # 2 MB
    delay_seconds: float = Field(default=1.5, validation_alias="scrape_delay_seconds")


class AudioSettings(_GroupSettings):
    """TTS provider toggles."""

    sapi_proxy_enabled: bool = True


class LlmSettings(_GroupSettings):
    """LLM provider config (Milestone B). Off by default.

    GEMINI_API_KEY is `.env` only — no default, never in docker-compose.yml.
    """

    enabled: bool = Field(default=False, validation_alias="llm_enabled")
    provider: str = Field(default="gemini", validation_alias="llm_provider")
    model: str = Field(default="gemini-3.5-flash-lite", validation_alias="llm_model")
    gemini_api_key: str | None = None
    timeout_seconds: int = Field(default=30, validation_alias="llm_timeout_seconds")
    max_output_tokens: int = Field(default=2048, validation_alias="llm_max_output_tokens")
    max_retries: int = Field(default=2, validation_alias="llm_max_retries")
    langfuse_enabled: bool = False

    @model_validator(mode="after")
    def _require_key_when_enabled(self) -> "LlmSettings":
        if self.enabled and self.provider == "gemini" and not self.gemini_api_key:
            msg = "GEMINI_API_KEY is required when LLM_ENABLED=true"
            raise ValueError(msg)
        return self


class LlmRuntimeSettings(_GroupSettings):
    """Orchestration budgets and knobs (B3). Exceeding any one ends the run.

    Deliberately code-only: these have no env names, so they cannot be
    tuned per-deployment yet. They move to a DB-backed dynamic config layer
    with per-tier overrides next (see the runtime-config plan). Read them
    only via `settings.llm_runtime` so extraction stays a one-object swap.
    """

    max_tool_iters: int = 6
    max_external_calls: int = 3
    max_turn_tokens_in: int = 64_000
    max_turn_tokens_out: int = 8_192
    max_turn_cost_usd: float = 0.05
    run_deadline_seconds: int = 60
    context_recent_messages: int = 10
    summary_trigger_tokens: int = 12_000
    summary_max_output_tokens: int = 1_200
    assistant_mode: str = "internal_only"
    # HITL: how long a pending confirmation stays valid; max pauses per turn.
    hitl_ttl_seconds: int = 900
    max_hitl_rounds: int = 3


class Settings(BaseSettings):
    """Runtime configuration, composed of env-loaded groups."""

    model_config = SettingsConfigDict(extra="ignore")

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    google: GoogleSsoSettings = Field(default_factory=GoogleSsoSettings)
    scrape: ScrapeSettings = Field(default_factory=ScrapeSettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    llm: LlmSettings = Field(default_factory=LlmSettings)
    llm_runtime: LlmRuntimeSettings = Field(default_factory=LlmRuntimeSettings)


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
