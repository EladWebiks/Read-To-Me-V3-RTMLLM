"""DTOs for cached and generated book summaries."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SummaryKind(StrEnum):
    """Supported summary views."""

    NO_SPOILER = "no_spoiler"
    FULL = "full"


class SummaryDraft(BaseModel):
    """Provider-validated structured summary."""

    summary: str = Field(min_length=40, max_length=8000)
    themes: list[str] = Field(default_factory=list, max_length=8)
    setting: str = Field(default="", max_length=1000)
    tropes: list[str] = Field(default_factory=list, max_length=8)
    coverage_note: str = Field(default="", max_length=500)


class BookSummaryRead(BaseModel):
    """Persisted summary returned to services and tools."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    book_id: UUID
    kind: str
    content: str
    structured_data: dict[str, object]
    source: str
    provider: str | None
    model: str | None
    prompt_version: str
    content_hash: str
    created_at: datetime
    updated_at: datetime


class SummaryLookup(BaseModel):
    """Cache lookup state without exposing stale text."""

    found: bool
    stale: bool
    summary: BookSummaryRead | None = None


class SummaryEnsureResult(BaseModel):
    """Generated or reused summary."""

    summary: BookSummaryRead
    cached: bool


class SummaryWrite(BaseModel):
    """Values persisted when refreshing one summary variant."""

    user_id: UUID
    book_id: UUID
    kind: str
    content: str
    structured_data: dict[str, object]
    provider: str
    model: str
    prompt_version: str
    content_hash: str


class SummarySearchHit(BaseModel):
    """Fresh summary match used ahead of chapter FTS."""

    book_id: UUID
    book_title: str
    snippet: str
