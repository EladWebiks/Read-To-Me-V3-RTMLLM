"""Grouped settings: required infra vars, dev defaults, flat env aliases."""

import pytest
from app.core.config import (
    AuthSettings,
    DatabaseSettings,
    GoogleSsoSettings,
    RedisSettings,
    StorageSettings,
)
from pydantic import ValidationError

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
