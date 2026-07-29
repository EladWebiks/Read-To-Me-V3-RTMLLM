"""Library content-search DTOs."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class LibraryContentHit(BaseModel):
    """One search hit in the user's library (metadata or chapter text)."""

    book_id: UUID
    book_title: str
    match_source: Literal["summary", "book_metadata", "chapter"]
    snippet: str
    chapter_id: UUID | None = None
    chapter_number: int | None = None
    chapter_title: str | None = None


class LibraryContentSearchResult(BaseModel):
    """Aggregated library content search result."""

    hits: list[LibraryContentHit]
    total: int = Field(description="Number of hits returned (may be capped)")
