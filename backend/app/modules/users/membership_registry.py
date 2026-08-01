"""DB-backed membership tier registry: async snapshot refresh, sync reads.

Same per-process TTL pattern as modules/llm/catalog.py: writers call
invalidate() so the writing process sees changes immediately; other
processes (arq worker, other API workers) converge within the TTL.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from time import monotonic
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import MembershipTier

CACHE_TTL_SECONDS = 30.0

_state: dict[str, Any] = {"snapshot": None, "expires_at": 0.0}


@dataclass(frozen=True, slots=True)
class TierSpec:
    """Immutable snapshot view of one membership tier."""

    slug: str
    label: str
    description: str | None
    price_label: str | None
    rank: int
    is_active: bool
    is_default: bool


def current_snapshot() -> tuple[TierSpec, ...]:
    """Sync view of the tier registry; empty when cold or expired."""
    snapshot = _state["snapshot"]
    if snapshot is None or monotonic() >= float(_state["expires_at"]):
        return ()
    return tuple(snapshot)


def put_snapshot(specs: Sequence[TierSpec]) -> None:
    """Cache a snapshot for the TTL window (also a test hook)."""
    _state["snapshot"] = tuple(specs)
    _state["expires_at"] = monotonic() + CACHE_TTL_SECONDS


def invalidate() -> None:
    """Drop the snapshot now (every memberships write calls this; test hook)."""
    _state["snapshot"] = None
    _state["expires_at"] = 0.0


async def ensure_loaded(session: AsyncSession) -> tuple[TierSpec, ...]:
    """Return a warm snapshot, loading from the DB when cold or expired."""
    snapshot = _state["snapshot"]
    if snapshot is not None and monotonic() < float(_state["expires_at"]):
        return tuple(snapshot)
    stmt = select(MembershipTier).order_by(MembershipTier.rank, MembershipTier.slug)
    rows = (await session.execute(stmt)).scalars().all()
    specs = tuple(
        TierSpec(
            slug=row.slug,
            label=row.label,
            description=row.description,
            price_label=row.price_label,
            rank=row.rank,
            is_active=row.is_active,
            is_default=row.is_default,
        )
        for row in rows
    )
    put_snapshot(specs)
    return specs


def rank_of(slug: str) -> int | None:
    """Rank of a tier in the current snapshot; None when unknown or cold."""
    for tier in current_snapshot():
        if tier.slug == slug:
            return tier.rank
    return None


def label_of(slug: str) -> str | None:
    """Label of a tier in the current snapshot; None when unknown or cold."""
    for tier in current_snapshot():
        if tier.slug == slug:
            return tier.label
    return None


async def label_for(session: AsyncSession, slug: str) -> str:
    """Warm label lookup for display; falls back to the raw slug (e.g. a
    tier deleted from under an in-flight request never surfaces as None)."""
    await ensure_loaded(session)
    return label_of(slug) or slug
