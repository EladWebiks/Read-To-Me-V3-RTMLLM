"""B3.2 low-risk action tool integration tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.modules.books.schemas import BookCreate
from app.modules.chapters.schemas import ChapterCreate
from app.modules.chapters.service import ChapterService
from app.modules.downloads.service import DownloadService
from app.modules.library.service import LibraryService
from app.modules.reader.schemas import ProgressUpsert
from app.modules.reader.service import ReaderService
from app.modules.tools.base import Mode, ToolContext
from app.modules.tools.definitions.chapter_ref import ChapterRefInput
from app.modules.tools.definitions.create_chapter_download import (
    CreateChapterDownloadOutput,
    CreateChapterDownloadTool,
)
from app.modules.tools.definitions.play_chapter import (
    PlayChapterOutput,
    PlayChapterTool,
)
from app.modules.tools.definitions.resume_book import (
    ResumeBookInput,
    ResumeBookOutput,
    ResumeBookTool,
)
from app.modules.tools.exceptions import ToolAuthzError
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def _user(session: AsyncSession) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(username=f"b32_{uuid4().hex[:8]}", password="test-pass-123", role="user")
    )


def _ctx(session: AsyncSession, user_id: UUID) -> ToolContext:
    return ToolContext(
        user_id=user_id,
        conversation_id=uuid4(),
        run_id=uuid4(),
        mode=Mode.INTERNAL_ONLY,
        session=session,
    )


async def _book_with_chapter(session: AsyncSession, user_id: UUID) -> tuple[UUID, UUID]:
    library = LibraryService(session)
    book = await library.add_book(
        user_id,
        BookCreate(title="B32 Book", author="A", description=""),
    )
    chapter = await ChapterService(session).create(
        book.id,
        ChapterCreate(title="Ch1", content="hello play chapter", chapter_number=1),
        starting_chapter_number=1,
    )
    await session.commit()
    return book.id, chapter.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_play_chapter_updates_progress(session: AsyncSession) -> None:
    user = await _user(session)
    book_id, chapter_id = await _book_with_chapter(session, user.id)
    ctx = _ctx(session, user.id)

    out = await PlayChapterTool().execute(
        ChapterRefInput(book_id=book_id, chapter_number=1),
        ctx,
    )
    assert isinstance(out, PlayChapterOutput)
    assert out.chapter_id == chapter_id
    assert out.progress_updated is True

    progress = await ReaderService(session).get_progress(user.id, book_id)
    assert progress.chapter_id == chapter_id
    assert progress.chapter_number == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_play_chapter_denied_for_other_user(session: AsyncSession) -> None:
    owner = await _user(session)
    other = await _user(session)
    book_id, _ = await _book_with_chapter(session, owner.id)
    ctx = _ctx(session, other.id)

    with pytest.raises(ToolAuthzError):
        await PlayChapterTool().authorize(
            ChapterRefInput(book_id=book_id, chapter_number=1),
            ctx,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resume_book_latest(session: AsyncSession) -> None:
    user = await _user(session)
    book_id, chapter_id = await _book_with_chapter(session, user.id)
    await ReaderService(session).upsert_progress(
        user.id,
        book_id,
        ProgressUpsert(chapter_id=chapter_id, chapter_number=1),
    )
    await session.commit()
    ctx = _ctx(session, user.id)

    out = await ResumeBookTool().execute(ResumeBookInput(), ctx)
    assert isinstance(out, ResumeBookOutput)
    assert out.found is True
    assert out.book_id == book_id
    assert out.chapter_number == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_chapter_download_idempotent(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        DownloadService,
        "_enqueue",
        AsyncMock(return_value=None),
    )
    user = await _user(session)
    book_id, _ = await _book_with_chapter(session, user.id)
    ctx = _ctx(session, user.id)
    tool = CreateChapterDownloadTool()

    first = await tool.execute(
        ChapterRefInput(book_id=book_id, chapter_number=1),
        ctx,
    )
    assert isinstance(first, CreateChapterDownloadOutput)
    assert first.reused is False
    assert first.status == "pending"

    second = await tool.execute(
        ChapterRefInput(book_id=book_id, chapter_number=1),
        ctx,
    )
    assert isinstance(second, CreateChapterDownloadOutput)
    assert second.reused is True
    assert second.job_id == first.job_id
