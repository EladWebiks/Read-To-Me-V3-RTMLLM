"""Metric registry + rollup repository roundtrip (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.modules.quotas.kinds import QuotaKind
from app.modules.usage.kinds import (
    KIND_METRICS,
    METRIC_REGISTRY,
    REJECTION_METRICS,
    UsageFact,
    UsageMetric,
)
from app.modules.usage.models import QuotaRejection, UsageDaily
from app.modules.usage.repository import UsageRepository
from app.modules.users.schemas import UserCreate
from app.modules.users.service import UserService
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(delete(UsageDaily))
        await db.execute(delete(QuotaRejection))
        await db.commit()
        yield db
        await db.rollback()
        await db.execute(delete(UsageDaily))
        await db.execute(delete(QuotaRejection))
        await db.commit()
    await engine.dispose()


async def _user_id(session: AsyncSession) -> UUID:
    user = await UserService(session).ensure_user(
        UserCreate(username=f"usg_{uuid4().hex[:8]}", password="test-pass-123")
    )
    return user.id


@pytest.mark.unit
def test_registry_covers_every_metric_and_kind() -> None:
    assert set(METRIC_REGISTRY) == set(UsageMetric)
    # Every quota kind except the level meter maps to usage metrics...
    assert set(KIND_METRICS) == set(QuotaKind) - {QuotaKind.STORAGE_BYTES}
    # ...and every kind (storage included) has a rejection metric.
    assert set(REJECTION_METRICS) == set(QuotaKind)
    assert KIND_METRICS[QuotaKind.LLM_TOKENS] == (
        UsageMetric.LLM_TOKENS_IN,
        UsageMetric.LLM_TOKENS_OUT,
    )


@pytest.mark.unit
def test_usage_settings_default_and_registry() -> None:
    from app.modules.runtime_config.registry import TUNABLE_FIELDS

    from tests.factories import make_settings

    assert make_settings().usage.rollup_window_days == 7
    assert make_settings(usage_rollup_window_days=3).usage.rollup_window_days == 3
    assert "usage.rollup_window_days" in TUNABLE_FIELDS


@pytest.mark.integration
@pytest.mark.asyncio
async def test_replace_day_is_idempotent_and_sparse(session: AsyncSession) -> None:
    uid = await _user_id(session)
    repo = UsageRepository(session)
    day = date(2026, 7, 30)
    facts = [
        UsageFact(uid, UsageMetric.LLM_TOKENS_IN, 100.0),
        UsageFact(uid, UsageMetric.LLM_TOKENS_OUT, 40.0),
        UsageFact(uid, UsageMetric.AUDIO_CHAPTERS, 0.0),  # sparse: must be dropped
    ]
    await repo.replace_day(day, facts)
    await repo.replace_day(day, facts)  # idempotent
    await session.commit()

    rows = (await session.execute(select(UsageDaily))).scalars().all()
    assert len(rows) == 2  # zero-amount row omitted, no duplicates
    amount = await repo.rolled_amount(
        uid,
        (UsageMetric.LLM_TOKENS_IN, UsageMetric.LLM_TOKENS_OUT),
        start_day=date(2026, 7, 1),
        end_day=date(2026, 8, 1),
    )
    assert amount == 140.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rolled_amount_excludes_end_day(session: AsyncSession) -> None:
    """[start_day, end_day) — the hybrid read must not double-count today."""
    uid = await _user_id(session)
    repo = UsageRepository(session)
    await repo.replace_day(date(2026, 7, 30), [UsageFact(uid, UsageMetric.LLM_COST_USD, 1.0)])
    await repo.replace_day(date(2026, 7, 31), [UsageFact(uid, UsageMetric.LLM_COST_USD, 9.0)])
    await session.commit()
    amount = await repo.rolled_amount(
        uid,
        (UsageMetric.LLM_COST_USD,),
        start_day=date(2026, 7, 1),
        end_day=date(2026, 7, 31),
    )
    assert amount == 1.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rejections_roundtrip_to_facts(session: AsyncSession) -> None:
    uid = await _user_id(session)
    repo = UsageRepository(session)
    repo.add_rejection(uid, QuotaKind.LLM_TOKENS, "chat")
    repo.add_rejection(uid, QuotaKind.LLM_TOKENS, "chat")
    repo.add_rejection(uid, QuotaKind.AUDIO_CHAPTERS, "api")
    await session.commit()

    from datetime import UTC, datetime

    facts = await repo.rejection_facts(datetime.now(UTC).date())
    by_metric = {(f.user_id, f.metric): f.amount for f in facts}
    assert by_metric[(uid, UsageMetric.REJECTED_LLM_TOKENS)] == 2.0
    assert by_metric[(uid, UsageMetric.REJECTED_AUDIO_CHAPTERS)] == 1.0
