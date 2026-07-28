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
