"""The hermetic settings factory: dummies, overrides, unknown-key rejection."""

import pytest

from tests.factories import make_settings


@pytest.mark.unit
def test_factory_builds_settings_with_dummy_required_values() -> None:
    settings = make_settings()
    # Flat access in Task 1; Task 2 moves these behind groups and updates
    # these two assertions in the same commit as the move.
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.minio_endpoint == "localhost:9000"


@pytest.mark.unit
def test_factory_override_wins() -> None:
    settings = make_settings(redis_url="redis://other:6379/1")
    assert settings.redis_url == "redis://other:6379/1"


@pytest.mark.unit
def test_factory_rejects_unknown_keys() -> None:
    with pytest.raises(ValueError, match="Unknown settings override: nope"):
        make_settings(nope=True)
