"""SQLAlchemy models for orchestration-owned AI policy."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MembershipPolicy(Base):
    """Per-tier PER-TURN cap overrides — one row per Membership enum value.

    NULL = inherit the effective runtime setting (there is always a global
    fallback; per-turn caps are safety rails that can never be absent).
    Monthly/standing quotas do NOT live here — they are keyed rows in the
    quotas module's membership_quotas table (spec §3.0/§3.1).
    """

    __tablename__ = "membership_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    membership: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    # Per-turn budget overrides. Field names match LlmRuntimeSettings exactly
    # so resolution can iterate one shared name list. NULL = inherit.
    max_tool_iters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_external_calls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_turn_tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_turn_tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_turn_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    run_deadline_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_hitl_rounds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
