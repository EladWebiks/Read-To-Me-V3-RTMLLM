"""SQLAlchemy models for discovery candidates."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DiscoveredBook(Base):
    """Normalized book candidate found via discovery (not yet in library)."""

    __tablename__ = "discovered_books"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(String(512))
    normalized_title: Mapped[str] = mapped_column(String(512), index=True)
    author: Mapped[str] = mapped_column(String(256), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(16), default="en")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class BookSource(Base):
    """One site listing for a discovered book."""

    __tablename__ = "book_sources"
    __table_args__ = (UniqueConstraint("source", "book_url", name="uq_book_sources_source_url"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    discovered_book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discovered_books.id", ondelete="CASCADE"),
        index=True,
    )
    source: Mapped[str] = mapped_column(String(64), index=True)
    book_url: Mapped[str] = mapped_column(String(2048))
    first_chapter_url: Mapped[str] = mapped_column(String(2048), default="")
    chapter_count_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
