"""Per-user usage aggregation tests (needs Postgres test DB)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import get_settings
from app.modules.llm.models import LlmExecution
from app.modules.llm.repository import ExecutionWrite, LlmRepository
from app.modules.llm.service import LlmService
from app.modules.users.models import User
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def llm_session() -> AsyncGenerator[AsyncSession, None]:
    """Fresh session against the test DB tables."""
    settings = get_settings()
    engine = create_async_engine(settings.database.url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _user(session: AsyncSession) -> User:
    user = User(username=f"usage-{uuid.uuid4().hex[:10]}", password_hash=None)
    session.add(user)
    await session.flush()
    return user


def _write(user_id: uuid.UUID, tokens_in: int, tokens_out: int, cost: float) -> ExecutionWrite:
    return ExecutionWrite(
        task="chat",
        provider="gemini",
        model="gemini-3.5-flash-lite",
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost=cost,
        latency_ms=100,
        status="ok",
        fallback_used=False,
        trace_id=None,
        error=None,
        unit_cost_in=0.0,
        unit_cost_out=0.0,
        user_id=user_id,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_usage_summary_sums_owner_rows_in_range(llm_session: AsyncSession) -> None:
    repo = LlmRepository(llm_session)
    owner = await _user(llm_session)
    other = await _user(llm_session)
    await repo.record_execution(_write(owner.id, 100, 40, 0.002))
    await repo.record_execution(_write(owner.id, 50, 10, 0.001))
    await repo.record_execution(_write(other.id, 999, 999, 9.9))
    # Owner row far outside the queried period (billing months are half-open).
    llm_session.add(
        LlmExecution(
            user_id=owner.id,
            task="chat",
            provider="gemini",
            model="gemini-3.5-flash-lite",
            tokens_in=777,
            tokens_out=777,
            cost=7.7,
            latency_ms=1,
            status="ok",
            fallback_used=False,
            created_at=datetime.now(UTC) - timedelta(days=90),
        )
    )
    await llm_session.commit()

    now = datetime.now(UTC)
    summary = await LlmService(llm_session, get_settings()).usage_summary(
        owner.id,
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=1),
    )
    assert summary.user_id == owner.id
    assert summary.execution_count == 2
    assert summary.tokens_in == 150
    assert summary.tokens_out == 50
    assert summary.total_cost == pytest.approx(0.003)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_usage_summary_empty_range_returns_zeros(llm_session: AsyncSession) -> None:
    owner = await _user(llm_session)
    await llm_session.commit()
    now = datetime.now(UTC)
    summary = await LlmService(llm_session, get_settings()).usage_summary(
        owner.id,
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=1),
    )
    assert summary.execution_count == 0
    assert summary.tokens_in == 0
    assert summary.tokens_out == 0
    assert summary.total_cost == 0.0
