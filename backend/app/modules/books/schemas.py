"""Book schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BookCreate(BaseModel):
    """Create-book payload."""

    title: str = Field(min_length=1, max_length=512)
    author: str = Field(default="", max_length=256)
    description: str = ""
    language: str = Field(default="en", max_length=16)
    starting_chapter_number: int = Field(default=1, ge=0)


class BookUpdate(BaseModel):
    """Partial book update."""

    title: str | None = Field(default=None, min_length=1, max_length=512)
    author: str | None = Field(default=None, max_length=256)
    description: str | None = None
    language: str | None = Field(default=None, max_length=16)
    starting_chapter_number: int | None = Field(default=None, ge=0)


class BookRead(BaseModel):
    """Public book representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    author: str
    description: str
    language: str
    cover_object_key: str | None
    cover_url: str | None = None
    starting_chapter_number: int
    status: str
    created_at: datetime
    updated_at: datetime
    chapter_count: int = 0
    last_read_chapter_number: int | None = None
    last_read_at: datetime | None = None
