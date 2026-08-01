"""Admin per-user quota override API (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota, UserQuotaOverride
from app.modules.users.models import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.dbcleanup import clear_users

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


async def _clean(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        for model in (UserQuotaOverride, MembershipQuota):
            await session.execute(delete(model))
        await session.commit()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await _clean(session_factory)
    async with engine.begin() as conn:
        await clear_users(conn)
    app.dependency_overrides[get_db] = _make_db_override(session_factory)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=f"http://{_HOST}") as http:
        yield http
    app.dependency_overrides.clear()
    await _clean(session_factory)
    async with engine.begin() as conn:
        await clear_users(conn)
    await engine.dispose()


async def _seed_users() -> tuple[UUID, UUID]:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        admin = User(
            username="uq-admin",
            email="uq-admin@example.com",
            password_hash=None,
            google_sub="uq-admin-sub",
            is_admin=True,
        )
        reader = User(
            username="uq-reader",
            email="uq-reader@example.com",
            password_hash=None,
            google_sub="uq-reader-sub",
            is_admin=False,
        )
        session.add_all([admin, reader])
        await session.flush()
        session.add(
            MembershipQuota(
                membership="free",
                quota_kind=QuotaKind.LLM_TOKENS.value,
                limit_value=1000.0,
            )
        )
        await session.commit()
        ids = (admin.id, reader.id)
    await engine.dispose()
    return ids


@pytest.fixture
async def ctx(client: AsyncClient) -> tuple[AsyncClient, UUID]:
    admin_id, reader_id = await _seed_users()
    token = create_access_token(user_id=admin_id, username="uq-admin", settings=get_settings())
    client.cookies.set(COOKIE_NAME, token, domain=_HOST, path="/")
    return client, reader_id


@pytest.mark.integration
async def test_anonymous_gets_401(client: AsyncClient) -> None:
    assert (await client.get(f"/api/admin/users/{uuid4()}/quotas")).status_code == 401


@pytest.mark.integration
async def test_get_serves_registry_tier_limits_and_overrides(
    ctx: tuple[AsyncClient, UUID],
) -> None:
    client, reader_id = ctx
    body = (await client.get(f"/api/admin/users/{reader_id}/quotas")).json()
    assert body["membership"] == "free"
    assert {k["kind"] for k in body["kinds"]} == {k.value for k in QuotaKind}
    assert body["tier_limits"] == {"llm_tokens": 1000.0}  # sparse
    assert body["overrides"] == []


@pytest.mark.integration
async def test_put_upserts_and_delete_clears(ctx: tuple[AsyncClient, UUID]) -> None:
    client, reader_id = ctx
    base = f"/api/admin/users/{reader_id}/quotas"
    put = await client.put(f"{base}/llm_tokens", json={"limit_value": 9000})
    assert put.status_code == 200
    assert put.json()["limit_value"] == 9000

    replaced = await client.put(f"{base}/llm_tokens", json={"limit_value": 50})
    assert replaced.json()["limit_value"] == 50
    assert len((await client.get(base)).json()["overrides"]) == 1

    assert (await client.delete(f"{base}/llm_tokens")).status_code == 204
    assert (await client.delete(f"{base}/llm_tokens")).status_code == 404


@pytest.mark.integration
async def test_put_accepts_zero_as_a_blocking_override(ctx: tuple[AsyncClient, UUID]) -> None:
    """0 blocks the kind for this user; unlimited is DELETE, never a 0 write."""
    client, reader_id = ctx
    base = f"/api/admin/users/{reader_id}/quotas"
    put = await client.put(f"{base}/llm_tokens", json={"limit_value": 0})
    assert put.status_code == 200
    assert put.json()["limit_value"] == 0
    assert (await client.get(base)).json()["overrides"][0]["limit_value"] == 0


@pytest.mark.integration
async def test_validation_and_unknown_user(ctx: tuple[AsyncClient, UUID]) -> None:
    client, reader_id = ctx
    base = f"/api/admin/users/{reader_id}/quotas"
    assert (await client.put(f"{base}/llm_tokens", json={"limit_value": -1})).status_code == 422
    assert (await client.put(f"{base}/not_a_kind", json={"limit_value": 5})).status_code == 422
    unknown = await client.get(f"/api/admin/users/{uuid4()}/quotas")
    assert unknown.status_code == 404  # UserNotFoundError mapping
