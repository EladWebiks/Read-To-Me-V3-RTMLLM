"""Aggregation-only DTOs for the backoffice API."""

from __future__ import annotations

from pydantic import BaseModel

from app.modules.llm.schemas import UserUsageRead


class Page[ItemT](BaseModel):
    """Uniform limit/offset pagination envelope for admin lists."""

    items: list[ItemT]
    total: int
    limit: int
    offset: int


class AdminUserUsageRead(UserUsageRead):
    """Per-user usage row + identity/quota columns resolved by the admin router.

    month_* cover the CURRENT UTC calendar month regardless of the selected
    period. *_limit fields: None = unlimited (no membership_quotas rule).
    """

    username: str | None = None
    membership: str | None = None
    month_tokens: int = 0
    month_cost: float = 0.0
    llm_tokens_limit: float | None = None
    llm_cost_limit: float | None = None
