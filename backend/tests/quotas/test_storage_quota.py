"""storage_bytes standing quota: meter + enforcement (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.jobs.tasks import _total_bytes
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
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy import delete
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


@pytest.mark.unit
def test_total_bytes_counts_combined_and_parts() -> None:
    assert _total_bytes(b"12345", [b"12", b"345"]) == 10


async def _user_with_book(session: AsyncSession) -> tuple[UserRead, UUID]:
    user = await UserService(session).ensure_user(
        UserCreate(username=f"sto_{uuid4().hex[:8]}", password="test-pass-123")
    )
    book = await LibraryService(session).add_book(
        user.id, BookCreate(title="Storage Book", author="A", description="d")
    )
    await ChapterService(session).upsert_by_number(book.id, 1, "Ch 1", "text " * 50)
    await session.commit()
    return user, book.id


def _stored_job(
    user_id: UUID,
    book_id: UUID,
    *,
    size: int | None,
    expired: bool,
    deleted: bool = False,
) -> DownloadJob:
    delta = timedelta(hours=-1) if expired else timedelta(hours=1)
    return DownloadJob(
        user_id=user_id,
        book_id=book_id,
        chapter_from=1,
        chapter_to=1,
        provider="edge",
        voice="v",
        rate="1.0",
        status="complete",
        total_count=1,
        size_bytes=size,
        expires_at=datetime.now(UTC) + delta,
        deleted_at=datetime.now(UTC) if deleted else None,
    )


@pytest.mark.integration
async def test_stored_bytes_ignores_expired_null_and_deleted(
    session: AsyncSession,
) -> None:
    user, book_id = await _user_with_book(session)
    session.add_all(
        [
            _stored_job(user.id, book_id, size=1000, expired=False),
            _stored_job(user.id, book_id, size=9999, expired=True),
            _stored_job(user.id, book_id, size=None, expired=False),
            # Soft-deleted: assets were purged, so bytes no longer count
            # (unlike the audio meter, which keeps counting deleted jobs).
            _stored_job(user.id, book_id, size=7777, expired=False, deleted=True),
        ]
    )
    await session.commit()
    assert await DownloadRepository(session).stored_bytes(user.id) == 1000


@pytest.mark.integration
async def test_standing_cap_blocks_new_job(session: AsyncSession) -> None:
    user, book_id = await _user_with_book(session)
    session.add(_stored_job(user.id, book_id, size=5000, expired=False))
    session.add(
        MembershipQuota(
            membership=Membership.FREE.value,
            quota_kind=QuotaKind.STORAGE_BYTES.value,
            limit_value=5000.0,
        )
    )
    await session.commit()
    with pytest.raises(QuotaExceededError) as excinfo:
        await DownloadService(session).create(
            user.id, DownloadCreate(book_id=book_id, chapter_from=1, chapter_to=1)
        )
    assert excinfo.value.kind is QuotaKind.STORAGE_BYTES
    assert excinfo.value.resets_at is None  # standing: no monthly reset
