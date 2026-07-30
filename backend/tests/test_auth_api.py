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
    engine = create_async_engine(settings.database.url, poolclass=NullPool)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    await _clear_users(engine)
    app.dependency_overrides[get_db] = _make_db_override(session_factory)
    await _seed_admin(session_factory)

    transport = ASGITransport(app=app)
    # base_url uses a dotted host ("test.local", not "test"): Python's
    # http.cookiejar special-cases single-label hostnames when matching a
    # cookie's Domain attribute, which breaks domain-scoped cookie handling
    # below (see test_me_and_logout_with_minted_token).
    async with AsyncClient(transport=transport, base_url="http://test.local") as http:
        yield http

    app.dependency_overrides.clear()
    await _clear_users(engine)
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_me_and_logout_with_minted_token(client: AsyncClient) -> None:
    """A directly-minted session token works for /me; logout clears it."""
    from app.core.security import create_access_token
    from app.modules.users.service import UserService

    settings = get_settings()
    engine = create_async_engine(settings.database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        user = await UserService(session).get_entity_by_username(settings.admin_username)
        assert user is not None
        token = create_access_token(user_id=user.id, username=user.username, settings=settings)
    await engine.dispose()

    # domain="test.local" must match the ASGITransport host (base_url set in
    # the `client` fixture above). Without an explicit, matching domain,
    # httpx's cookiejar stores this manually-injected cookie as a
    # domain-less entry that the logout response's host-scoped Set-Cookie
    # cannot expire, so the client would keep sending the "deleted" cookie
    # and /me would wrongly still return 200 after logout — a cookie-jar
    # artifact, not real proof that logout invalidates the session.
    client.cookies.set("rtm_token", token, domain="test.local", path="/")
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == settings.admin_username

    logout = await client.post("/api/auth/logout")
    assert logout.status_code == 204

    me_after = await client.get("/api/auth/me")
    assert me_after.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_password_login_is_gone(client: AsyncClient) -> None:
    """The old password endpoint no longer exists."""
    settings = get_settings()
    response = await client.post(
        "/api/auth/login",
        json={
            "username": settings.admin_username,
            "password": settings.admin_password,
        },
    )
    assert response.status_code == 404
