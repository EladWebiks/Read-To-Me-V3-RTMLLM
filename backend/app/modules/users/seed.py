"""Seed the memberships registry (insert-if-missing; never overwrites edits)."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.modules.users import membership_registry
from app.modules.users.membership import DEFAULT_SLUG
from app.modules.users.membership_repository import MembershipRepository
from app.modules.users.models import MembershipTier

logger = logging.getLogger(__name__)


async def seed_default_membership(session: AsyncSession | None = None) -> None:
    """Ensure the 'free' tier row exists. Idempotent; a restart never
    reverts admin edits (same contract as the LLM catalog seed)."""
    if session is not None:
        inserted = await _seed(session)
        await session.commit()
    else:
        async with SessionLocal() as owned:
            inserted = await _seed(owned)
            await owned.commit()
    if inserted:
        # Invalidate only after commit: invalidating first would let a
        # concurrent coroutine re-warm the snapshot from a pre-insert read
        # and hold that stale (missing-row) view for the full TTL.
        membership_registry.invalidate()


async def _seed(session: AsyncSession) -> bool:
    """Insert the 'free' row if missing. Returns whether it inserted."""
    repo = MembershipRepository(session)
    if await repo.get_by_slug(DEFAULT_SLUG) is not None:
        return False
    has_default = await repo.get_default() is not None
    repo.add(
        MembershipTier(
            slug=DEFAULT_SLUG, label="Free", rank=0, is_active=True, is_default=not has_default
        )
    )
    logger.info("seeding default membership tier", extra={"slug": DEFAULT_SLUG})
    return True
