"""Admin summary/by-user = rolled closed days + live today (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from app.core.config import get_settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.llm.models import LlmExecution
from app.modules.usage.kinds import LlmModelFact, LlmTaskFact, UsageFact, UsageMetric
from app.modules.usage.models import LlmModelDaily, LlmTaskDaily, UsageDaily
from app.modules.usage.repository import UsageRepository
from app.modules.users.models import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.dbcleanup import clear_users

_HOST = "test.local"


def _make_db_override(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[], AsyncIterator[AsyncSession]]:
    async def _override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return _override_db


async def _clean(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        for model in (UsageDaily, LlmModelDaily, LlmTaskDaily, LlmExecution):
            await session.execute(delete(model))
        await session.commit()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await _clean(session_factory)
    async with engine.begin() as conn:
        await clear_users(conn)
    app.dependency_overrides[get_db] = _make_db_override(session_factory)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=f"http://{_HOST}") as http:
        yield http
    app.dependency_overrides.clear()
    await _clean(session_factory)
    async with engine.begin() as conn:
        await clear_users(conn)
    await engine.dispose()


async def _seed() -> UUID:
    """Admin; reader with 100/40 tokens rolled YESTERDAY + 10/5 raw TODAY."""
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        admin = User(
            username="hyb-admin",
            email="hyb-admin@example.com",
            password_hash=None,
            google_sub="hyb-admin-sub",
            is_admin=True,
        )
        reader = User(
            username="hyb-reader",
            email="hyb-reader@example.com",
            password_hash=None,
            google_sub="hyb-reader-sub",
            is_admin=False,
        )
        session.add_all([admin, reader])
        await session.flush()
        yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
        repo = UsageRepository(session)
        await repo.replace_day(
            yesterday,
            [
                UsageFact(reader.id, UsageMetric.LLM_TOKENS_IN, 100.0),
                UsageFact(reader.id, UsageMetric.LLM_TOKENS_OUT, 40.0),
                UsageFact(reader.id, UsageMetric.LLM_COST_USD, 0.5),
                UsageFact(reader.id, UsageMetric.LLM_EXECUTIONS, 2.0),
            ],
        )
        await repo.replace_llm_day(
            yesterday,
            [LlmModelFact("gemini", "m1", 100, 40, 0.5, 2)],
            [LlmTaskFact("chat_tools", 100, 40, 0.5, 2)],
        )
        session.add(
            LlmExecution(
                user_id=reader.id,
                task="chat_tools",
                provider="gemini",
                model="m1",
                tokens_in=10,
                tokens_out=5,
                cost=0.1,
                latency_ms=1,
                status="ok",
            )
        )
        await session.commit()
        admin_id = admin.id
    await engine.dispose()
    return admin_id


@pytest.mark.integration
async def test_summary_and_by_user_combine_rolled_and_today(
    client: AsyncClient,
) -> None:
    admin_id = await _seed()
    token = create_access_token(user_id=admin_id, username="hyb-admin", settings=get_settings())
    client.cookies.set(COOKIE_NAME, token, domain=_HOST, path="/")
    now = datetime.now(UTC)
    frm = (now - timedelta(days=3)).strftime("%Y-%m-%dT00:00:00Z")
    to = (now + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")

    summary = (await client.get(f"/api/admin/usage/summary?from={frm}&to={to}")).json()
    assert summary["tokens_in"] == 110  # 100 rolled + 10 today
    assert summary["tokens_out"] == 45
    assert summary["total_cost"] == pytest.approx(0.6)
    m1 = next(m for m in summary["by_model"] if m["model"] == "m1")
    assert m1["tokens_in"] == 110

    by_user = (await client.get(f"/api/admin/usage/by-user?from={frm}&to={to}")).json()
    reader_row = next(r for r in by_user["items"] if r["username"] == "hyb-reader")
    assert reader_row["tokens_in"] == 110
    assert reader_row["execution_count"] == 3
