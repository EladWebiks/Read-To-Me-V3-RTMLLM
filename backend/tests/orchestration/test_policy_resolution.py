"""Resolution chain permutations: tier set/NULL x runtime override present/absent."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.core.config import Settings, get_settings
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.policy import PolicyService
from app.modules.orchestration.seed import seed_membership_policies
from app.modules.runtime_config import cache
from app.modules.runtime_config.service import RuntimeConfigService
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.factories import make_settings


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
        await db.rollback()
        await db.execute(delete(MembershipPolicy))
        await db.commit()
        await seed_membership_policies(db)
    await engine.dispose()


def _user(membership: str = "free", *, is_admin: bool = False) -> UserRead:
    """resolve() only reads membership/is_admin — no DB user needed."""
    return UserRead(
        id=uuid4(),
        username="policy-test",
        email=None,
        is_admin=is_admin,
        membership=membership,
        created_at=datetime.now(UTC),
    )


async def _set_free_tier(session: AsyncSession, **values: int | float | None) -> None:
    await session.execute(delete(MembershipPolicy))
    await session.commit()
    await seed_membership_policies(session)
    row = (
        await session.execute(
            select(MembershipPolicy).where(MembershipPolicy.membership == "free")
        )
    ).scalar_one()
    for field, value in values.items():
        setattr(row, field, value)
    await session.commit()


def _effective(base: Settings, **runtime_overrides: int | float) -> Settings:
    """Simulate get_effective_settings output (runtime_config layer applied)."""
    runtime = base.llm_runtime.model_copy(update=runtime_overrides)
    return base.model_copy(update={"llm_runtime": runtime})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tier_null_inherits_env_default(session: AsyncSession) -> None:
    await _set_free_tier(session)  # all NULL
    settings = make_settings(llm_max_tool_iters=9)
    policy = await PolicyService(session, settings).resolve(_user())
    assert policy.max_tool_iters == 9
    assert policy.tier_overridden == ()
    assert policy.membership == "free"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tier_null_inherits_runtime_override(session: AsyncSession) -> None:
    await _set_free_tier(session)
    settings = _effective(make_settings(llm_max_tool_iters=9), max_tool_iters=4)
    policy = await PolicyService(session, settings).resolve(_user())
    assert policy.max_tool_iters == 4


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tier_value_beats_runtime_override_even_when_looser(
    session: AsyncSession,
) -> None:
    # Specificity-wins, NOT strictest-wins: 12 > 4 and the tier still wins.
    await _set_free_tier(session, max_tool_iters=12)
    settings = _effective(make_settings(llm_max_tool_iters=9), max_tool_iters=4)
    policy = await PolicyService(session, settings).resolve(_user())
    assert policy.max_tool_iters == 12
    assert "max_tool_iters" in policy.tier_overridden


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tier_value_beats_env_default(session: AsyncSession) -> None:
    await _set_free_tier(session, max_turn_cost_usd=0.5, max_hitl_rounds=1)
    policy = await PolicyService(session, make_settings()).resolve(_user())
    assert policy.max_turn_cost_usd == 0.5
    assert policy.max_hitl_rounds == 1
    # Untouched fields still inherit.
    assert policy.max_external_calls == make_settings().llm_runtime.max_external_calls


@pytest.mark.integration
@pytest.mark.asyncio
async def test_missing_row_inherits_everything(session: AsyncSession) -> None:
    await session.execute(delete(MembershipPolicy))
    await session.commit()
    settings = make_settings(llm_max_turn_tokens_out=1234)
    policy = await PolicyService(session, settings).resolve(_user())
    assert policy.max_turn_tokens_out == 1234
    assert policy.tier_overridden == ()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_identity_passes_through(session: AsyncSession) -> None:
    await _set_free_tier(session)
    policy = await PolicyService(session, make_settings()).resolve(_user(is_admin=True))
    assert policy.is_admin is True
    assert policy.membership == "free"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_chain_through_real_runtime_config(session: AsyncSession) -> None:
    """End-to-end: app_settings override row -> effective_settings -> resolve."""
    await _set_free_tier(session)
    admin = await UserService(session).ensure_user(
        UserCreate(username=f"pol_{uuid4().hex[:8]}", password="test-pass-123")
    )
    base = make_settings(llm_max_tool_iters=9)
    rc = RuntimeConfigService(session, base)
    await rc.set_override("llm_runtime.max_tool_iters", 3, updated_by=admin.id)
    await session.commit()
    try:
        effective = await RuntimeConfigService(session, base).effective_settings()
        policy = await PolicyService(session, effective).resolve(_user())
        assert policy.max_tool_iters == 3
    finally:
        await rc.clear_override("llm_runtime.max_tool_iters", updated_by=admin.id)
        await session.commit()
        cache.invalidate()
