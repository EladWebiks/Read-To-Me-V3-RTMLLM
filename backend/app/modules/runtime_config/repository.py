"""DB access for app_settings / app_settings_audit (this module only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.runtime_config.models import AppSetting, AppSettingAudit


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Fields for one append-only audit insert."""

    key: str
    action: str  # "set" | "clear"
    old_value: Any
    new_value: Any
    actor_id: UUID


class AppSettingsRepository:
    """CRUD for override rows + audit appends."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[AppSetting]:
        """All override rows, ordered by key."""
        result = await self._session.execute(select(AppSetting).order_by(AppSetting.key))
        return list(result.scalars().all())

    async def get_by_key(self, key: str) -> AppSetting | None:
        """One override row by key."""
        result = await self._session.execute(select(AppSetting).where(AppSetting.key == key))
        return result.scalar_one_or_none()

    async def upsert(self, key: str, value: Any, updated_by: UUID) -> AppSetting:
        """Insert or update the override row for a key."""
        row = await self.get_by_key(key)
        if row is None:
            row = AppSetting(key=key, value=value, updated_by=updated_by)
            self._session.add(row)
        else:
            row.value = value
            row.updated_by = updated_by
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def delete(self, row: AppSetting) -> None:
        """Hard-delete an override row (history lives in the audit table)."""
        await self._session.delete(row)
        await self._session.flush()

    async def add_audit(self, entry: AuditEntry) -> None:
        """Append one audit row."""
        self._session.add(
            AppSettingAudit(
                key=entry.key,
                action=entry.action,
                old_value=entry.old_value,
                new_value=entry.new_value,
                actor_id=entry.actor_id,
            )
        )
        await self._session.flush()
