"""A resumed turn uses the policy resolved at turn start (spec §3.4)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.core.config import Settings, get_settings
from app.modules.llm.chat_service import ChatService
from app.modules.llm.types import (
    ToolCall,
    ToolCallingRequest,
    ToolCallingResponse,
    Usage,
)
from app.modules.orchestration.hitl_pause import budget_from_snapshot
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.seed import seed_membership_policies
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.factories import make_settings
from tests.llm.stream_fakes import stream_from_call

_URL = "https://novelfull.net/book/foo.html"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(delete(MembershipPolicy))
        await db.commit()
        await seed_membership_policies(db)
        yield db
        await db.rollback()
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
        llm_assistant_mode="external_allowed",
    )


async def _user(session: AsyncSession) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(username=f"frz_{uuid4().hex[:8]}", password="test-pass-123")
    )


def _scrape_then_reply() -> Any:
    calls = {"n": 0}

    async def _fake(req: ToolCallingRequest, **_kwargs: Any) -> ToolCallingResponse:
        del req
        calls["n"] += 1
        if calls["n"] == 1:
            return ToolCallingResponse(
                text=None,
                tool_calls=[
                    ToolCall(
                        id="sc1",
                        name="scrape_book_range",
                        arguments={
                            "url": _URL,
                            "start_chapter": 1,
                            "chapter_count": 10,
                        },
                    )
                ],
                usage=Usage(10, 5),
                model="gemini-3.5-flash-lite",
                provider="gemini",
            )
        return ToolCallingResponse(
            text="Understood, not scraping.",
            tool_calls=[],
            usage=Usage(12, 6),
            model="gemini-3.5-flash-lite",
            provider="gemini",
        )

    return _fake


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resume_uses_caps_frozen_at_turn_start(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tighten the tier mid-pause; the resumed turn still runs under old caps."""
    user = await _user(session)
    service = ChatService(session, _settings())
    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_scrape_then_reply()))

    events = [e async for e in service.stream_chat(user, "scrape this", None)]
    assert events[-1].data.get("status") == "awaiting_confirmation"
    call_id = UUID(str(events[-1].data["call_id"]))
    conv_id = UUID(str(events[0].data["conversation_id"]))

    # Mid-pause tier change: 1 iteration would already be exhausted.
    await session.execute(
        update(MembershipPolicy)
        .where(MembershipPolicy.membership == "free")
        .values(max_tool_iters=1)
    )
    await session.commit()

    # Decline -> the loop resumes for the wrap-up LLM round (iteration 2).
    # Frozen caps (default 6) allow it; a re-resolve (cap 1) would not.
    resume = [
        e
        async for e in service.stream_confirm(user, conv_id, call_id, approved=False, values=None)
    ]
    assert not [e for e in resume if e.event == "error"]
    assert resume[-1].data.get("status") == "complete"
    assert resume[-1].data.get("membership") == "free"


@pytest.mark.unit
def test_legacy_snapshot_without_caps_returns_none() -> None:
    raw = {
        "cost_usd": 0.1,
        "iters": 2,
        "external_calls": 1,
        "tokens_in": 5,
        "tokens_out": 3,
    }
    assert budget_from_snapshot(raw) is None


@pytest.mark.unit
def test_snapshot_roundtrip_restores_caps_and_counters() -> None:
    raw = {
        "cost_usd": 0.01,
        "iters": 2,
        "external_calls": 1,
        "tokens_in": 100,
        "tokens_out": 50,
        "caps": {
            "max_iters": 9,
            "max_external_calls": 4,
            "max_tokens_in": 1000,
            "max_tokens_out": 500,
            "max_cost_usd": 0.5,
            "run_deadline_seconds": 77,
            "max_hitl_rounds": 2,
            "membership": "free",
        },
    }
    budget = budget_from_snapshot(raw)
    assert budget is not None
    assert budget.max_iters == 9
    assert budget.iters == 2
    assert budget.max_hitl_rounds == 2
    assert budget.run_deadline_seconds == 77
    assert budget.membership == "free"
