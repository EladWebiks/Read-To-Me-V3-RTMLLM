"""Self-serve plan listing and tier switching (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.core.deps import get_db
from app.main import app
from app.modules.runtime_config import cache
from app.modules.runtime_config.service import RuntimeConfigService
from app.modules.users.membership_service import MembershipService
from app.modules.users.models import User
from app.modules.users.schemas import MembershipCreate
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.admin.helpers import HOST, create_user, login
from tests.dbcleanup import clear_users


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
    async with AsyncClient(transport=transport, base_url=f"http://{HOST}") as http:
        yield http
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await clear_users(conn)
    await engine.dispose()


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as db:
        yield db
        await db.rollback()
    await engine.dispose()


@pytest.fixture
async def user(client: AsyncClient) -> UUID:
    user_id = await create_user("reader")
    login(client, user_id, "reader")
    return user_id


@pytest.fixture
async def premium(session: AsyncSession) -> None:
    await MembershipService(session).create_tier(
        MembershipCreate(slug="premium", label="Premium", rank=1, price_label="$9/mo"),
        actor_id=uuid4(),
    )
    await session.commit()


@pytest.mark.integration
async def test_plans_lists_active_tiers_with_current(
    client: AsyncClient, user: UUID, premium: None
) -> None:
    response = await client.get("/api/me/plans")
    assert response.status_code == 200
    body = response.json()
    assert body["can_switch"] is True
    assert [p["slug"] for p in body["plans"]] == ["free", "premium"]  # rank order
    assert next(p for p in body["plans"] if p["slug"] == "free")["current"] is True


@pytest.mark.integration
async def test_switch_and_noop_and_unknown(client: AsyncClient, user: UUID, premium: None) -> None:
    ok = await client.post("/api/me/membership", json={"membership": "premium"})
    assert ok.status_code == 200
    assert ok.json()["membership"] == "premium"
    noop = await client.post("/api/me/membership", json={"membership": "premium"})
    assert noop.status_code == 200
    unknown = await client.post("/api/me/membership", json={"membership": "ghost"})
    assert unknown.status_code == 404


@pytest.mark.integration
async def test_flag_off_hides_and_403s(
    client: AsyncClient, user: UUID, session: AsyncSession
) -> None:
    # Write the runtime override membership.self_switch_enabled = False using
    # the same write-and-invalidate pattern as
    # tests/runtime_config/test_effective_dependency.py
    # (test_override_changes_budget_enforcement_without_restart): a real
    # admin row (FK'd by app_settings.updated_by) + RuntimeConfigService +
    # cache.invalidate() so the flag-off is visible in this process at once.
    base = get_settings()
    admin = User(
        username="cfg-admin",
        email="cfg-admin@example.com",
        password_hash=None,
        google_sub="cfg-admin-sub",
        is_admin=True,
    )
    session.add(admin)
    await session.flush()
    await RuntimeConfigService(session, base).set_override(
        "membership.self_switch_enabled", False, admin.id
    )
    await session.commit()
    cache.invalidate()

    plans = await client.get("/api/me/plans")
    assert plans.json()["can_switch"] is False
    switch = await client.post("/api/me/membership", json={"membership": "free"})
    assert switch.status_code == 403
