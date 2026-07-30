"""Library + chapters API integration tests."""

from collections.abc import AsyncIterator, Callable

import pytest
from app.core.config import get_settings
from app.core.deps import get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.users.schemas import UserCreate
from app.modules.users.service import UserService
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


def _make_db_override(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[], AsyncIterator[AsyncSession]]:
    async def _override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return _override_db


async def _clear_library(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM scraping_job_items"))
        await conn.execute(text("DELETE FROM scraping_jobs"))
        await conn.execute(text("DELETE FROM download_jobs"))
        await conn.execute(text("DELETE FROM reading_progress"))
        await conn.execute(text("DELETE FROM chapters"))
        await conn.execute(text("DELETE FROM user_books"))
        await conn.execute(text("DELETE FROM books"))
        await conn.execute(text("DELETE FROM cost_records"))
        await conn.execute(text("DELETE FROM llm_executions"))
        await conn.execute(text("DELETE FROM tool_calls"))
        await conn.execute(text("DELETE FROM conversation_messages"))
        await conn.execute(text("DELETE FROM conversations"))
        await conn.execute(text("DELETE FROM users"))


async def _seed_admin(session_factory: async_sessionmaker[AsyncSession]) -> None:
    settings = get_settings()
    async with session_factory() as session:
        await UserService(session).ensure_user(
            UserCreate(
                username=settings.auth.admin_username,
                password=settings.auth.admin_password,
                role="admin",
            )
        )
        await session.commit()


async def _mint_token(
    session_factory: async_sessionmaker[AsyncSession],
) -> str:
    """Mint a session token directly, bypassing the (removed) password endpoint."""
    settings = get_settings()
    async with session_factory() as session:
        user = await UserService(session).get_entity_by_username(settings.auth.admin_username)
        assert user is not None
        return create_access_token(user_id=user.id, username=user.username, settings=settings)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Authenticated ASGI client with a clean library."""
    settings = get_settings()
    engine = create_async_engine(settings.database.url, poolclass=NullPool)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    await _clear_library(engine)
    app.dependency_overrides[get_db] = _make_db_override(session_factory)
    await _seed_admin(session_factory)
    token = await _mint_token(session_factory)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        http.cookies.set("rtm_token", token)
        yield http

    app.dependency_overrides.clear()
    await _clear_library(engine)
    await engine.dispose()


async def _create_book(client: AsyncClient) -> str:
    created = await client.post(
        "/api/library/books",
        json={"title": "Test Novel", "author": "A. Author"},
    )
    assert created.status_code == 201
    book = created.json()
    assert book["chapter_count"] == 0
    return str(book["id"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_library_book_and_chapter_flow(client: AsyncClient) -> None:
    """Create book, add chapter, list, delete."""
    book_id = await _create_book(client)
    chapter = await client.post(
        f"/api/library/books/{book_id}/chapters",
        json={"title": "Chapter 1", "content": "Once upon a time"},
    )
    assert chapter.status_code == 201
    assert chapter.json()["chapter_number"] == 1

    listed = await client.get("/api/library/books")
    assert listed.status_code == 200
    assert listed.json()[0]["chapter_count"] == 1

    deleted = await client.delete(f"/api/library/books/{book_id}")
    assert deleted.status_code == 204
    assert (await client.get("/api/library/books")).json() == []
