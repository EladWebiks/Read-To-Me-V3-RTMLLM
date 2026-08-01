"""By-user month columns count rolled closed days with no raw rows (needs Postgres).

Equivalence proof (spec §7.7): raw-only seeding keeps today's values identical;
rolled-only seeding (no raw rows for the closed day) MUST now appear too —
the raw-scan implementation would return 0 for it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from uuid import UUID

import pytest
from app.core.config import get_settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.llm.models import LlmExecution
from app.modules.quotas.service import QuotaService
from app.modules.usage.kinds import UsageFact, UsageMetric
from app.modules.usage.models import UsageDaily
from app.modules.usage.repository import UsageRepository
from app.modules.users.models import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.dbcleanup import clear_users

_HOST = "test.local"
BASE = "/api/admin/usage/by-user"


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
        for model in (UsageDaily, LlmExecution):
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
    """Admin + reader: rolled tokens on the month's first day + raw tokens today."""
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        admin = User(
            username="mc-admin",
            email="mc-admin@example.com",
            password_hash=None,
            google_sub="mc-admin-sub",
            is_admin=True,
        )
        reader = User(
            username="mc-reader",
            email="mc-reader@example.com",
            password_hash=None,
            google_sub="mc-reader-sub",
            is_admin=False,
        )
        session.add_all([admin, reader])
        await session.flush()
        now = datetime.now(UTC)
        month_start, _ = QuotaService.current_month_window(now)
        if month_start.date() != now.date():
            await UsageRepository(session).replace_day(
                month_start.date(),
                [
                    UsageFact(reader.id, UsageMetric.LLM_TOKENS_IN, 300.0),
                    UsageFact(reader.id, UsageMetric.AUDIO_CHAPTERS, 7.0),
                ],
            )
        session.add(
            LlmExecution(
                user_id=reader.id,
                task="chat_tools",
                provider="gemini",
                model="m",
                tokens_in=100,
                tokens_out=0,
                cost=0.5,
                latency_ms=10,
                status="ok",
            )
        )
        await session.commit()
        admin_id = admin.id
    await engine.dispose()
    return admin_id


@pytest.mark.integration
async def test_month_columns_are_hybrid(client: AsyncClient) -> None:
    admin_id = await _seed()
    token = create_access_token(user_id=admin_id, username="mc-admin", settings=get_settings())
    client.cookies.set(COOKIE_NAME, token, domain=_HOST, path="/")

    now = datetime.now(UTC)
    on_day_one = QuotaService.current_month_window(now)[0].date() == now.date()
    query = f"?from={now.year}-01-01T00:00:00Z&to={now.year + 1}-01-01T00:00:00Z"
    rows = (await client.get(BASE + query)).json()["items"]
    reader_row = next(r for r in rows if r["username"] == "mc-reader")
    assert reader_row["month_tokens"] == (100 if on_day_one else 400)  # rolled 300 + today 100
    assert reader_row["month_audio_chapters"] == (0 if on_day_one else 7)  # rolled-only
    assert reader_row["month_cost"] == pytest.approx(0.5)  # today-tail only
