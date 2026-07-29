"""Chapter schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChapterCreate(BaseModel):
    """Create-chapter payload."""

    title: str = Field(default="", max_length=512)
    content: str = Field(min_length=1)
    chapter_number: int | None = Field(default=None, ge=0)


class ChapterUpdate(BaseModel):
    """Partial chapter update."""

    title: str | None = Field(default=None, max_length=512)
    content: str | None = None
    chapter_number: int | None = Field(default=None, ge=0)


class ChapterSummary(BaseModel):
    """Chapter without full content (for lists)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    book_id: UUID
    chapter_number: int
    title: str
    word_count: int
    created_at: datetime
    updated_at: datetime


class ChapterRead(ChapterSummary):
    """Full chapter including content."""

    content: str


class ChapterContentHit(BaseModel):
    """One chapter match with a short snippet (not full content)."""

    chapter_id: UUID
    book_id: UUID
    chapter_number: int
    chapter_title: str
    snippet: str = Field(description="Short highlight around the match")
