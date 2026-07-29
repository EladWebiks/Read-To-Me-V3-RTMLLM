"""Chapter upsert must refresh server-side timestamps (async SQLAlchemy)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.modules.books.schemas import BookCreate
from app.modules.chapters.service import ChapterService
from app.modules.library.service import LibraryService
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
async def test_upsert_update_returns_chapter_read(session: AsyncSession) -> None:
    user = await UserService(session).ensure_user(
        UserCreate(username=f"ch_{uuid4().hex[:8]}", password="test-pass-123", role="user")
    )
    book = await LibraryService(session).add_book(
        user.id, BookCreate(title="Upsert Book", author="A", description="")
    )
    chapters = ChapterService(session)
    first = await chapters.upsert_by_number(book.id, 1, "Ch1", "body one")
    assert first.chapter_number == 1
    await session.commit()

    updated = await chapters.upsert_by_number(book.id, 1, "Ch1b", "body two")
    assert updated.title == "Ch1b"
    assert updated.content == "body two"
    assert updated.updated_at is not None
