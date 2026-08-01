"""Schema-level guarantees for the memberships registry (needs Postgres)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from app.core.config import get_settings
from app.modules.users.models import MembershipTier, User
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
        await db.rollback()
    await engine.dispose()


@pytest.mark.integration
async def test_free_tier_backfilled(session: AsyncSession) -> None:
    row = (
        await session.execute(
            text("SELECT label, rank, is_active, is_default FROM memberships WHERE slug = 'free'")
        )
    ).one()
    assert row == ("Free", 0, True, True)


@pytest.mark.integration
async def test_user_membership_fk_blocks_unknown_slug(session: AsyncSession) -> None:
    session.add(User(username=f"fk-{uuid.uuid4().hex[:8]}", membership="no-such-tier"))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.integration
async def test_only_one_default_tier(session: AsyncSession) -> None:
    session.add(
        MembershipTier(slug="premium2", label="Premium 2", rank=1, is_active=True, is_default=True)
    )
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()
