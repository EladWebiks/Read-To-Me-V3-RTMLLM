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
        await _seed(session)
        await session.commit()
        return
    async with SessionLocal() as owned:
        await _seed(owned)
        await owned.commit()


async def _seed(session: AsyncSession) -> None:
    repo = MembershipRepository(session)
    if await repo.get_by_slug(DEFAULT_SLUG) is not None:
        return
    has_default = await repo.get_default() is not None
    repo.add(
        MembershipTier(
            slug=DEFAULT_SLUG, label="Free", rank=0, is_active=True, is_default=not has_default
        )
    )
    membership_registry.invalidate()  # every memberships write invalidates the snapshot
    logger.info("seeding default membership tier", extra={"slug": DEFAULT_SLUG})
