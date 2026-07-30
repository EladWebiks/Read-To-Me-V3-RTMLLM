"""Reading progress API integration tests."""

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


async def _clear(engine: AsyncEngine) -> None:
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


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Authenticated client with one book + chapter."""
    settings = get_settings()
    engine = create_async_engine(settings.database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await _clear(engine)
    app.dependency_overrides[get_db] = _make_db_override(factory)
    async with factory() as session:
        user = await UserService(session).ensure_user(
            UserCreate(
                username=settings.auth.admin_username,
                password=settings.auth.admin_password,
                role="admin",
            )
        )
        await session.commit()
    token = create_access_token(user_id=user.id, username=user.username, settings=settings)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        http.cookies.set("rtm_token", token)
        yield http

    app.dependency_overrides.clear()
    await _clear(engine)
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_progress_upsert_and_get(client: AsyncClient) -> None:
    """Saving progress then reading it back works."""
    book = (
        await client.post(
            "/api/library/books",
            json={"title": "Progress Book"},
        )
    ).json()
    chapter = (
        await client.post(
            f"/api/library/books/{book['id']}/chapters",
            json={"title": "One", "content": "Alpha beta gamma"},
        )
    ).json()

    missing = await client.get(f"/api/library/books/{book['id']}/progress")
    assert missing.status_code == 404

    saved = await client.put(
        f"/api/library/books/{book['id']}/progress",
        json={
            "chapter_id": chapter["id"],
            "chapter_number": chapter["chapter_number"],
            "paragraph_index": 0,
            "word_index": 2,
        },
    )
    assert saved.status_code == 200
    assert saved.json()["word_index"] == 2

    again = await client.get(f"/api/library/books/{book['id']}/progress")
    assert again.status_code == 200
    assert again.json()["chapter_id"] == chapter["id"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_continue_clears_after_book_delete(client: AsyncClient) -> None:
    """Deleting a book must not leave continue-reading on a dead chapter."""
    book = (
        await client.post(
            "/api/library/books",
            json={"title": "Gone Book"},
        )
    ).json()
    chapter = (
        await client.post(
            f"/api/library/books/{book['id']}/chapters",
            json={"title": "One", "content": "Soon deleted"},
        )
    ).json()
    saved = await client.put(
        f"/api/library/books/{book['id']}/progress",
        json={
            "chapter_id": chapter["id"],
            "chapter_number": chapter["chapter_number"],
            "paragraph_index": 0,
            "word_index": 0,
        },
    )
    assert saved.status_code == 200

    cont = await client.get("/api/library/reading/continue")
    assert cont.status_code == 200
    assert cont.json()["book_id"] == book["id"]

    deleted = await client.delete(f"/api/library/books/{book['id']}")
    assert deleted.status_code == 204

    after = await client.get("/api/library/reading/continue")
    assert after.status_code == 200
    assert after.json() is None

    chapter_get = await client.get(f"/api/chapters/{chapter['id']}")
    assert chapter_get.status_code == 404
