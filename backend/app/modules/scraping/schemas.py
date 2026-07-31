"""Scraping API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ScrapePreviewRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)


class ScrapePreviewResponse(BaseModel):
    source: str
    book_url: str | None
    title: str
    author: str
    cover_url: str
    first_chapter_url: str


class ScrapeJobCreate(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    book_url: str | None = Field(default=None, max_length=2048)
    mode: str = Field(default="full", pattern="^(full|range)$")
    chapter_from: int | None = Field(default=None, ge=0)
    chapter_to: int | None = Field(default=None, ge=0)
    max_chapters: int | None = Field(default=None, ge=1, le=5000)
    starting_chapter: int | None = Field(default=None, ge=0)


class ScrapeJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    book_id: UUID | None
    book_title: str | None = None
    start_url: str
    mode: str
    chapter_from: int | None
    chapter_to: int | None
    max_chapters: int | None
    status: str
    chapters_done: int
    message: str
    error: str | None
    created_at: datetime
    updated_at: datetime


class ScrapeJobAdminRead(BaseModel):
    """Backoffice view of one scraping job (cross-user, read-only, raw error)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    book_id: UUID | None
    book_title: str | None = None
    start_url: str
    mode: str
    status: str
    chapters_done: int
    chapter_from: int | None
    chapter_to: int | None
    message: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime
