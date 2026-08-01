"""Turn-start LLM quota enforcement through the real chat pipeline (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.core.config import Settings, get_settings
from app.modules.llm.chat_service import ChatService
from app.modules.llm.models import LlmExecution
from app.modules.llm.types import ToolCallingRequest, ToolCallingResponse, Usage
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.seed import seed_membership_policies
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.factories import make_settings
from tests.llm.stream_fakes import stream_from_call


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(delete(MembershipQuota))
        await db.execute(delete(MembershipPolicy))
        await db.commit()
        await seed_membership_policies(db)
        yield db
        await db.rollback()
        await db.execute(delete(MembershipQuota))
        await db.execute(delete(MembershipPolicy))
        await db.commit()
        await seed_membership_policies(db)
    await engine.dispose()


def _settings() -> Settings:
    return make_settings(
        llm_enabled=True,
        gemini_api_key="test-key",
        llm_provider="gemini",
        llm_model="gemini-3.5-flash-lite",
    )


async def _user(session: AsyncSession, *, is_admin: bool = False) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(username=f"quo_{uuid4().hex[:8]}", password="test-pass-123", is_admin=is_admin)
    )


async def _seed_usage(
    session: AsyncSession, user_id: UUID, *, tokens_in: int, tokens_out: int, cost: float
) -> None:
    session.add(
        LlmExecution(
            user_id=user_id,
            task="chat_tools",
            provider="gemini",
            model="gemini-3.5-flash-lite",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            latency_ms=10,
            status="ok",
        )
    )
    await session.commit()


async def _set_quota(session: AsyncSession, kind: QuotaKind, limit: float | None) -> None:
    await session.execute(
        delete(MembershipQuota).where(
            MembershipQuota.membership == "free",
            MembershipQuota.quota_kind == kind.value,
        )
    )
    if limit is not None:
        session.add(MembershipQuota(membership="free", quota_kind=kind.value, limit_value=limit))
    await session.commit()


def _text_llm(counter: dict[str, int]) -> Any:
    async def _fake(req: ToolCallingRequest, **_kwargs: Any) -> ToolCallingResponse:
        del req
        counter["calls"] += 1
        return ToolCallingResponse(
            text="Hello!",
            tool_calls=[],
            usage=Usage(5, 5),
            model="gemini-3.5-flash-lite",
            provider="gemini",
        )

    return _fake


async def _run_turn(
    session: AsyncSession,
    user: UserRead,
    counter: dict[str, int],
    monkeypatch: pytest.MonkeyPatch,
) -> list[Any]:
    service = ChatService(session, _settings())
    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_text_llm(counter)))
    return [e async for e in service.stream_chat(user, "hi", None)]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_over_cap_blocks_before_any_provider_call(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _set_quota(session, QuotaKind.LLM_TOKENS, 100)
    user = await _user(session)
    await _seed_usage(session, user.id, tokens_in=60, tokens_out=50, cost=0.0)  # 110 >= 100
    counter = {"calls": 0}
    events = await _run_turn(session, user, counter, monkeypatch)
    error = next(e for e in events if e.event == "error")
    assert error.data["code"] == "quota_exceeded"
    assert error.data["kind"] == "llm_tokens"
    assert "resets_at" in error.data
    assert counter["calls"] == 0  # BEFORE any provider call
    assert not [e for e in events if e.event == "done"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_near_cap_still_runs(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    await _set_quota(session, QuotaKind.LLM_TOKENS, 200)
    user = await _user(session)
    await _seed_usage(session, user.id, tokens_in=60, tokens_out=50, cost=0.0)  # 110 < 200
    counter = {"calls": 0}
    events = await _run_turn(session, user, counter, monkeypatch)
    assert events[-1].event == "done"
    assert counter["calls"] == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cost_cap_blocks(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    await _set_quota(session, QuotaKind.LLM_COST_USD, 1.0)
    user = await _user(session)
    await _seed_usage(session, user.id, tokens_in=1, tokens_out=1, cost=2.5)
    counter = {"calls": 0}
    events = await _run_turn(session, user, counter, monkeypatch)
    error = next(e for e in events if e.event == "error")
    assert error.data["code"] == "quota_exceeded"
    assert error.data["kind"] == "llm_cost_usd"
    assert counter["calls"] == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_is_exempt_from_quota(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _set_quota(session, QuotaKind.LLM_TOKENS, 10)
    user = await _user(session, is_admin=True)
    await _seed_usage(session, user.id, tokens_in=100, tokens_out=100, cost=0.0)
    counter = {"calls": 0}
    events = await _run_turn(session, user, counter, monkeypatch)
    assert events[-1].event == "done"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_raising_or_removing_the_rule_unblocks_immediately(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Limits are read fresh per turn: no cache, no restart.

    (Only the 'free' tier is registered in this suite, so a 'tier upgrade' is
    simulated by removing the tier's rule — the freshness property is identical.)
    """
    await _set_quota(session, QuotaKind.LLM_TOKENS, 100)
    user = await _user(session)
    await _seed_usage(session, user.id, tokens_in=60, tokens_out=50, cost=0.0)
    counter = {"calls": 0}
    blocked = await _run_turn(session, user, counter, monkeypatch)
    assert next(e for e in blocked if e.event == "error").data["code"] == "quota_exceeded"

    await _set_quota(session, QuotaKind.LLM_TOKENS, None)  # row gone = unlimited
    events = await _run_turn(session, user, counter, monkeypatch)
    assert events[-1].event == "done"
