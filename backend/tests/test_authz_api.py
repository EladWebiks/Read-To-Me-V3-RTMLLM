"""Authorization matrix over a test-local app using the real deps/handlers."""

from collections.abc import AsyncIterator, Callable
from typing import Annotated

import pytest
from app.core.config import get_settings
from app.core.deps import get_db, require_admin, require_membership
from app.core.exceptions import register_exception_handlers
from app.core.security import create_access_token
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.dbcleanup import clear_users

# http.cookiejar drops cookies scoped to a single-label host, so the ASGI
# transport must answer on a dotted name (see test_auth_api.py).
_HOST = "test.local"


def _build_app() -> FastAPI:
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/admin-only")
    async def admin_only(
        user: Annotated[UserRead, Depends(require_admin)],
    ) -> dict[str, str]:
        return {"username": user.username}

    @test_app.get("/free-tier")
    async def free_tier(
        user: Annotated[UserRead, Depends(require_membership("free"))],
    ) -> dict[str, str]:
        return {"username": user.username}

    return test_app


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


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await clear_users(conn)
    test_app = _build_app()
    test_app.dependency_overrides[get_db] = _make_db_override(session_factory)
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url=f"http://{_HOST}") as http:
        yield http
    test_app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await clear_users(conn)
    await engine.dispose()


async def _login_as(client: AsyncClient, *, is_admin: bool) -> None:
    """Create a user directly and set their session cookie on the client."""
    settings = get_settings()
    engine = create_async_engine(settings.database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    username = "matrix-admin" if is_admin else "matrix-user"
    async with factory() as session:
        user = await UserService(session).create(
            UserCreate(username=username, password="password123", is_admin=is_admin)
        )
        await session.commit()
    await engine.dispose()
    token = create_access_token(user_id=user.id, username=user.username, settings=settings)
    client.cookies.set("rtm_token", token, domain=_HOST, path="/")


@pytest.mark.integration
async def test_admin_route_rejects_anonymous(client: AsyncClient) -> None:
    response = await client.get("/admin-only")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.integration
async def test_admin_route_rejects_non_admin(client: AsyncClient) -> None:
    await _login_as(client, is_admin=False)
    response = await client.get("/admin-only")
    assert response.status_code == 403
    assert response.json() == {"detail": "Not authorized"}


@pytest.mark.integration
async def test_admin_route_allows_admin(client: AsyncClient) -> None:
    await _login_as(client, is_admin=True)
    response = await client.get("/admin-only")
    assert response.status_code == 200
    assert response.json() == {"username": "matrix-admin"}


@pytest.mark.integration
async def test_membership_route_rejects_anonymous(client: AsyncClient) -> None:
    response = await client.get("/free-tier")
    assert response.status_code == 401


@pytest.mark.integration
async def test_membership_route_allows_free_user_at_free_minimum(
    client: AsyncClient,
) -> None:
    await _login_as(client, is_admin=False)
    response = await client.get("/free-tier")
    assert response.status_code == 200
    assert response.json() == {"username": "matrix-user"}


@pytest.mark.integration
async def test_membership_route_rejects_insufficient_tier(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.deps.meets_minimum", lambda actual, minimum: False)
    await _login_as(client, is_admin=False)
    response = await client.get("/free-tier")
    assert response.status_code == 403
    assert response.json() == {"detail": "Not authorized"}
