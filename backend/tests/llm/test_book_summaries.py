"""Persisted summary cache, ownership, and invalidation tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.modules.books.schemas import BookCreate, BookRead
from app.modules.chapters.schemas import ChapterCreate, ChapterRead, ChapterUpdate
from app.modules.chapters.service import ChapterService
from app.modules.library.exceptions import BookAccessDeniedError
from app.modules.library.service import LibraryService
from app.modules.llm.service import LlmService
from app.modules.summaries.schemas import SummaryDraft, SummaryKind
from app.modules.summaries.service import SummaryService
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def _user(session: AsyncSession, prefix: str) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(
            username=f"{prefix}_{uuid4().hex[:8]}",
            password="test-pass-123",
            role="user",
        )
    )


async def _seed_book(session: AsyncSession, user: UserRead) -> tuple[BookRead, ChapterRead]:
    book = await LibraryService(session).add_book(
        user.id,
        BookCreate(title="Cache Book", author="Author", description="A test story."),
    )
    chapter = await ChapterService(session).create(
        book.id,
        ChapterCreate(
            title="Opening",
            content="The hero enters a strange city and meets an ally.",
            chapter_number=1,
        ),
        starting_chapter_number=1,
    )
    await session.commit()
    return book, chapter


@pytest.mark.integration
@pytest.mark.asyncio
async def test_summary_cache_and_chapter_hash_invalidation(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _user(session, "summary")
    book, chapter = await _seed_book(session, user)
    chapters = ChapterService(session)
    llm = LlmService(session, get_settings())
    generate = AsyncMock(
        return_value=(
            SummaryDraft(
                summary=(
                    "A hero enters a strange city and begins an uncertain journey "
                    "with a newly discovered ally."
                ),
                themes=["friendship"],
                setting="A strange city",
                tropes=["unlikely allies"],
                coverage_note="Opening chapter",
            ),
            "fake",
            "fake-summary-model",
        )
    )
    monkeypatch.setattr(llm, "generate_structured_with_model", generate)
    service = SummaryService(session, llm)

    first = await service.ensure(user.id, book.id, SummaryKind.NO_SPOILER)
    second = await service.ensure(user.id, book.id, SummaryKind.NO_SPOILER)
    assert (first.cached, second.cached) == (False, True)
    assert generate.await_count == 1

    await chapters.update(
        chapter.id,
        ChapterUpdate(content="The hero leaves the city after the alliance breaks."),
    )
    await session.commit()
    stale = await service.lookup(user.id, book.id, SummaryKind.NO_SPOILER)
    assert stale.found is True
    assert stale.stale is True
    assert stale.summary is None

    refreshed = await service.ensure(user.id, book.id, SummaryKind.NO_SPOILER)
    assert refreshed.cached is False
    assert generate.await_count == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_summary_lookup_enforces_ownership(session: AsyncSession) -> None:
    owner = await _user(session, "summary_owner")
    other = await _user(session, "summary_other")
    book = await LibraryService(session).add_book(
        owner.id,
        BookCreate(title="Private Summary", author="", description="Private."),
    )
    await session.commit()

    with pytest.raises(BookAccessDeniedError):
        await SummaryService(session).lookup(other.id, book.id, SummaryKind.NO_SPOILER)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_summary_soft_delete_for_book(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _user(session, "summary_delete")
    book, _chapter = await _seed_book(session, user)
    llm = LlmService(session, get_settings())
    generate = AsyncMock(
        return_value=(
            SummaryDraft(
                summary=(
                    "A hero enters a strange city and begins an uncertain journey "
                    "with a newly discovered ally."
                ),
                themes=["friendship"],
                setting="A strange city",
                tropes=["unlikely allies"],
                coverage_note="Opening chapter",
            ),
            "fake",
            "fake-summary-model",
        )
    )
    monkeypatch.setattr(llm, "generate_structured_with_model", generate)
    service = SummaryService(session, llm)
    await service.ensure(user.id, book.id, SummaryKind.NO_SPOILER)
    await service.soft_delete_for_book(user.id, book.id)
    remaining = await service.lookup(user.id, book.id, SummaryKind.NO_SPOILER)
    assert remaining.found is False
