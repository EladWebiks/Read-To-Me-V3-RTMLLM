"""Admin usage endpoints expose hybrid rejection counts (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from app.core.config import get_settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.quotas.kinds import QuotaKind
from app.modules.usage.kinds import REJECTION_METRICS, UsageFact
from app.modules.usage.models import QuotaRejection, UsageDaily
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
        for model in (UsageDaily, QuotaRejection):
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


async def _seed() -> tuple[UUID, UUID]:
    """Admin + a reader with 2 rolled rejections (yesterday) + 1 raw (today).

    The rolled rejected_* row also puts the reader in the by-user listing
    (it is a usage_daily row), so no LLM execution seeding is needed.
    """
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        admin = User(
            username="rej-admin",
            email="rej-admin@example.com",
            password_hash=None,
            google_sub="rej-admin-sub",
            is_admin=True,
        )
        reader = User(
            username="rej-reader",
            email="rej-reader@example.com",
            password_hash=None,
            google_sub="rej-reader-sub",
            is_admin=False,
        )
        session.add_all([admin, reader])
        await session.flush()
        yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
        await UsageRepository(session).replace_day(
            yesterday,
            [UsageFact(reader.id, REJECTION_METRICS[QuotaKind.LLM_TOKENS], 2.0)],
        )
        session.add(QuotaRejection(user_id=reader.id, quota_kind="audio_chapters", source="api"))
        await session.commit()
        ids = (admin.id, reader.id)
    await engine.dispose()
    return ids


def _login(client: AsyncClient, user_id: UUID, username: str) -> None:
    token = create_access_token(user_id=user_id, username=username, settings=get_settings())
    client.cookies.set(COOKIE_NAME, token, domain=_HOST, path="/")


def _period() -> str:
    now = datetime.now(UTC)
    start = (now - timedelta(days=3)).strftime("%Y-%m-%dT00:00:00Z")
    end = (now + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
    return f"?from={start}&to={end}"


@pytest.mark.integration
async def test_summary_and_by_user_carry_hybrid_rejections(client: AsyncClient) -> None:
    admin_id, reader_id = await _seed()
    _login(client, admin_id, "rej-admin")

    summary = (await client.get("/api/admin/usage/summary" + _period())).json()
    assert summary["rejections"] == 3  # 2 rolled + 1 raw today
    assert summary["rejections_by_kind"]["llm_tokens"] == 2
    assert summary["rejections_by_kind"]["audio_chapters"] == 1

    by_user = (await client.get("/api/admin/usage/by-user" + _period())).json()
    reader_row = next(r for r in by_user["items"] if r["user_id"] == str(reader_id))
    assert reader_row["period_rejections"] == 3
