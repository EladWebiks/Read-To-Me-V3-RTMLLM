"""SQLAlchemy models for per-tier usage quotas and per-user overrides."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MembershipQuota(Base):
    """One quota limit for one (membership, kind). Row absent = unlimited.

    Sparse by design: no seeding, no NULL limits. limit_value is float64 —
    exact for integer counts up to 2^53 (tokens/chapters/bytes all fit).
    """

    __tablename__ = "membership_quotas"
    __table_args__ = (
        UniqueConstraint("membership", "quota_kind", name="uq_membership_quotas_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    membership: Mapped[str] = mapped_column(String(32), index=True)
    quota_kind: Mapped[str] = mapped_column(String(32))
    limit_value: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserQuotaOverride(Base):
    """One per-user quota override. Row absent = the user's tier limit applies.

    Sparse like membership_quotas; specificity wins: admin exempt > user
    override > tier row > unlimited. Looser AND tighter overrides are legal.
    """

    __tablename__ = "user_quota_overrides"
    __table_args__ = (
        UniqueConstraint("user_id", "quota_kind", name="uq_user_quota_overrides_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    quota_kind: Mapped[str] = mapped_column(String(32))
    limit_value: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
