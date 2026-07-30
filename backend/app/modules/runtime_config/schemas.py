"""Pydantic DTOs for runtime config overrides."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OverrideRead(BaseModel):
    """One stored override row."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    value: Any
    updated_by: UUID
    updated_at: datetime


class EffectiveSettingRead(BaseModel):
    """One whitelisted key with its effective and env values."""

    key: str
    effective_value: Any
    env_value: Any
    overridden: bool
    updated_by: UUID | None = None
    updated_at: datetime | None = None


class SettingsListResponse(BaseModel):
    """GET /admin/settings payload."""

    settings: list[EffectiveSettingRead]


class SettingValueWrite(BaseModel):
    """PUT /admin/settings/{key} body."""

    value: Any
