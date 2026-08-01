"""MembershipService lifecycle rules (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.modules.users import membership_registry as reg
from app.modules.users.exceptions import (
    DuplicateMembershipError,
    MembershipLifecycleError,
    UnknownMembershipError,
)
from app.modules.users.membership_service import MembershipService
from app.modules.users.models import User
from app.modules.users.schemas import MembershipCreate, MembershipPatch
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ACTOR = uuid4()


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
        await db.rollback()
    await engine.dispose()


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    reg.invalidate()
    yield
    reg.invalidate()


def _premium() -> MembershipCreate:
    return MembershipCreate(slug="premium", label="Premium", rank=1, price_label="$9/mo")


@pytest.mark.integration
async def test_create_then_list_includes_user_counts(session: AsyncSession) -> None:
    service = MembershipService(session)
    await service.create_tier(_premium(), actor_id=ACTOR)
    session.add(User(username=f"u-{uuid4().hex[:8]}", membership="premium"))
    await session.flush()
    tiers = await service.list_tiers()
    by_slug = {t.slug: t for t in tiers}
    assert by_slug["premium"].user_count == 1
    assert by_slug["premium"].price_label == "$9/mo"
    assert by_slug["free"].is_default is True


@pytest.mark.integration
async def test_create_duplicate_slug_raises(session: AsyncSession) -> None:
    service = MembershipService(session)
    await service.create_tier(_premium(), actor_id=ACTOR)
    with pytest.raises(DuplicateMembershipError):
        await service.create_tier(_premium(), actor_id=ACTOR)


@pytest.mark.integration
async def test_crowning_default_uncrowns_previous(session: AsyncSession) -> None:
    service = MembershipService(session)
    await service.create_tier(_premium(), actor_id=ACTOR)
    await service.update_tier("premium", MembershipPatch(is_default=True), actor_id=ACTOR)
    assert (await service.require_tier("premium")).is_default is True
    assert (await service.require_tier("free")).is_default is False
    assert await service.default_slug() == "premium"


@pytest.mark.integration
async def test_deactivate_migrates_users_and_guards(session: AsyncSession) -> None:
    service = MembershipService(session)
    await service.create_tier(_premium(), actor_id=ACTOR)
    session.add(User(username=f"u-{uuid4().hex[:8]}", membership="premium"))
    await session.flush()
    with pytest.raises(MembershipLifecycleError):  # default is protected
        await service.deactivate_tier("free", "premium", actor_id=ACTOR)
    with pytest.raises(MembershipLifecycleError):  # target must differ
        await service.deactivate_tier("premium", "premium", actor_id=ACTOR)
    tier, moved = await service.deactivate_tier("premium", "free", actor_id=ACTOR)
    assert tier.is_active is False
    assert moved == 1
    with pytest.raises(UnknownMembershipError):  # inactive is not assignable
        await service.require_assignable("premium")
    with pytest.raises(MembershipLifecycleError):  # inactive target rejected
        await service.deactivate_tier("free", "premium", actor_id=ACTOR)


@pytest.mark.integration
async def test_crowning_inactive_tier_is_rejected(session: AsyncSession) -> None:
    """Regression: an inactive tier must never be crownable as default —
    otherwise default_slug() hands new users a slug active_plans excludes."""
    service = MembershipService(session)
    await service.create_tier(_premium(), actor_id=ACTOR)
    await service.deactivate_tier("premium", "free", actor_id=ACTOR)
    with pytest.raises(MembershipLifecycleError):
        await service.update_tier("premium", MembershipPatch(is_default=True), actor_id=ACTOR)
    assert (await service.require_tier("premium")).is_default is False
    # A single PATCH may still reactivate-and-crown in one call.
    row = await service.update_tier(
        "premium", MembershipPatch(is_active=True, is_default=True), actor_id=ACTOR
    )
    assert row.is_active is True
    assert row.is_default is True
    assert await service.default_slug() == "premium"


@pytest.mark.integration
async def test_unknown_slug_raises(session: AsyncSession) -> None:
    with pytest.raises(UnknownMembershipError):
        await MembershipService(session).require_tier("ghost")
