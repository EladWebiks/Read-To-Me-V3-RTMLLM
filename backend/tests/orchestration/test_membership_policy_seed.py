"""Seeding contract: every enum value gets a row; edits survive (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from app.core.config import get_settings
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.seed import seed_membership_policies
from app.modules.users.membership import Membership
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
        # Leave a freshly seeded table behind for other suites.
        await db.execute(delete(MembershipPolicy))
        await db.commit()
        await seed_membership_policies(db)
    await engine.dispose()


async def _rows(session: AsyncSession) -> list[MembershipPolicy]:
    return list((await session.execute(select(MembershipPolicy))).scalars().all())


@pytest.mark.integration
@pytest.mark.asyncio
async def test_every_membership_value_has_all_null_seed_row(
    session: AsyncSession,
) -> None:
    await session.execute(delete(MembershipPolicy))
    await session.commit()
    await seed_membership_policies(session)
    rows = await _rows(session)
    assert {row.membership for row in rows} == {m.value for m in Membership}
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
    await session.execute(delete(MembershipPolicy))
    await session.commit()
    await seed_membership_policies(session)
    row = (
        await session.execute(
            select(MembershipPolicy).where(MembershipPolicy.membership == Membership.FREE.value)
        )
    ).scalar_one()
    row.max_tool_iters = 2
    await session.commit()

    await seed_membership_policies(session)

    await session.refresh(row)
    assert row.max_tool_iters == 2
    assert len(await _rows(session)) == len(list(Membership))
