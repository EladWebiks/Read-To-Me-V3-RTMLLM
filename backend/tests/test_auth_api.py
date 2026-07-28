"""Auth API integration tests (requires Postgres)."""

from collections.abc import AsyncIterator, Callable

import pytest
from app.core.config import get_settings
from app.core.deps import get_db
from app.main import app
from app.modules.users.models import User  # noqa: F401
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


async def _clear_users(engine: AsyncEngine) -> None:
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
                username=settings.admin_username,
                password=settings.admin_password,
                role="admin",
            )
        )
        await session.commit()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """ASGI client against the migrated database (clears users per test)."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    await _clear_users(engine)
    app.dependency_overrides[get_db] = _make_db_override(session_factory)
    await _seed_admin(session_factory)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http

    app.dependency_overrides.clear()
    await _clear_users(engine)
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_me_logout_flow(client: AsyncClient) -> None:
    """Login sets cookie; /me works; logout clears session."""
    settings = get_settings()
    login = await client.post(
        "/api/auth/login",
        json={
            "username": settings.admin_username,
            "password": settings.admin_password,
        },
    )
    assert login.status_code == 200
    assert login.json()["user"]["username"] == settings.admin_username
    assert "rtm_token" in login.cookies

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == settings.admin_username

    logout = await client.post("/api/auth/logout")
    assert logout.status_code == 204

    me_after = await client.get("/api/auth/me")
    assert me_after.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_rejects_bad_password(client: AsyncClient) -> None:
    """Wrong password returns 401."""
    settings = get_settings()
    response = await client.post(
        "/api/auth/login",
        json={"username": settings.admin_username, "password": "not-the-password"},
    )
    assert response.status_code == 401
