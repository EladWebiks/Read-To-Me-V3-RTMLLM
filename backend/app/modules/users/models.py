"""SQLAlchemy models for users."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, false, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.modules.users.membership import Membership


class User(Base):
    """Application user (single-user now, multi-user-ready)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_sub: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=True,
    )
    picture_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
    )
    membership: Mapped[str] = mapped_column(
        String(32),
        default=Membership.FREE,
        server_default=Membership.FREE.value,
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
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
