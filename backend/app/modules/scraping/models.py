"""SQLAlchemy models for the scraping module."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ScrapingSource(Base):
    """Known scraping source (novelbin, novelfull, etc.)."""

    __tablename__ = "scraping_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    base_domains: Mapped[list[str]] = mapped_column(ARRAY(String(256)))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    rate_limit_seconds: Mapped[float] = mapped_column(Float, default=1.5)
    terms_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ScrapingJob(Base):
    """Durable scraping job created by a user."""

    __tablename__ = "scraping_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scraping_sources.id")
    )
    book_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id"), nullable=True
    )
    start_url: Mapped[str] = mapped_column(String(2048))
    mode: Mapped[str] = mapped_column(String(16), default="full")
    chapter_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chapter_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_chapters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    chapters_done: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ScrapingJobItem(Base):
    """Individual chapter within a scraping job."""

    __tablename__ = "scraping_job_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scraping_jobs.id"), index=True
    )
    chapter_number: Mapped[int] = mapped_column(Integer)
    url: Mapped[str] = mapped_column(String(2048))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
