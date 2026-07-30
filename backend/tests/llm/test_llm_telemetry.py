"""Telemetry persistence tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
from app.core.config import get_settings
from app.modules.llm.catalog import get_model
from app.modules.llm.models import CostRecord, LlmExecution
from app.modules.llm.telemetry import LlmTelemetry, NoOpTracer, TelemetryContext
from app.modules.llm.types import Usage
from app.modules.users.models import User
from sqlalchemy import select
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
    """Unique throwaway user so the NOT NULL FK has a real target."""
    user = User(username=f"telemetry-{uuid.uuid4().hex[:10]}", password_hash=None)
    session.add(user)
    await session.flush()
    return user


@pytest.mark.integration
@pytest.mark.asyncio
async def test_telemetry_writes_execution_and_cost(llm_session: AsyncSession) -> None:
    model = get_model("gemini", "gemini-3.5-flash-lite")
    assert model is not None
    user = await _user(llm_session)
    telemetry = LlmTelemetry(llm_session, NoOpTracer())

    async def _call() -> tuple[str, Usage]:
        return "ok", Usage(tokens_in=10, tokens_out=5)

    result = await telemetry.record_call(
        TelemetryContext(
            task="chat",
            model=model,
            fallback_used=False,
            user_id=user.id,
        ),
        _call,
    )
    assert result == "ok"

    executions = (
        (await llm_session.execute(select(LlmExecution).order_by(LlmExecution.created_at.desc())))
        .scalars()
        .all()
    )
    assert executions
    assert executions[0].task == "chat"
    assert executions[0].tokens_in == 10
    assert executions[0].status == "ok"
    assert executions[0].user_id == user.id

    costs = (
        (await llm_session.execute(select(CostRecord).order_by(CostRecord.created_at.desc())))
        .scalars()
        .all()
    )
    assert costs
    assert costs[0].llm_execution_id == executions[0].id
