"""import_discovered_book requires HITL confirmation."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.core.normalize import normalize_title
from app.modules.discovery.models import BookSource, DiscoveredBook
from app.modules.discovery.repository import DiscoveryRepository
from app.modules.llm.repository import LlmRepository
from app.modules.llm.types import ToolCall
from app.modules.tools.base import Mode, ToolContext
from app.modules.tools.definitions.import_discovered_book import ImportDiscoveredBookTool
from app.modules.tools.executor import execute_tool_call
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
        UserCreate(
            username=f"imp_{uuid4().hex[:8]}",
            password="test-pass-123",
            role="user",
        )
    )


async def _seed_discovered(session: AsyncSession) -> DiscoveredBook:
    repo = DiscoveryRepository(session)
    title = f"Import Seed {uuid4().hex[:6]}"
    book = await repo.add_book(
        DiscoveredBook(
            title=title,
            normalized_title=normalize_title(title),
            author="Tester",
        )
    )
    slug = uuid4().hex[:8]
    await repo.add_source(
        BookSource(
            discovered_book_id=book.id,
            source="novelfull",
            book_url=f"https://novelfull.net/book/seed-{slug}.html",
            first_chapter_url="",
            chapter_count_estimate=100,
        )
    )
    await session.commit()
    return book


@pytest.mark.unit
@pytest.mark.asyncio
async def test_import_discovered_never_runs_without_confirm(
    session: AsyncSession,
) -> None:
    user = await _user(session)
    book = await _seed_discovered(session)
    ctx = ToolContext(
        user_id=user.id,
        conversation_id=uuid4(),
        run_id=uuid4(),
        mode=Mode.EXTERNAL_ALLOWED,
        session=session,
    )
    result = await execute_tool_call(
        ImportDiscoveredBookTool(),
        ToolCall(
            id="x",
            name="import_discovered_book",
            arguments={"discovered_book_id": str(book.id)},
        ),
        ctx,
        LlmRepository(session),
    )
    assert result["ok"] is False
    err = str(result["error"]).lower()
    assert "confirmation" in err or "import_discovered_book" in err
