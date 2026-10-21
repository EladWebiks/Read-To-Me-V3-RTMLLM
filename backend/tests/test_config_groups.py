"""Grouped settings: required infra vars, dev defaults, flat env aliases."""

import pytest
from app.core.config import (
    AuthSettings,
    DatabaseSettings,
    GoogleSsoSettings,
    LlmRuntimeSettings,
    RedisSettings,
    Settings,
    StorageSettings,
)
from pydantic import ValidationError
from pydantic_settings import BaseSettings

from tests.factories import make_settings


@pytest.mark.unit
def test_infra_urls_are_required(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("DATABASE_URL", "REDIS_URL", "MINIO_ENDPOINT"):
        monkeypatch.delenv(var, raising=False)
    for cls, field in (
        (DatabaseSettings, "database_url"),
        (RedisSettings, "redis_url"),
        (StorageSettings, "minio_endpoint"),
    ):
        with pytest.raises(ValidationError) as excinfo:
            cls(_env_file=None)
        assert field in str(excinfo.value)


@pytest.mark.unit
def test_database_url_reads_flat_env_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db:5432/x")
    settings = DatabaseSettings(_env_file=None)
    assert settings.url == "postgresql+asyncpg://u:p@db:5432/x"


@pytest.mark.unit
def test_factory_routes_flat_names_to_groups() -> None:
    settings = make_settings(database_url="postgresql+asyncpg://u:p@h:5432/d")
    assert settings.database.url == "postgresql+asyncpg://u:p@h:5432/d"
    assert settings.redis.url == "redis://localhost:6379/0"


@pytest.mark.unit
def test_storage_dev_defaults() -> None:
    settings = make_settings(minio_public_endpoint="media.local:9000")
    assert settings.storage.access_key == "rtm"
    assert settings.storage.bucket == "rtm"
    assert settings.storage.secure is False
    assert settings.storage.public_endpoint == "media.local:9000"
    assert settings.storage.download_job_ttl_hours == 24


@pytest.mark.unit
def test_auth_boots_on_dev_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("JWT_SECRET", "ADMIN_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    auth = AuthSettings(_env_file=None)
    assert len(auth.jwt_secret) >= 32
    assert auth.admin_username == "admin"
    assert auth.admin_password
    assert auth.cookie_samesite == "lax"


@pytest.mark.unit
def test_google_sso_has_no_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"):
        monkeypatch.delenv(var, raising=False)
    google = GoogleSsoSettings(_env_file=None)
    assert google.client_id is None
    assert google.client_secret is None
    assert google.redirect_uri is None


@pytest.mark.unit
def test_llm_enabled_requires_gemini_key() -> None:
    with pytest.raises(ValidationError, match="GEMINI_API_KEY"):
        make_settings(llm_enabled=True, gemini_api_key=None)


@pytest.mark.unit
def test_llm_disabled_allows_missing_key() -> None:
    settings = make_settings(llm_enabled=False, gemini_api_key=None)
    assert settings.llm.enabled is False


@pytest.mark.unit
def test_llm_runtime_defaults() -> None:
    runtime = make_settings(llm_max_tool_iters=2).llm_runtime
    assert runtime.max_tool_iters == 2
    assert runtime.max_external_calls == 8
    assert runtime.max_turn_tokens_in == 64_000
    assert runtime.max_turn_tokens_out == 8_192
    assert runtime.max_turn_cost_usd == 0.05
    assert runtime.run_deadline_seconds == 300
    assert runtime.context_recent_messages == 10
    assert runtime.summary_trigger_tokens == 12_000
    assert runtime.summary_max_output_tokens == 1_200
    assert runtime.assistant_mode == "internal_only"
    assert runtime.hitl_ttl_seconds == 900
    assert runtime.max_hitl_rounds == 3


@pytest.mark.unit
def test_llm_runtime_reads_prefixed_env_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """The knobs became env-addressable when the runtime-config layer landed."""
    monkeypatch.setenv("LLM_MAX_TOOL_ITERS", "99")
    monkeypatch.setenv("LLM_ASSISTANT_MODE", "external_allowed")
    runtime = LlmRuntimeSettings(_env_file=None)
    assert runtime.max_tool_iters == 99
    assert runtime.assistant_mode == "external_allowed"


@pytest.mark.unit
def test_llm_runtime_ignores_unprefixed_env_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """`validation_alias` is what stops a bare name from configuring a run.

    Without it pydantic-settings matches the field name itself, so a generic
    `MAX_TOOL_ITERS` or `ASSISTANT_MODE` in the environment would silently
    change orchestration budgets.
    """
    monkeypatch.setenv("MAX_TOOL_ITERS", "99")
    monkeypatch.setenv("ASSISTANT_MODE", "external_allowed")
    runtime = LlmRuntimeSettings(_env_file=None)
    assert runtime.max_tool_iters == 6
    assert runtime.assistant_mode == "internal_only"


@pytest.mark.unit
def test_app_scrape_audio_defaults() -> None:
    settings = make_settings(app_name="RTM test", scrape_delay_seconds=0.5)
    assert settings.app.name == "RTM test"
    assert settings.app.api_prefix == "/api"
    # The dockerized frontend origin must be covered without compose help.
    assert "http://localhost" in settings.app.cors_origins
    assert settings.scrape.timeout_seconds == 20
    assert settings.scrape.max_bytes == 2_097_152
    assert settings.scrape.delay_seconds == 0.5
    assert settings.audio.sapi_proxy_enabled is True


@pytest.mark.unit
def test_root_is_groups_only() -> None:
    for field in Settings.model_fields.values():
        annotation = field.annotation
        assert isinstance(annotation, type)
        assert issubclass(annotation, BaseSettings)
