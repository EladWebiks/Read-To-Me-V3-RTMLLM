"""Seeding contract: every registered tier gets a row; edits survive (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.seed import seed_membership_policies
from app.modules.users import membership_registry as reg
from app.modules.users.membership_service import MembershipService
from app.modules.users.models import MembershipTier
from app.modules.users.schemas import MembershipCreate
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ACTOR = uuid4()


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        # The seed reads the registry through the cached snapshot; a stale one
        # left by another suite would decide which rows get written here.
        reg.invalidate()
        yield db
        # Leave a freshly seeded table and a `free`-only registry behind.
        await db.execute(delete(MembershipPolicy))
        await db.execute(delete(MembershipTier).where(MembershipTier.slug != "free"))
        await db.commit()
        reg.invalidate()
        await seed_membership_policies(db)
        reg.invalidate()
    await engine.dispose()


async def _rows(session: AsyncSession) -> list[MembershipPolicy]:
    return list((await session.execute(select(MembershipPolicy))).scalars().all())


async def _register_premium(session: AsyncSession) -> None:
    """Add a second tier so the seed has more than the backfilled default."""
    await MembershipService(session).create_tier(
        MembershipCreate(slug="premium", label="Premium", rank=1), actor_id=ACTOR
    )
    await session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_every_registered_tier_has_all_null_seed_row(
    session: AsyncSession,
) -> None:
    await _register_premium(session)
    await session.execute(delete(MembershipPolicy))
    await session.commit()
    await seed_membership_policies(session)
    rows = await _rows(session)
    assert {row.membership for row in rows} == {"free", "premium"}
    assert len(rows) == 2
    for row in rows:
        assert row.max_tool_iters is None
        assert row.max_external_calls is None
        assert row.max_turn_tokens_in is None
        assert row.max_turn_tokens_out is None
        assert row.max_turn_cost_usd is None
        assert row.run_deadline_seconds is None
        assert row.max_hitl_rounds is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_seed_is_idempotent_and_never_overwrites_edits(
    session: AsyncSession,
) -> None:
    await _register_premium(session)
    await session.execute(delete(MembershipPolicy))
    await session.commit()
    await seed_membership_policies(session)
    row = (
        await session.execute(
            select(MembershipPolicy).where(MembershipPolicy.membership == "free")
        )
    ).scalar_one()
    row.max_tool_iters = 2
    await session.commit()

    await seed_membership_policies(session)

    await session.refresh(row)
    assert row.max_tool_iters == 2
    assert len(await _rows(session)) == 2
