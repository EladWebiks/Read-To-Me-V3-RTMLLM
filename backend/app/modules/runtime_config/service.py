"""Effective-settings resolution (env base + DB overrides) and admin writes."""

from __future__ import annotations

import logging
from typing import Any, TypeVar, cast
from uuid import UUID

from pydantic import ValidationError
from pydantic_settings import BaseSettings
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.runtime_config import cache
from app.modules.runtime_config.exceptions import (
    OverrideNotFoundError,
    SettingValueInvalidError,
    UnknownSettingKeyError,
)
from app.modules.runtime_config.models import AppSetting
from app.modules.runtime_config.registry import TUNABLE_FIELDS, TunableField, section_of
from app.modules.runtime_config.repository import AppSettingsRepository, AuditEntry
from app.modules.runtime_config.schemas import EffectiveSettingRead, OverrideRead

logger = logging.getLogger(__name__)

GroupT = TypeVar("GroupT", bound=BaseSettings)


class RuntimeConfigService:
    """Layered runtime config: env Settings base + sparse DB overrides.

    Constructible without FastAPI — arq jobs pass a SessionLocal() session.
    Warm-cache reads perform zero DB queries.
    """

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._repo = AppSettingsRepository(session)
        self._settings = settings

    async def get_effective(self, group_cls: type[GroupT]) -> GroupT:
        """One settings group with any DB overrides applied."""
        section = section_of(group_cls)
        updates = (await self._per_section()).get(section)
        base = getattr(self._settings, section)
        model = base.model_copy(update=updates) if updates else base
        return cast("GroupT", model)

    async def effective_settings(self) -> Settings:
        """Full Settings clone with overrides applied to tunable sections."""
        per_section = await self._per_section()
        if not per_section:
            return self._settings
        updates = {
            section: getattr(self._settings, section).model_copy(update=fields)
            for section, fields in per_section.items()
        }
        return self._settings.model_copy(update=updates)

    async def list_overrides(self) -> list[OverrideRead]:
        """Current DB overrides."""
        return [OverrideRead.model_validate(row) for row in await self._repo.list_all()]

    async def list_effective(self) -> list[EffectiveSettingRead]:
        """Every whitelisted key with effective/env values and attribution."""
        rows = {row.key: row for row in await self._repo.list_all()}
        overrides = await self._validated_overrides()
        return [
            self._effective_entry(field, rows.get(key), overrides)
            for key, field in sorted(TUNABLE_FIELDS.items())
        ]

    async def set_override(self, key: str, value: Any, updated_by: UUID) -> OverrideRead:
        """Validate → upsert → audit → invalidate. Never logs the value."""
        field = self._require_field(key)
        try:
            validated = field.adapter.validate_python(value)
        except ValidationError as exc:
            raise SettingValueInvalidError(key, exc.errors()[0]["msg"]) from exc
        stored = field.adapter.dump_python(validated, mode="json")
        existing = await self._repo.get_by_key(key)
        old_value = existing.value if existing else None
        row = await self._repo.upsert(key, stored, updated_by)
        await self._repo.add_audit(AuditEntry(key, "set", old_value, stored, updated_by))
        cache.invalidate()
        logger.info("app setting override set", extra={"key": key, "actor": str(updated_by)})
        return OverrideRead.model_validate(row)

    async def clear_override(self, key: str, updated_by: UUID) -> None:
        """Delete → audit → invalidate. Env value applies again."""
        self._require_field(key)
        existing = await self._repo.get_by_key(key)
        if existing is None:
            raise OverrideNotFoundError(key)
        old_value = existing.value
        await self._repo.delete(existing)
        await self._repo.add_audit(AuditEntry(key, "clear", old_value, None, updated_by))
        cache.invalidate()
        logger.info("app setting override cleared", extra={"key": key, "actor": str(updated_by)})

    def _require_field(self, key: str) -> TunableField:
        field = TUNABLE_FIELDS.get(key)
        if field is None:
            raise UnknownSettingKeyError(key)
        return field

    async def _per_section(self) -> dict[str, dict[str, Any]]:
        """Validated overrides grouped by Settings section attribute."""
        per_section: dict[str, dict[str, Any]] = {}
        for key, value in (await self._validated_overrides()).items():
            field = TUNABLE_FIELDS[key]
            per_section.setdefault(field.section, {})[field.field_name] = value
        return per_section

    async def _validated_overrides(self) -> dict[str, Any]:
        """Load-and-validate overrides, served from the process cache when warm."""
        cached = cache.get_cached()
        if cached is not None:
            return cached
        validated: dict[str, Any] = {}
        for row in await self._repo.list_all():
            self._absorb_row(row, validated)
        cache.put(validated)
        return validated

    def _absorb_row(self, row: AppSetting, validated: dict[str, Any]) -> None:
        """Fail-open per row: unknown or invalid rows are skipped with a warning."""
        field = TUNABLE_FIELDS.get(row.key)
        if field is None:
            logger.warning("ignoring unknown app_settings row", extra={"key": row.key})
            return
        try:
            validated[row.key] = field.adapter.validate_python(row.value)
        except ValidationError:
            logger.warning("ignoring invalid app_settings override", extra={"key": row.key})

    def _effective_entry(
        self,
        field: TunableField,
        row: AppSetting | None,
        overrides: dict[str, Any],
    ) -> EffectiveSettingRead:
        env_value = getattr(getattr(self._settings, field.section), field.field_name)
        overridden = field.key in overrides
        return EffectiveSettingRead(
            key=field.key,
            effective_value=overrides[field.key] if overridden else env_value,
            env_value=env_value,
            overridden=overridden,
            updated_by=row.updated_by if row is not None else None,
            updated_at=row.updated_at if row is not None else None,
        )
