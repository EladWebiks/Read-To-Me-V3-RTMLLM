"""Whitelist of runtime-tunable settings — the ONLY DB-overridable keys.

Secrets, credentials, and infrastructure endpoints are excluded by
construction: their groups/fields simply never appear here. Each entry
carries a TypeAdapter built from the field's annotation AND FieldInfo, so
type and declared constraints are enforced identically on write and read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import TypeAdapter
from pydantic_settings import BaseSettings

from app.core.config import (
    AudioSettings,
    LlmRuntimeSettings,
    ScrapeSettings,
    StorageSettings,
)

# Sections where EVERY field is tunable (derived by introspection, so a new
# field in the group is automatically overridable and validated).
_FULL_SECTIONS: dict[str, type[BaseSettings]] = {
    "llm_runtime": LlmRuntimeSettings,
}

# Sections where only the listed fields are tunable. An unknown field name
# fails at import time (model_fields lookup below), so the list cannot drift.
_PARTIAL_SECTIONS: dict[str, tuple[type[BaseSettings], tuple[str, ...]]] = {
    "scrape": (ScrapeSettings, ("timeout_seconds", "max_bytes", "delay_seconds")),
    "storage": (StorageSettings, ("download_job_ttl_hours", "signed_url_expires_seconds")),
    "audio": (AudioSettings, ("sapi_proxy_enabled",)),
}


@dataclass(frozen=True)
class TunableField:
    """One whitelisted override target."""

    key: str  # "llm_runtime.max_tool_iters"
    section: str  # attribute on the root Settings
    field_name: str  # attribute on the group model
    group_cls: type[BaseSettings]
    adapter: TypeAdapter[Any]  # validates type AND field constraints


def _field_adapter(group_cls: type[BaseSettings], field_name: str) -> TypeAdapter[Any]:
    """Adapter enforcing the field's annotation plus its declared constraints.

    Only `FieldInfo.metadata` (the Ge/Gt/Le… objects) is carried over. Passing
    the whole FieldInfo would also hand `validation_alias` and `default` to a
    context that has no use for them, which pydantic warns about — and an
    override always supplies a value, so a default would never apply anyway.
    """
    info = group_cls.model_fields[field_name]
    annotation: Any = info.annotation
    if not info.metadata:
        return TypeAdapter(annotation)
    return TypeAdapter(Annotated[(annotation, *info.metadata)])


def _entry(section: str, group_cls: type[BaseSettings], field_name: str) -> TunableField:
    return TunableField(
        key=f"{section}.{field_name}",
        section=section,
        field_name=field_name,
        group_cls=group_cls,
        adapter=_field_adapter(group_cls, field_name),
    )


def _build_registry() -> dict[str, TunableField]:
    entries: list[TunableField] = []
    for section, group_cls in _FULL_SECTIONS.items():
        entries.extend(_entry(section, group_cls, name) for name in group_cls.model_fields)
    for section, (group_cls, names) in _PARTIAL_SECTIONS.items():
        entries.extend(_entry(section, group_cls, name) for name in names)
    return {entry.key: entry for entry in entries}


TUNABLE_FIELDS: dict[str, TunableField] = _build_registry()

_SECTION_BY_GROUP: dict[type[BaseSettings], str] = {
    **{cls: section for section, cls in _FULL_SECTIONS.items()},
    **{cls: section for section, (cls, _names) in _PARTIAL_SECTIONS.items()},
}


def section_of(group_cls: type[BaseSettings]) -> str:
    """Root Settings attribute for a tunable group; KeyError if not tunable."""
    return _SECTION_BY_GROUP[group_cls]
