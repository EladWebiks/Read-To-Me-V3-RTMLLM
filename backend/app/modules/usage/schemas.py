"""Pydantic DTOs for the self-serve usage endpoint."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.modules.quotas.kinds import QuotaKind


class MeUsageKindRead(BaseModel):
    """One quota kind with hybrid usage and the caller's resolved limit."""

    kind: QuotaKind
    label: str
    unit: str
    window: Literal["month", "standing"]
    used: float
    limit: float | None  # None = unlimited (row absent or exempt)


class MeUsageResponse(BaseModel):
    membership: str
    exempt: bool  # admins: limits all None but usage still shown
    as_of: datetime
    resets_at: datetime  # month-window end; standing kinds ignore it
    kinds: list[MeUsageKindRead]
