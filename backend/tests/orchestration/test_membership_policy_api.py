"""Admin membership-policies API: authz + PATCH semantics (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from uuid import UUID

import pytest
from app.core.config import get_settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.seed import seed_membership_policies
from app.modules.users.models import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from tests.dbcleanup import clear_users

_HOST = "test.local"  # single-label hosts drop cookies (see test_auth_api.py)
BASE = "/api/admin/membership-policies"


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
        await session.execute(delete(MembershipPolicy))
        await session.commit()
        await seed_membership_policies(session)
    async with engine.begin() as conn:
        await clear_users(conn)
    app.dependency_overrides[get_db] = _make_db_override(session_factory)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=f"http://{_HOST}") as http:
        yield http
    app.dependency_overrides.clear()
    async with session_factory() as session:
        await session.execute(delete(MembershipPolicy))
        await session.commit()
        await seed_membership_policies(session)
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
    user_id = await _create_user("policy-admin", is_admin=True)
    _login(client, user_id, "policy-admin")
    return client


@pytest.mark.integration
async def test_anonymous_gets_401(client: AsyncClient) -> None:
    assert (await client.get(BASE)).status_code == 401


@pytest.mark.integration
async def test_non_admin_gets_403(client: AsyncClient) -> None:
    user_id = await _create_user("policy-user", is_admin=False)
    _login(client, user_id, "policy-user")
    assert (await client.get(BASE)).status_code == 403


@pytest.mark.integration
async def test_list_returns_row_per_tier_with_inherited_defaults(
    admin_client: AsyncClient,
) -> None:
    response = await admin_client.get(BASE)
    assert response.status_code == 200
    body = response.json()
    memberships = {p["membership"] for p in body["policies"]}
    assert memberships == {"free"}  # the only tier the test DB registers
    assert body["inherited"]["max_tool_iters"] >= 1
    free = next(p for p in body["policies"] if p["membership"] == "free")
    assert free["max_tool_iters"] is None  # NULL = inherit


@pytest.mark.integration
async def test_patch_sets_and_clears_fields(admin_client: AsyncClient) -> None:
    patched = await admin_client.patch(
        f"{BASE}/free", json={"max_tool_iters": 3, "max_hitl_rounds": 1}
    )
    assert patched.status_code == 200
    assert patched.json()["max_tool_iters"] == 3
    assert patched.json()["max_hitl_rounds"] == 1

    # Omitted fields unchanged; explicit null clears back to inherit.
    cleared = await admin_client.patch(f"{BASE}/free", json={"max_tool_iters": None})
    assert cleared.status_code == 200
    assert cleared.json()["max_tool_iters"] is None
    assert cleared.json()["max_hitl_rounds"] == 1


@pytest.mark.integration
async def test_patch_rejects_invalid_values_and_unknown_tier(
    admin_client: AsyncClient,
) -> None:
    assert (
        await admin_client.patch(f"{BASE}/free", json={"max_tool_iters": 0})
    ).status_code == 422
    assert (
        await admin_client.patch(f"{BASE}/platinum", json={"max_tool_iters": 3})
    ).status_code == 404  # tier is not in the registry
