"""SQLAlchemy models for download jobs."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DownloadJob(Base):
    """Durable chapter-range MP3 generation job."""

    __tablename__ = "download_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        index=True,
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("books.id"),
        index=True,
    )
    chapter_from: Mapped[int] = mapped_column(Integer)
    chapter_to: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(16))
    voice: Mapped[str] = mapped_column(String(128))
    rate: Mapped[str] = mapped_column(String(16), default="1.0")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    ready_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    # Soft delete (golden rule 6): delete/clean/TTL-purge free the MinIO
    # assets but KEEP the row — the monthly audio_chapters meter must not
    # shrink when jobs disappear. Reads filter this; the meter does not.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
