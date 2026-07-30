"""Admin settings API: authz matrix, typed errors, set/clear flows (needs Postgres)."""

from collections.abc import AsyncIterator, Callable
from uuid import UUID

import pytest
from app.core.config import get_settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.runtime_config import cache
from app.modules.users.models import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.dbcleanup import clear_users

# http.cookiejar drops cookies scoped to a single-label host, so the ASGI
# transport must answer on a dotted name (see test_auth_api.py).
_HOST = "test.local"


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


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    cache.invalidate()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await clear_users(conn)
    app.dependency_overrides[get_db] = _make_db_override(session_factory)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=f"http://{_HOST}") as http:
        yield http
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await clear_users(conn)
    await engine.dispose()


async def _create_user(username: str, *, is_admin: bool) -> UUID:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=None,
            google_sub=f"{username}-sub",
            is_admin=is_admin,
        )
        session.add(user)
        await session.commit()
        user_id = user.id
    await engine.dispose()
    return user_id


def _login(client: AsyncClient, user_id: UUID, username: str) -> None:
    token = create_access_token(user_id=user_id, username=username, settings=get_settings())
    client.cookies.set(COOKIE_NAME, token, domain=_HOST, path="/")


@pytest.fixture
async def admin_client(client: AsyncClient) -> AsyncClient:
    user_id = await _create_user("cfg-admin", is_admin=True)
    _login(client, user_id, "cfg-admin")
    return client


@pytest.mark.integration
async def test_anonymous_gets_401(client: AsyncClient) -> None:
    assert (await client.get("/api/admin/settings")).status_code == 401


@pytest.mark.integration
async def test_non_admin_gets_403(client: AsyncClient) -> None:
    user_id = await _create_user("cfg-reader", is_admin=False)
    _login(client, user_id, "cfg-reader")
    assert (await client.get("/api/admin/settings")).status_code == 403
    put = await client.put("/api/admin/settings/llm_runtime.max_tool_iters", json={"value": 2})
    assert put.status_code == 403


@pytest.mark.integration
async def test_set_get_clear_flow(admin_client: AsyncClient) -> None:
    put = await admin_client.put(
        "/api/admin/settings/llm_runtime.max_tool_iters", json={"value": 2}
    )
    assert put.status_code == 200
    assert put.json()["value"] == 2

    listing = await admin_client.get("/api/admin/settings")
    assert listing.status_code == 200
    entries = {e["key"]: e for e in listing.json()["settings"]}
    assert entries["llm_runtime.max_tool_iters"]["overridden"] is True
    assert entries["llm_runtime.max_tool_iters"]["effective_value"] == 2
    assert entries["llm_runtime.max_hitl_rounds"]["overridden"] is False

    delete = await admin_client.delete("/api/admin/settings/llm_runtime.max_tool_iters")
    assert delete.status_code == 204
    listing = await admin_client.get("/api/admin/settings")
    entries = {e["key"]: e for e in listing.json()["settings"]}
    assert entries["llm_runtime.max_tool_iters"]["overridden"] is False


@pytest.mark.integration
async def test_unknown_key_is_404(admin_client: AsyncClient) -> None:
    put = await admin_client.put("/api/admin/settings/auth.jwt_secret", json={"value": "x"})
    assert put.status_code == 404
    delete = await admin_client.delete("/api/admin/settings/nope.nope")
    assert delete.status_code == 404


@pytest.mark.integration
async def test_clear_without_override_is_404(admin_client: AsyncClient) -> None:
    delete = await admin_client.delete("/api/admin/settings/llm_runtime.max_tool_iters")
    assert delete.status_code == 404


@pytest.mark.integration
async def test_invalid_value_is_422(admin_client: AsyncClient) -> None:
    bad_type = await admin_client.put(
        "/api/admin/settings/llm_runtime.max_tool_iters", json={"value": "many"}
    )
    assert bad_type.status_code == 422
    out_of_range = await admin_client.put(
        "/api/admin/settings/llm_runtime.max_tool_iters", json={"value": 0}
    )
    assert out_of_range.status_code == 422
