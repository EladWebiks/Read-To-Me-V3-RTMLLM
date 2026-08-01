"""Admin membership-quotas API: authz + upsert/clear (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from uuid import UUID

import pytest
from app.core.config import get_settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
from app.modules.users.models import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.dbcleanup import clear_users

_HOST = "test.local"
BASE = "/api/admin/membership-quotas"


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
    async with session_factory() as session:
        await session.execute(delete(MembershipQuota))
        await session.commit()
    async with engine.begin() as conn:
        await clear_users(conn)
    app.dependency_overrides[get_db] = _make_db_override(session_factory)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=f"http://{_HOST}") as http:
        yield http
    app.dependency_overrides.clear()
    async with session_factory() as session:
        await session.execute(delete(MembershipQuota))
        await session.commit()
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


@pytest.fixture
async def admin_client(client: AsyncClient) -> AsyncClient:
    user_id = await _create_user("quota-admin", is_admin=True)
    token = create_access_token(user_id=user_id, username="quota-admin", settings=get_settings())
    client.cookies.set(COOKIE_NAME, token, domain=_HOST, path="/")
    return client


@pytest.fixture
async def reader_client(client: AsyncClient) -> AsyncClient:
    """An authenticated NON-admin — quota rules are backoffice-only."""
    user_id = await _create_user("quota-reader", is_admin=False)
    token = create_access_token(user_id=user_id, username="quota-reader", settings=get_settings())
    client.cookies.set(COOKIE_NAME, token, domain=_HOST, path="/")
    return client


@pytest.mark.integration
async def test_anonymous_gets_401(client: AsyncClient) -> None:
    assert (await client.get(BASE)).status_code == 401


@pytest.mark.integration
async def test_non_admin_gets_403_on_every_verb(reader_client: AsyncClient) -> None:
    """A signed-in reader must not read, raise, or clear anyone's quota rules."""
    assert (await reader_client.get(BASE)).status_code == 403
    put = await reader_client.put(f"{BASE}/free/llm_tokens", json={"limit_value": 10**9})
    assert put.status_code == 403
    assert (await reader_client.delete(f"{BASE}/free/llm_tokens")).status_code == 403


@pytest.mark.integration
async def test_list_serves_registry_and_rows(admin_client: AsyncClient) -> None:
    response = await admin_client.get(BASE)
    assert response.status_code == 200
    body = response.json()
    assert {k["kind"] for k in body["kinds"]} == {k.value for k in QuotaKind}
    assert body["quotas"] == []  # sparse: nothing configured = all unlimited


@pytest.mark.integration
async def test_put_upserts_and_delete_clears(admin_client: AsyncClient) -> None:
    put = await admin_client.put(f"{BASE}/free/llm_tokens", json={"limit_value": 500000})
    assert put.status_code == 200
    assert put.json()["limit_value"] == 500000

    replaced = await admin_client.put(f"{BASE}/free/llm_tokens", json={"limit_value": 250000})
    assert replaced.json()["limit_value"] == 250000
    listed = await admin_client.get(BASE)
    assert len(listed.json()["quotas"]) == 1

    assert (await admin_client.delete(f"{BASE}/free/llm_tokens")).status_code == 204
    assert (await admin_client.delete(f"{BASE}/free/llm_tokens")).status_code == 404


@pytest.mark.integration
async def test_put_accepts_zero_as_a_blocking_limit(admin_client: AsyncClient) -> None:
    """0 is a real limit (no allowance), not a synonym for unlimited."""
    put = await admin_client.put(f"{BASE}/free/llm_tokens", json={"limit_value": 0})
    assert put.status_code == 200
    assert put.json()["limit_value"] == 0

    listed = await admin_client.get(BASE)
    assert listed.json()["quotas"] == [
        {
            "membership": "free",
            "quota_kind": "llm_tokens",
            "limit_value": 0.0,
            "updated_at": listed.json()["quotas"][0]["updated_at"],
        }
    ]  # a row exists — unlimited would be no row at all


@pytest.mark.integration
async def test_validation_rejects_bad_inputs(admin_client: AsyncClient) -> None:
    assert (
        await admin_client.put(f"{BASE}/free/llm_tokens", json={"limit_value": -1})
    ).status_code == 422
    assert (
        await admin_client.put(f"{BASE}/free/not_a_kind", json={"limit_value": 5})
    ).status_code == 422
    assert (
        await admin_client.put(f"{BASE}/platinum/llm_tokens", json={"limit_value": 5})
    ).status_code == 404  # tier is not in the registry
