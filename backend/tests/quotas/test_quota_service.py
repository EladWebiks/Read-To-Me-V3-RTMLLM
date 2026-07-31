"""Quota kinds registry, window math, limits resolution, enforce (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.modules.quotas.exceptions import QuotaExceededError
from app.modules.quotas.kinds import KIND_REGISTRY, QuotaKind
from app.modules.quotas.models import MembershipQuota
from app.modules.quotas.service import QuotaLimits, QuotaService
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserRead
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(delete(MembershipQuota))
        await db.commit()
        yield db
        await db.rollback()
        await db.execute(delete(MembershipQuota))
        await db.commit()
    await engine.dispose()


def _user(*, is_admin: bool = False) -> UserRead:
    return UserRead(
        id=uuid4(),
        username="quota-test",
        email=None,
        is_admin=is_admin,
        membership=Membership.FREE,
        created_at=datetime.now(UTC),
    )


@pytest.mark.unit
def test_registry_covers_every_kind() -> None:
    assert set(KIND_REGISTRY) == set(QuotaKind)
    for meta in KIND_REGISTRY.values():
        assert meta.window in ("month", "standing")


@pytest.mark.unit
def test_month_window_mid_year_and_december() -> None:
    start, end = QuotaService.current_month_window(datetime(2026, 7, 31, 23, 59, tzinfo=UTC))
    assert (start, end) == (datetime(2026, 7, 1, tzinfo=UTC), datetime(2026, 8, 1, tzinfo=UTC))
    start, end = QuotaService.current_month_window(datetime(2026, 12, 15, tzinfo=UTC))
    assert (start, end) == (datetime(2026, 12, 1, tzinfo=UTC), datetime(2027, 1, 1, tzinfo=UTC))


@pytest.mark.unit
def test_enforce_blocks_at_and_over_never_under() -> None:
    limits = QuotaLimits(exempt=False, values={QuotaKind.LLM_TOKENS: 100.0})
    QuotaService.enforce(QuotaKind.LLM_TOKENS, 99, limits, resets_at=None)  # under: fine
    with pytest.raises(QuotaExceededError) as excinfo:
        QuotaService.enforce(
            QuotaKind.LLM_TOKENS,
            100,
            limits,
            resets_at=datetime(2026, 8, 1, tzinfo=UTC),
        )
    assert excinfo.value.kind is QuotaKind.LLM_TOKENS
    assert excinfo.value.resets_at is not None
    assert "2026-08-01" in str(excinfo.value)


@pytest.mark.unit
def test_enforce_skips_unlimited_and_exempt() -> None:
    QuotaService.enforce(
        QuotaKind.LLM_TOKENS,
        10**12,
        QuotaLimits(exempt=False, values={}),
        resets_at=None,
    )
    QuotaService.enforce(
        QuotaKind.LLM_TOKENS,
        10**12,
        QuotaLimits(exempt=True, values={QuotaKind.LLM_TOKENS: 1.0}),
        resets_at=None,
    )


@pytest.mark.unit
def test_standing_kind_copy_has_no_reset_date() -> None:
    exc = QuotaExceededError(QuotaKind.STORAGE_BYTES, limit=100.0, used=150.0, resets_at=None)
    assert "Resets" not in str(exc)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_limits_for_reads_rows_and_exempts_admins(session: AsyncSession) -> None:
    session.add(
        MembershipQuota(
            membership=Membership.FREE.value,
            quota_kind=QuotaKind.LLM_TOKENS.value,
            limit_value=5000.0,
        )
    )
    await session.commit()
    service = QuotaService(session)

    limits = await service.limits_for(_user())
    assert limits.limit(QuotaKind.LLM_TOKENS) == 5000.0
    assert limits.limit(QuotaKind.LLM_COST_USD) is None  # row absent = unlimited
    assert limits.any_limited(QuotaKind.LLM_TOKENS, QuotaKind.LLM_COST_USD)

    admin = await service.limits_for(_user(is_admin=True))
    assert admin.exempt is True
    assert admin.limit(QuotaKind.LLM_TOKENS) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unknown_kind_rows_are_skipped(session: AsyncSession) -> None:
    """A row for a since-removed kind must not break resolution (fail-open)."""
    session.add(
        MembershipQuota(
            membership=Membership.FREE.value, quota_kind="retired_kind", limit_value=1.0
        )
    )
    await session.commit()
    limits = await QuotaService(session).limits_for(_user())
    assert limits.values == {}
