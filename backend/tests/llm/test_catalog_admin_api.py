"""Admin catalog API: authz matrix + typed errors (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from uuid import UUID

import pytest
from app.core.config import get_settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.users.models import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.dbcleanup import clear_users

# http.cookiejar drops cookies scoped to a single-label host (see test_auth_api.py).
_HOST = "test.local"
BASE = "/api/admin/llm/catalog"
LITE = "gemini-3.5-flash-lite"


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
async def client(seeded_catalog: None) -> AsyncIterator[AsyncClient]:
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
    user_id = await _create_user("catalog-admin", is_admin=True)
    _login(client, user_id, "catalog-admin")
    return client


@pytest.mark.integration
async def test_anonymous_gets_401(client: AsyncClient) -> None:
    assert (await client.get(BASE)).status_code == 401


@pytest.mark.integration
async def test_non_admin_gets_403(client: AsyncClient) -> None:
    user_id = await _create_user("catalog-reader", is_admin=False)
    _login(client, user_id, "catalog-reader")
    assert (await client.get(BASE)).status_code == 403
    patch = await client.patch(f"{BASE}/models/gemini/{LITE}", json={"enabled": False})
    assert patch.status_code == 403


@pytest.mark.integration
async def test_admin_lists_catalog_with_pricing(admin_client: AsyncClient) -> None:
    response = await admin_client.get(BASE)
    assert response.status_code == 200
    gemini = next(p for p in response.json()["providers"] if p["name"] == "gemini")
    assert gemini["has_adapter"] is True
    lite = next(m for m in gemini["models"] if m["model_name"] == LITE)
    assert lite["effective_enabled"] is True
    assert lite["input_cost_per_1m"] == 0.10


@pytest.mark.integration
async def test_patch_model_and_provider(admin_client: AsyncClient) -> None:
    patch = await admin_client.patch(
        f"{BASE}/models/gemini/{LITE}",
        json={"input_cost_per_1m": 0.5, "enabled": False},
    )
    assert patch.status_code == 200
    assert patch.json()["input_cost_per_1m"] == 0.5
    assert patch.json()["enabled"] is False

    provider = await admin_client.patch(f"{BASE}/providers/gemini", json={"enabled": False})
    assert provider.status_code == 200
    assert all(m["effective_enabled"] is False for m in provider.json()["models"])


@pytest.mark.integration
async def test_post_model_and_typed_errors(admin_client: AsyncClient) -> None:
    body = {
        "provider": "gemini",
        "model_name": "gemini-3.7-pro",
        "capabilities": ["FAST_CHAT", "TOOL_CALLING"],
        "context_window": 200_000,
        "input_cost_per_1m": 1.25,
        "output_cost_per_1m": 5.0,
    }
    created = await admin_client.post(f"{BASE}/models", json=body)
    assert created.status_code == 201
    assert created.json()["effective_enabled"] is True

    duplicate = await admin_client.post(f"{BASE}/models", json=body)
    assert duplicate.status_code == 409

    no_adapter = await admin_client.post(f"{BASE}/models", json={**body, "provider": "openai"})
    assert no_adapter.status_code == 422

    bad_capability = await admin_client.post(
        f"{BASE}/models",
        json={**body, "model_name": "x", "capabilities": ["NOT_A_CAP"]},
    )
    assert bad_capability.status_code == 422

    missing = await admin_client.patch(f"{BASE}/models/gemini/nope", json={"enabled": True})
    assert missing.status_code == 404
    missing_provider = await admin_client.patch(f"{BASE}/providers/nope", json={"enabled": True})
    assert missing_provider.status_code == 404
