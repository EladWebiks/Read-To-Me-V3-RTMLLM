"""Seed membership_policies rows (insert-if-missing; never overwrites edits)."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.modules.orchestration.models import MembershipPolicy
from app.modules.users.membership import Membership

logger = logging.getLogger(__name__)


async def seed_membership_policies(session: AsyncSession | None = None) -> None:
    """Ensure one all-NULL policy row exists per Membership value.

    Idempotent, insert-if-missing: a restart never reverts admin edits
    (same contract as the LLM catalog seed). New enum values get their row
    on the next startup even if the migration predates them. All per-turn
    columns stay NULL, which means "inherit" — never "unlimited".
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
    missing = [m.value for m in Membership if m.value not in existing]
    for value in missing:
        session.add(MembershipPolicy(membership=value))
    if missing:
        logger.info("seeding membership policies", extra={"memberships": missing})
