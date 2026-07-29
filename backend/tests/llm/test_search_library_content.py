"""Library content search (chapter FTS) tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.modules.books.schemas import BookCreate
from app.modules.chapters.schemas import ChapterCreate
from app.modules.chapters.service import ChapterService
from app.modules.library.service import LibraryService
from app.modules.tools.base import Mode, ToolContext
from app.modules.tools.definitions.search_library_content import (
    SearchLibraryContentInput,
    SearchLibraryContentTool,
)
from app.modules.users.schemas import UserCreate
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_library_content_matches_chapter_text(session: AsyncSession) -> None:
    user = await UserService(session).ensure_user(
        UserCreate(username=f"fts_{uuid4().hex[:8]}", password="test-pass-123", role="user")
    )
    library = LibraryService(session)
    book = await library.add_book(
        user.id,
        BookCreate(title="Untitled Novel", author="A", description="misc"),
    )
    await ChapterService(session).create(
        book.id,
        ChapterCreate(
            title="Chapter 1",
            content=(
                "In a modern city the boy discovered cultivation techniques "
                "and spirit qi flowing through skyscrapers."
            ),
            chapter_number=1,
        ),
        starting_chapter_number=1,
    )
    await session.commit()

    result = await library.search_content(user.id, "cultivation spirit qi")
    assert result.total >= 1
    assert any(hit.match_source == "chapter" for hit in result.hits)
    assert any("cultivation" in hit.snippet.lower() for hit in result.hits)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_library_content_tool_scopes_to_owner(session: AsyncSession) -> None:
    owner = await UserService(session).ensure_user(
        UserCreate(username=f"own_{uuid4().hex[:8]}", password="test-pass-123", role="user")
    )
    other = await UserService(session).ensure_user(
        UserCreate(username=f"oth_{uuid4().hex[:8]}", password="test-pass-123", role="user")
    )
    library = LibraryService(session)
    book = await library.add_book(
        owner.id,
        BookCreate(title="Secret", author="A", description=""),
    )
    await ChapterService(session).create(
        book.id,
        ChapterCreate(
            title="One",
            content="The hidden cultivation manual was buried under asphalt.",
            chapter_number=1,
        ),
        starting_chapter_number=1,
    )
    await session.commit()

    tool = SearchLibraryContentTool()
    ctx = ToolContext(
        user_id=other.id,
        conversation_id=uuid4(),
        run_id=uuid4(),
        mode=Mode.INTERNAL_ONLY,
        session=session,
    )
    out = await tool.execute(SearchLibraryContentInput(query="cultivation"), ctx)
    from app.modules.library.schemas import LibraryContentSearchResult

    assert isinstance(out, LibraryContentSearchResult)
    assert out.total == 0
