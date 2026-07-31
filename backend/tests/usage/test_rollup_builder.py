"""Builder: idempotency, late-arriving convergence, backfill equivalence."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.modules.llm.models import LlmExecution
from app.modules.scraping.models import ScrapingJob, ScrapingSource
from app.modules.usage.kinds import UsageMetric
from app.modules.usage.models import LlmModelDaily, LlmTaskDaily, UsageDaily
from app.modules.usage.rollup import roll_day
from app.modules.users.schemas import UserCreate
from app.modules.users.service import UserService
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        for model in (UsageDaily, LlmModelDaily, LlmTaskDaily):
            await db.execute(delete(model))
        await db.execute(delete(LlmExecution))
        await db.commit()
        yield db
        await db.rollback()
        for model in (UsageDaily, LlmModelDaily, LlmTaskDaily):
            await db.execute(delete(model))
        await db.execute(delete(LlmExecution))
        await db.commit()
    await engine.dispose()


async def _uid(session: AsyncSession) -> UUID:
    user = await UserService(session).ensure_user(
        UserCreate(username=f"rol_{uuid4().hex[:8]}", password="test-pass-123")
    )
    return user.id


async def _rolled(session: AsyncSession, uid: UUID, metric: UsageMetric) -> float:
    stmt = select(UsageDaily.amount).where(
        UsageDaily.user_id == uid, UsageDaily.metric == metric.value
    )
    value = (await session.execute(stmt)).scalar_one_or_none()
    return float(value) if value is not None else 0.0


async def _any_source(session: AsyncSession) -> ScrapingSource:
    source = (await session.execute(select(ScrapingSource).limit(1))).scalar_one_or_none()
    if source is None:
        source = ScrapingSource(name=f"src_{uuid4().hex[:8]}", base_domains=["example.com"])
        session.add(source)
        await session.flush()
    return source


@pytest.mark.integration
@pytest.mark.asyncio
async def test_roll_day_is_idempotent(session: AsyncSession) -> None:
    uid = await _uid(session)
    session.add(
        LlmExecution(
            user_id=uid,
            task="chat_tools",
            provider="gemini",
            model="m",
            tokens_in=100,
            tokens_out=50,
            cost=0.2,
            latency_ms=1,
            status="ok",
        )
    )
    await session.commit()
    today = datetime.now(UTC).date()

    await roll_day(session, today)
    await session.commit()
    first = (await session.execute(select(UsageDaily))).scalars().all()
    await roll_day(session, today)
    await session.commit()
    second = (await session.execute(select(UsageDaily))).scalars().all()

    assert len(first) == len(second)
    assert await _rolled(session, uid, UsageMetric.LLM_TOKENS_IN) == 100.0
    model_rows = (await session.execute(select(LlmModelDaily))).scalars().all()
    assert len(model_rows) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_late_arriving_facts_converge_on_reroll(session: AsyncSession) -> None:
    """A running scrape job's chapters grow after the first roll (spec §6)."""
    uid = await _uid(session)
    source = await _any_source(session)
    job = ScrapingJob(
        user_id=uid,
        source_id=source.id,
        start_url="https://x/y",
        mode="range",
        status="running",
        chapters_done=10,
    )
    session.add(job)
    await session.commit()
    today = datetime.now(UTC).date()

    await roll_day(session, today)
    await session.commit()
    assert await _rolled(session, uid, UsageMetric.SCRAPE_CHAPTERS) == 10.0

    await session.execute(
        update(ScrapingJob)
        .where(ScrapingJob.id == job.id)
        .values(chapters_done=25, status="complete")
    )
    await session.commit()
    await roll_day(session, today)  # the nightly window re-roll
    await session.commit()
    assert await _rolled(session, uid, UsageMetric.SCRAPE_CHAPTERS) == 25.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rolled_equals_raw_aggregate(session: AsyncSession) -> None:
    """Backfill equivalence: rolled totals == the on-the-fly aggregate."""
    from app.modules.llm.repository import LlmRepository
    from app.modules.usage.repository import day_window

    uid = await _uid(session)
    session.add_all(
        [
            LlmExecution(
                user_id=uid,
                task="chat_tools",
                provider="gemini",
                model="m",
                tokens_in=70,
                tokens_out=30,
                cost=0.3,
                latency_ms=1,
                status="ok",
            ),
            LlmExecution(
                user_id=uid,
                task="summarize",
                provider="gemini",
                model="m",
                tokens_in=20,
                tokens_out=10,
                cost=0.1,
                latency_ms=1,
                status="ok",
            ),
        ]
    )
    await session.commit()
    today = datetime.now(UTC).date()
    await roll_day(session, today)
    await session.commit()

    start, end = day_window(today)
    raw = await LlmRepository(session).usage_summary_for_user(
        uid, period_start=start, period_end=end
    )
    rolled_in = await _rolled(session, uid, UsageMetric.LLM_TOKENS_IN)
    rolled_out = await _rolled(session, uid, UsageMetric.LLM_TOKENS_OUT)
    rolled_cost = await _rolled(session, uid, UsageMetric.LLM_COST_USD)
    assert (rolled_in, rolled_out) == (raw.tokens_in, raw.tokens_out)
    assert rolled_cost == pytest.approx(raw.total_cost)
