"""scrape_chapters quota at job creation (needs Postgres; no network)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.modules.quotas.exceptions import QuotaExceededError
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
from app.modules.quotas.service import QuotaService
from app.modules.scraping.models import ScrapingJob, ScrapingSource
from app.modules.scraping.repository import ScrapingRepository
from app.modules.scraping.schemas import ScrapeJobCreate
from app.modules.scraping.service import ScrapingService
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy import delete, select
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


async def _user(session: AsyncSession) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(username=f"scr_{uuid4().hex[:8]}", password="test-pass-123")
    )


async def _any_source_id(session: AsyncSession) -> UUID:
    """Sources are seeded at startup; reuse one (or create a throwaway)."""
    row = (await session.execute(select(ScrapingSource).limit(1))).scalar_one_or_none()
    if row is None:
        row = ScrapingSource(name=f"src_{uuid4().hex[:8]}", base_domains=["example.com"])
        session.add(row)
        await session.commit()
    return row.id


async def _seed_scraped(session: AsyncSession, user_id: UUID, chapters: int) -> None:
    session.add(
        ScrapingJob(
            user_id=user_id,
            source_id=await _any_source_id(session),
            start_url="https://novelfull.net/book/x.html",
            mode="range",
            status="complete",
            chapters_done=chapters,
        )
    )
    await session.commit()


async def _set_scrape_quota(session: AsyncSession, limit: float) -> None:
    session.add(
        MembershipQuota(
            membership=Membership.FREE.value,
            quota_kind=QuotaKind.SCRAPE_CHAPTERS.value,
            limit_value=limit,
        )
    )
    await session.commit()


@pytest.mark.integration
async def test_meter_sums_month_chapters(session: AsyncSession) -> None:
    user = await _user(session)
    await _seed_scraped(session, user.id, 120)
    await _seed_scraped(session, user.id, 30)
    start, end = QuotaService.current_month_window(datetime.now(UTC))
    used = await ScrapingRepository(session).chapters_in_period(
        user.id, period_start=start, period_end=end
    )
    assert used == 150


@pytest.mark.integration
async def test_over_cap_blocks_before_any_network(session: AsyncSession) -> None:
    """Enforcement precedes adapter/network work: no mock needed, no fetch made."""
    user = await _user(session)
    await _set_scrape_quota(session, 100)
    await _seed_scraped(session, user.id, 100)
    with pytest.raises(QuotaExceededError) as excinfo:
        await ScrapingService(session).create_job(
            user.id, ScrapeJobCreate(url="https://novelfull.net/book/x.html")
        )
    assert excinfo.value.kind is QuotaKind.SCRAPE_CHAPTERS
