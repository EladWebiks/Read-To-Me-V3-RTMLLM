"""Pydantic DTOs for the membership-quotas admin API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.quotas.kinds import QuotaKind


class QuotaKindInfo(BaseModel):
    """One registry entry, served so the frontend never hardcodes kinds."""

    kind: QuotaKind
    label: str
    unit: str
    window: Literal["month", "standing"]


class MembershipQuotaRead(BaseModel):
    """One configured quota rule."""

    model_config = ConfigDict(from_attributes=True)

    membership: str
    quota_kind: QuotaKind
    limit_value: float
    updated_at: datetime


class MembershipQuotasResponse(BaseModel):
    """Kind registry + every configured rule."""

    kinds: list[QuotaKindInfo]
    quotas: list[MembershipQuotaRead]


class UserQuotaOverrideRead(BaseModel):
    """One per-user override row (absent kind = the tier limit applies)."""

    model_config = ConfigDict(from_attributes=True)

    quota_kind: QuotaKind
    limit_value: float
    updated_at: datetime


class UserQuotasResponse(BaseModel):
    """Registry + the user's tier limits (sparse) + their override rows."""

    membership: str
    kinds: list[QuotaKindInfo]
    tier_limits: dict[str, float]
    overrides: list[UserQuotaOverrideRead]


class QuotaLimitWrite(BaseModel):
    """Body of a quota upsert; a zero/negative limit would block everything."""

    limit_value: float = Field(gt=0)
