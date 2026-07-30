"""Aggregation-only DTOs for the backoffice API."""

from __future__ import annotations

from pydantic import BaseModel


class Page[ItemT](BaseModel):
    """Uniform limit/offset pagination envelope for admin lists."""

    items: list[ItemT]
    total: int
    limit: int
    offset: int
