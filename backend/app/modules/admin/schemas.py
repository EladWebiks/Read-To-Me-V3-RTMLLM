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
    """Per-user usage row + username resolved by the admin router."""

    username: str | None = None
