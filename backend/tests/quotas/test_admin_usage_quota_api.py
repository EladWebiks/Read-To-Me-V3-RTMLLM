"""By-user usage rows carry membership + month usage + LLM quota (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.books.schemas import BookCreate
from app.modules.downloads.models import DownloadJob
from app.modules.imports.models import EpubImportRecord
from app.modules.imports.repository import EpubImportRepository
from app.modules.library.service import LibraryService
from app.modules.llm.models import LlmExecution
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
from app.modules.scraping.models import ScrapingJob, ScrapingSource
from app.modules.users.membership import Membership
from app.modules.users.models import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
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
        await session.execute(delete(LlmExecution))
        await session.execute(delete(MembershipQuota))
        await session.execute(delete(EpubImportRecord))
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
    """Admin + a reader with usage this month + a free-tier token quota rule."""
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        admin = User(
            username="usage-admin",
            email="usage-admin@example.com",
            password_hash=None,
            google_sub="usage-admin-sub",
            is_admin=True,
        )
        reader = User(
            username="usage-reader",
            email="usage-reader@example.com",
            password_hash=None,
            google_sub="usage-reader-sub",
            is_admin=False,
        )
        session.add_all([admin, reader])
        await session.flush()
        session.add(
            LlmExecution(
                user_id=reader.id,
                task="chat_tools",
                provider="gemini",
                model="m",
                tokens_in=600,
                tokens_out=400,
                cost=0.25,
                latency_ms=10,
                status="ok",
            )
        )
        session.add(
            MembershipQuota(
                membership=Membership.FREE.value,
                quota_kind=QuotaKind.LLM_TOKENS.value,
                limit_value=5000.0,
            )
        )
        await _seed_job_usage(session, reader.id)
        await session.commit()
        admin_id = admin.id
    await engine.dispose()
    return admin_id


async def _seed_job_usage(session: AsyncSession, user_id: UUID) -> None:
    """One of each non-LLM dimension this month, for the "Jobs (month)" column."""
    book = await LibraryService(session).add_book(
        user_id, BookCreate(title="Usage Book", author="A", description="d")
    )
    source = (await session.execute(select(ScrapingSource).limit(1))).scalar_one_or_none()
    if source is None:
        source = ScrapingSource(name=f"src_{uuid4().hex[:8]}", base_domains=["example.com"])
        session.add(source)
        await session.flush()
    record = await EpubImportRepository(session).add(user_id)
    await EpubImportRepository(session).set_terminal(
        record.id, status="completed", chapter_count=7
    )
    session.add_all(
        [
            DownloadJob(
                user_id=user_id,
                book_id=book.id,
                chapter_from=1,
                chapter_to=3,
                provider="edge",
                voice="v",
                rate="1.0",
                status="complete",
                total_count=3,
            ),
            ScrapingJob(
                user_id=user_id,
                source_id=source.id,
                start_url="https://novelfull.net/book/x.html",
                mode="range",
                status="complete",
                chapters_done=40,
            ),
        ]
    )
    await session.flush()


@pytest.mark.integration
async def test_by_user_rows_include_membership_month_and_quota(
    client: AsyncClient,
) -> None:
    admin_id = await _seed()
    token = create_access_token(user_id=admin_id, username="usage-admin", settings=get_settings())
    client.cookies.set(COOKIE_NAME, token, domain=_HOST, path="/")

    now = datetime.now(UTC)
    query = f"?from={now.year}-01-01T00:00:00Z&to={now.year + 1}-01-01T00:00:00Z"
    response = await client.get(BASE + query)
    assert response.status_code == 200
    rows = response.json()["items"]
    reader_row = next(r for r in rows if r["username"] == "usage-reader")
    assert reader_row["membership"] == "free"
    assert reader_row["month_tokens"] == 1000
    assert reader_row["month_cost"] == pytest.approx(0.25)
    assert reader_row["llm_tokens_limit"] == 5000.0
    assert reader_row["llm_cost_limit"] is None  # no rule = unlimited
    assert reader_row["month_audio_chapters"] == 3
    assert reader_row["month_scrape_chapters"] == 40
    assert reader_row["month_epub_imports"] == 1
