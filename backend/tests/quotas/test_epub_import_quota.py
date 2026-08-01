"""epub_imports quota + durable record lifecycle (needs Postgres)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.modules.imports.exceptions import InvalidEpubUploadError
from app.modules.imports.models import EpubImportRecord
from app.modules.imports.repository import EpubImportRepository
from app.modules.imports.service import ImportService
from app.modules.quotas.exceptions import QuotaExceededError
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
from app.modules.quotas.service import QuotaService
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.test_epub_parse import _minimal_epub


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(delete(MembershipQuota))
        await db.execute(delete(EpubImportRecord))
        await db.commit()
        yield db
        await db.rollback()
        await db.execute(delete(MembershipQuota))
        await db.execute(delete(EpubImportRecord))
        await db.commit()
    await engine.dispose()


async def _user(session: AsyncSession) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(username=f"epu_{uuid4().hex[:8]}", password="test-pass-123")
    )


async def _seed_completed(session: AsyncSession, user_id: UUID, count: int) -> None:
    repo = EpubImportRepository(session)
    for _ in range(count):
        record = await repo.add(user_id)
        await repo.set_terminal(record.id, status="completed", chapter_count=5)
    await session.commit()


@pytest.mark.integration
async def test_meter_counts_completed_only(session: AsyncSession) -> None:
    user = await _user(session)
    repo = EpubImportRepository(session)
    await _seed_completed(session, user.id, 2)
    failed = await repo.add(user.id)
    await repo.set_terminal(failed.id, status="failed", chapter_count=0)
    await session.commit()
    start, end = QuotaService.current_month_window(datetime.now(UTC))
    used = await repo.completed_in_period(user.id, period_start=start, period_end=end)
    assert used == 2


@pytest.mark.integration
async def test_over_cap_blocks_before_validation(session: AsyncSession) -> None:
    """Quota gate precedes validation: a .txt payload (which _validate_file
    would reject) still gets the QUOTA error — ordering is provable."""
    user = await _user(session)
    session.add(
        MembershipQuota(
            membership="free",
            quota_kind=QuotaKind.EPUB_IMPORTS.value,
            limit_value=2.0,
        )
    )
    await session.commit()
    await _seed_completed(session, user.id, 2)
    with pytest.raises(QuotaExceededError):
        await ImportService(session).start(
            user.id,
            [("junk.txt", b"not an epub")],
            title=None,
            author=None,
            starting_chapter=1,
        )


@pytest.mark.integration
async def test_successful_import_stamps_the_record_completed(
    session: AsyncSession,
) -> None:
    """The background runner is the meter's only writer: without this stamp the
    epub_imports quota could never accrue."""
    user = await _user(session)
    progress = await ImportService(session).start(
        user.id,
        [("book.epub", _minimal_epub())],
        title="Quota Lifecycle Book",
        author=None,
        starting_chapter=1,
    )
    assert progress.status == "running"
    for _ in range(100):  # the runner is an asyncio task on this same loop
        await asyncio.sleep(0.05)
        row = (
            await session.execute(
                select(EpubImportRecord).where(EpubImportRecord.user_id == user.id)
            )
        ).scalar_one()
        await session.refresh(row)
        if row.status != "running":
            break
    assert row.status == "completed"
    assert row.chapter_count == 1
    assert row.book_id is not None

    start, end = QuotaService.current_month_window(datetime.now(UTC))
    repo = EpubImportRepository(session)
    assert await repo.completed_in_period(user.id, period_start=start, period_end=end) == 1


@pytest.mark.integration
async def test_under_cap_reaches_validation(session: AsyncSession) -> None:
    """With quota headroom, the same .txt payload fails file validation instead
    (extension check in _validate_file)."""
    user = await _user(session)
    session.add(
        MembershipQuota(
            membership="free",
            quota_kind=QuotaKind.EPUB_IMPORTS.value,
            limit_value=10.0,
        )
    )
    await session.commit()
    with pytest.raises(InvalidEpubUploadError):
        await ImportService(session).start(
            user.id,
            [("junk.txt", b"not an epub")],
            title=None,
            author=None,
            starting_chapter=1,
        )
