"""Seed membership_policies rows (insert-if-missing; never overwrites edits)."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.modules.orchestration.models import MembershipPolicy
from app.modules.users.membership_registry import ensure_loaded

logger = logging.getLogger(__name__)


async def seed_membership_policies(session: AsyncSession | None = None) -> None:
    """Ensure one all-NULL policy row exists per memberships row.

    Idempotent, insert-if-missing: a restart never reverts admin edits
    (same contract as the LLM catalog seed). Newly registered tiers get their
    row on the next startup. All per-turn columns stay NULL, which means
    "inherit" — never "unlimited".
    """
    if session is not None:
        await _seed(session)
        await session.commit()
        return
    async with SessionLocal() as owned:
        await _seed(owned)
        await owned.commit()


async def _seed(session: AsyncSession) -> None:
    existing = set((await session.execute(select(MembershipPolicy.membership))).scalars().all())
    tiers = await ensure_loaded(session)
    missing = [t.slug for t in tiers if t.slug not in existing]
    for value in missing:
        session.add(MembershipPolicy(membership=value))
    if missing:
        logger.info("seeding membership policies", extra={"memberships": missing})
