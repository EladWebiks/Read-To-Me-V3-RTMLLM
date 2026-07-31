"""audio_chapters quota + soft-delete meter integrity (needs Postgres+Redis+MinIO)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.modules.books.schemas import BookCreate
from app.modules.chapters.service import ChapterService
from app.modules.downloads.models import DownloadJob
from app.modules.downloads.repository import DownloadRepository
from app.modules.downloads.schemas import DownloadCreate
from app.modules.downloads.service import DownloadService
from app.modules.library.service import LibraryService
from app.modules.quotas.exceptions import QuotaExceededError
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
from app.modules.quotas.service import QuotaService
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture(autouse=True)
def _no_enqueue(monkeypatch: pytest.MonkeyPatch) -> None:
    """The arq pool is a module-global bound to the first event loop, so a
    second real enqueue in this file would fail. Quotas gate before enqueue."""
    monkeypatch.setattr(DownloadService, "_enqueue", AsyncMock(return_value=None))


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


async def _user_with_book(session: AsyncSession) -> tuple[UserRead, UUID]:
    user = await UserService(session).ensure_user(
        UserCreate(username=f"aud_{uuid4().hex[:8]}", password="test-pass-123")
    )
    book = await LibraryService(session).add_book(
        user.id, BookCreate(title="Audio Quota Book", author="A", description="d")
    )
    chapters = ChapterService(session)
    for number in range(1, 4):
        await chapters.upsert_by_number(book.id, number, f"Ch {number}", "text " * 50)
    await session.commit()
    return user, book.id


async def _set_audio_quota(session: AsyncSession, limit: float) -> None:
    session.add(
        MembershipQuota(
            membership="free",
            quota_kind=QuotaKind.AUDIO_CHAPTERS.value,
            limit_value=limit,
        )
    )
    await session.commit()


async def _month_used(session: AsyncSession, user_id: UUID) -> int:
    start, end = QuotaService.current_month_window(datetime.now(UTC))
    return await DownloadRepository(session).chapters_in_period(
        user_id, period_start=start, period_end=end
    )


async def _seed_prior_job(
    session: AsyncSession, user_id: UUID, book_id: UUID, n: int, *, expired: bool = False
) -> None:
    """A this-month job covering n chapters (created_at defaults to now())."""
    delta = timedelta(hours=-1) if expired else timedelta(hours=1)
    session.add(
        DownloadJob(
            user_id=user_id,
            book_id=book_id,
            chapter_from=1,
            chapter_to=n,
            provider="edge",
            voice="v",
            rate="1.0",
            status="complete",
            total_count=n,
            expires_at=datetime.now(UTC) + delta,
        )
    )
    await session.commit()


@pytest.mark.integration
async def test_over_cap_blocks_new_audio_job(session: AsyncSession) -> None:
    user, book_id = await _user_with_book(session)
    await _set_audio_quota(session, 10)
    await _seed_prior_job(session, user.id, book_id, 10)  # 10 >= 10
    with pytest.raises(QuotaExceededError) as excinfo:
        await DownloadService(session).create(
            user.id, DownloadCreate(book_id=book_id, chapter_from=1, chapter_to=3)
        )
    assert excinfo.value.kind is QuotaKind.AUDIO_CHAPTERS
    assert "quota" in str(excinfo.value).lower()


@pytest.mark.integration
async def test_under_cap_creates_job(session: AsyncSession) -> None:
    user, book_id = await _user_with_book(session)
    await _set_audio_quota(session, 10)
    await _seed_prior_job(session, user.id, book_id, 5)  # 5 < 10
    job = await DownloadService(session).create(
        user.id, DownloadCreate(book_id=book_id, chapter_from=1, chapter_to=2)
    )
    assert job.status == "pending"


@pytest.mark.integration
async def test_admin_and_unlimited_are_not_metered(session: AsyncSession) -> None:
    # No quota row at all: create succeeds without a meter query.
    user, book_id = await _user_with_book(session)
    job = await DownloadService(session).create(
        user.id, DownloadCreate(book_id=book_id, chapter_from=1, chapter_to=1)
    )
    assert job.status == "pending"


@pytest.mark.integration
async def test_deleting_a_job_hides_it_but_keeps_the_quota_charge(
    session: AsyncSession,
) -> None:
    """Soft delete: the row leaves listings but the month's usage stands."""
    user, book_id = await _user_with_book(session)
    await _set_audio_quota(session, 3)
    service = DownloadService(session)
    job = await service.create(
        user.id, DownloadCreate(book_id=book_id, chapter_from=1, chapter_to=3)
    )
    await service.delete(user.id, job.id)

    listed = await DownloadRepository(session).list_for_user(
        user.id, book_id, limit=50, include_expired=True
    )
    assert job.id not in [row.id for row in listed]
    assert await _month_used(session, user.id) == 3  # charge survives
    with pytest.raises(QuotaExceededError):
        await service.create(
            user.id, DownloadCreate(book_id=book_id, chapter_from=1, chapter_to=1)
        )


@pytest.mark.integration
async def test_ttl_purge_does_not_reclaim_quota(session: AsyncSession) -> None:
    user, book_id = await _user_with_book(session)
    await _set_audio_quota(session, 4)
    await _seed_prior_job(session, user.id, book_id, 4, expired=True)
    await DownloadService(session).purge_all_expired()

    assert await _month_used(session, user.id) == 4
    with pytest.raises(QuotaExceededError):
        await DownloadService(session).create(
            user.id, DownloadCreate(book_id=book_id, chapter_from=1, chapter_to=1)
        )
