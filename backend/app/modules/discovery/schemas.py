"""Discovery API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BookSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: str
    book_url: str
    first_chapter_url: str
    chapter_count_estimate: int | None
    recommended: bool = False
    created_at: datetime
    updated_at: datetime


class DiscoveredBookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    author: str
    description: str
    language: str
    already_owned: bool = False
    sources: list[BookSourceRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DiscoverySearchResponse(BaseModel):
    query: str
    results: list[DiscoveredBookRead]


class DiscoveryRecommendItem(BaseModel):
    """One ranked recommend result with match evidence."""

    book: DiscoveredBookRead
    evidence: list[str] = Field(default_factory=list)
    # Best known chapter count across scrape sources (None = unknown on our sites).
    scrapable_chapters: int | None = None


class DiscoveryRecommendResponse(BaseModel):
    """Bounded batch discovery recommendation."""

    queries: list[str]
    themes: list[str] = Field(default_factory=list)
    limit: int
    results: list[DiscoveryRecommendItem] = Field(default_factory=list)
