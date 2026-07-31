"""GET /api/me/usage: registry coverage, hybrid math, limits, admin (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from app.core.config import get_settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.llm.models import LlmExecution
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
from app.modules.quotas.service import QuotaService
from app.modules.usage.kinds import UsageFact, UsageMetric
from app.modules.usage.models import UsageDaily
from app.modules.usage.repository import UsageRepository
from app.modules.users.membership import Membership
from app.modules.users.models import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.dbcleanup import clear_users

_HOST = "test.local"
BASE = "/api/me/usage"


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
        for model in (UsageDaily, MembershipQuota, LlmExecution):
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


async def _create_user(username: str, *, is_admin: bool = False) -> UUID:
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


async def _seed_llm_usage(user_id: UUID, *, rolled: float, today_tokens: int) -> None:
    """A rolled closed-day row + a live llm_executions row for today."""
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        now = datetime.now(UTC)
        month_start, _ = QuotaService.current_month_window(now)
        if month_start.date() != now.date():  # skip rolled part on day 1 of month
            await UsageRepository(session).replace_day(
                month_start.date(),
                [UsageFact(user_id, UsageMetric.LLM_TOKENS_IN, rolled)],
            )
        session.add(
            LlmExecution(
                user_id=user_id,
                task="chat_tools",
                provider="gemini",
                model="m",
                tokens_in=today_tokens,
                tokens_out=0,
                cost=0.0,
                latency_ms=10,
                status="ok",
            )
        )
        session.add(
            MembershipQuota(
                membership=Membership.FREE.value,
                quota_kind=QuotaKind.LLM_TOKENS.value,
                limit_value=5000.0,
            )
        )
        await session.commit()
    await engine.dispose()


def _assert_kinds(body: dict[str, Any], *, expected_llm_tokens: float) -> None:
    """Per-kind assertions, split out to keep the test under the statement cap."""
    kinds = {k["kind"]: k for k in body["kinds"]}
    assert set(kinds) == {k.value for k in QuotaKind}  # registry-driven, all present
    llm = kinds["llm_tokens"]
    assert llm["used"] == expected_llm_tokens  # rolled closed day + live today
    assert llm["limit"] == 5000.0
    assert llm["window"] == "month"
    assert kinds["llm_cost_usd"]["limit"] is None  # no rule = unlimited
    storage = kinds["storage_bytes"]
    assert storage["window"] == "standing"
    assert storage["used"] == 0.0  # no download jobs seeded: live meter reads zero


@pytest.mark.integration
async def test_anonymous_gets_401(client: AsyncClient) -> None:
    assert (await client.get(BASE)).status_code == 401


@pytest.mark.integration
async def test_every_kind_present_with_hybrid_usage_and_limits(client: AsyncClient) -> None:
    user_id = await _create_user("me-usage-reader")
    rolled = 100.0
    now = datetime.now(UTC)
    on_day_one = QuotaService.current_month_window(now)[0].date() == now.date()
    await _seed_llm_usage(user_id, rolled=rolled, today_tokens=40)
    _login(client, user_id, "me-usage-reader")

    response = await client.get(BASE)
    assert response.status_code == 200
    body = response.json()
    assert body["membership"] == "free"
    assert body["exempt"] is False
    assert body["resets_at"].startswith(
        QuotaService.current_month_window(now)[1].date().isoformat()
    )
    _assert_kinds(body, expected_llm_tokens=40.0 if on_day_one else rolled + 40.0)


@pytest.mark.integration
async def test_admin_is_exempt_but_sees_usage(client: AsyncClient) -> None:
    user_id = await _create_user("me-usage-admin", is_admin=True)
    await _seed_llm_usage(user_id, rolled=100.0, today_tokens=40)
    _login(client, user_id, "me-usage-admin")

    body = (await client.get(BASE)).json()
    assert body["exempt"] is True
    kinds = {k["kind"]: k for k in body["kinds"]}
    assert kinds["llm_tokens"]["limit"] is None  # exempt: every limit null
    assert kinds["llm_tokens"]["used"] > 0  # usage still computed
