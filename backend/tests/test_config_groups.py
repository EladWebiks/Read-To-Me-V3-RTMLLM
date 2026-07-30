"""Grouped settings: required infra vars, dev defaults, flat env aliases."""

import pytest
from app.core.config import DatabaseSettings, RedisSettings, StorageSettings
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
