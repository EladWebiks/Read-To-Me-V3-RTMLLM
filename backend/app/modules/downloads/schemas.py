"""Download job schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.audio.schemas import ProviderName


class DownloadCreate(BaseModel):
    """Create a chapter-range MP3 job."""

    book_id: UUID
    chapter_from: int = Field(ge=0)
    chapter_to: int = Field(ge=0)
    provider: ProviderName = "edge"
    voice: str | None = None
    rate: float = Field(default=1.0, ge=0.5, le=2.0)


class DownloadJobRead(BaseModel):
    """Download job status."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    book_id: UUID
    chapter_from: int
    chapter_to: int
    provider: str
    voice: str
    rate: str
    status: str
    ready_count: int
    total_count: int
    object_key: str | None
    error: str | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DownloadUrlRead(BaseModel):
    """Signed download URL."""

    url: str
    expires_at: datetime


class DownloadCleanResult(BaseModel):
    """Result of cleaning jobs for a book."""

    deleted: int
