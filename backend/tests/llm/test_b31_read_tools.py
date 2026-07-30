"""B3.1 read-only tool integration tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.modules.books.schemas import BookCreate
from app.modules.chapters.schemas import ChapterCreate
from app.modules.chapters.service import ChapterService
from app.modules.library.service import LibraryService
from app.modules.reader.schemas import ProgressUpsert
from app.modules.reader.service import ReaderService
from app.modules.tools.base import Mode, ToolContext
from app.modules.tools.definitions.get_chapter_content import (
    GetChapterContentInput,
    GetChapterContentOutput,
    GetChapterContentTool,
)
from app.modules.tools.definitions.get_reading_progress import (
    GetReadingProgressInput,
    GetReadingProgressOutput,
    GetReadingProgressTool,
)
from app.modules.tools.definitions.get_recently_read_chapters import (
    GetRecentlyReadChaptersTool,
    GetRecentlyReadInput,
    GetRecentlyReadOutput,
)
from app.modules.tools.definitions.list_available_chapters import (
    ListAvailableChaptersInput,
    ListAvailableChaptersOutput,
    ListAvailableChaptersTool,
)
from app.modules.tools.exceptions import ToolAuthzError
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    settings = get_settings()
    engine = create_async_engine(settings.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def _user(session: AsyncSession) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(username=f"b31_{uuid4().hex[:8]}", password="test-pass-123", role="user")
    )


def _ctx(session: AsyncSession, user_id: UUID) -> ToolContext:
    return ToolContext(
        user_id=user_id,
        conversation_id=uuid4(),
        run_id=uuid4(),
        mode=Mode.INTERNAL_ONLY,
        session=session,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_and_get_chapter_content(session: AsyncSession) -> None:
    user = await _user(session)
    library = LibraryService(session)
    book = await library.add_book(
        user.id,
        BookCreate(title="B31 Book", author="A", description="d"),
    )
    chapter = await ChapterService(session).create(
        book.id,
        ChapterCreate(title="Ch1", content="Once upon a cultivation path.", chapter_number=1),
        starting_chapter_number=1,
    )
    await session.commit()
    ctx = _ctx(session, user.id)

    listed = await ListAvailableChaptersTool().execute(
        ListAvailableChaptersInput(book_id=book.id),
        ctx,
    )
    assert isinstance(listed, ListAvailableChaptersOutput)
    assert listed.total == 1

    got = await GetChapterContentTool().execute(
        GetChapterContentInput(book_id=book.id, chapter_number=1),
        ctx,
    )
    assert isinstance(got, GetChapterContentOutput)
    assert got.chapter_id == chapter.id
    assert "cultivation" in got.content
    assert got.truncated is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chapter_content_denied_for_other_user(session: AsyncSession) -> None:
    owner = await _user(session)
    other = await _user(session)
    library = LibraryService(session)
    book = await library.add_book(
        owner.id,
        BookCreate(title="Private", author="A", description=""),
    )
    await ChapterService(session).create(
        book.id,
        ChapterCreate(title="Ch1", content="secret text here", chapter_number=1),
        starting_chapter_number=1,
    )
    await session.commit()

    tool = GetChapterContentTool()
    ctx = _ctx(session, other.id)
    with pytest.raises(ToolAuthzError):
        await tool.authorize(
            GetChapterContentInput(book_id=book.id, chapter_number=1),
            ctx,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reading_progress_and_recent(session: AsyncSession) -> None:
    user = await _user(session)
    library = LibraryService(session)
    book = await library.add_book(
        user.id,
        BookCreate(title="Progress Book", author="A", description=""),
    )
    chapter = await ChapterService(session).create(
        book.id,
        ChapterCreate(title="Ch1", content="hello world chapter", chapter_number=1),
        starting_chapter_number=1,
    )
    await ReaderService(session).upsert_progress(
        user.id,
        book.id,
        ProgressUpsert(chapter_id=chapter.id, chapter_number=1),
    )
    await session.commit()
    ctx = _ctx(session, user.id)

    progress = await GetReadingProgressTool().execute(
        GetReadingProgressInput(book_id=book.id),
        ctx,
    )
    assert isinstance(progress, GetReadingProgressOutput)
    assert progress.found is True
    assert progress.chapter_number == 1

    recent = await GetRecentlyReadChaptersTool().execute(
        GetRecentlyReadInput(limit=5),
        ctx,
    )
    assert isinstance(recent, GetRecentlyReadOutput)
    assert recent.total >= 1
    assert recent.items[0].book_id == book.id
