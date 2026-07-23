"""Reading progress schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProgressUpsert(BaseModel):
    """Save reading position."""

    chapter_id: UUID
    chapter_number: int = Field(ge=0)
    paragraph_index: int = Field(default=0, ge=0)
    word_index: int = Field(default=0, ge=0)


class ProgressRead(BaseModel):
    """Current reading progress for a book."""

    model_config = ConfigDict(from_attributes=True)

    book_id: UUID
    chapter_id: UUID
    chapter_number: int
    paragraph_index: int
    word_index: int
    updated_at: datetime
