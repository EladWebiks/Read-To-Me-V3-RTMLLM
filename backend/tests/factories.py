"""Hermetic `Settings` construction for tests.

`Settings` is (being) composed of per-group `BaseSettings` classes that each
read env + dotenv on their own, so `Settings(_env_file=None)` alone is not
hermetic. This factory builds every group with `_env_file=None`, fills the
required fields with safe dummies, and routes flat legacy-named overrides
(`jwt_secret=...`, `minio_endpoint=...`) to the right group.

Note: os.environ still takes part for fields NOT passed explicitly (same as
direct `Settings(...)` construction always did); conftest pins the required
vars and admits only infra keys from the repo-root `.env`, so results are
deterministic.
"""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings

# Only the three vars that have no code default. Values need to be
# well-formed, not reachable — factory-built Settings never open real
# connections (DB fixtures use get_settings(), which conftest pins).
_REQUIRED_DUMMIES: dict[str, Any] = {
    "database_url": "postgresql+asyncpg://rtm:rtm@localhost:5432/rtm_test",
    "redis_url": "redis://localhost:6379/0",
    "minio_endpoint": "localhost:9000",
}


def _group_classes() -> dict[str, type[BaseSettings]]:
    """Root field name -> group class, for composed group fields."""
    groups: dict[str, type[BaseSettings]] = {}
    for name, field in Settings.model_fields.items():
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseSettings):
            groups[name] = annotation
    return groups


def _flat_key(field_name: str, field: FieldInfo) -> str:
    """Legacy flat name of a group field (its env alias, or its own name)."""
    alias = field.validation_alias
    return alias if isinstance(alias, str) else field_name


def _routing() -> dict[str, str]:
    """Legacy flat key -> root group attribute name."""
    return {
        _flat_key(field_name, field): group_name
        for group_name, cls in _group_classes().items()
        for field_name, field in cls.model_fields.items()
    }


def make_settings(**overrides: Any) -> Settings:
    """Build hermetic Settings; overrides use legacy flat env-style names."""
    values = {**_REQUIRED_DUMMIES, **overrides}
    routing = _routing()
    per_group: dict[str, dict[str, Any]] = {name: {} for name in _group_classes()}
    flat: dict[str, Any] = {}
    for key, value in values.items():
        if key in routing:
            per_group[routing[key]][key] = value
        elif key in Settings.model_fields:
            flat[key] = value
        else:
            msg = f"Unknown settings override: {key}"
            raise ValueError(msg)
    # dict[str, Any] (not dict[str, BaseSettings]) so the pydantic mypy plugin
    # accepts unpacking into the field-typed `Settings.__init__` it synthesizes.
    groups: dict[str, Any] = {
        name: cls(_env_file=None, **per_group[name]) for name, cls in _group_classes().items()
    }
    return Settings(_env_file=None, **groups, **flat)
