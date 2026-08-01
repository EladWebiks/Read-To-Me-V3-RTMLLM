"""Tier rows drive the loop budget without restart (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from app.core.config import Settings, get_settings
from app.modules.llm.chat_service import ChatService
from app.modules.llm.types import (
    ToolCall,
    ToolCallingRequest,
    ToolCallingResponse,
    Usage,
)
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.seed import seed_membership_policies
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.factories import make_settings
from tests.llm.stream_fakes import stream_from_call


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
    )


async def _user(session: AsyncSession) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(username=f"tier_{uuid4().hex[:8]}", password="test-pass-123")
    )


async def _tighten_free_tier(session: AsyncSession, **values: int | float) -> None:
    row = (
        await session.execute(
            select(MembershipPolicy).where(MembershipPolicy.membership == "free")
        )
    ).scalar_one()
    for field, value in values.items():
        setattr(row, field, value)
    await session.commit()


def _tool_then_text_llm() -> Any:
    calls = {"n": 0}

    async def _fake(req: ToolCallingRequest, **_kwargs: Any) -> ToolCallingResponse:
        del req
        calls["n"] += 1
        if calls["n"] == 1:
            return ToolCallingResponse(
                text=None,
                tool_calls=[ToolCall(id="t1", name="search_user_books", arguments={"query": "x"})],
                usage=Usage(10, 5),
                model="gemini-3.5-flash-lite",
                provider="gemini",
            )
        return ToolCallingResponse(
            text="All done.",
            tool_calls=[],
            usage=Usage(10, 5),
            model="gemini-3.5-flash-lite",
            provider="gemini",
        )

    return _fake


@pytest.mark.integration
@pytest.mark.asyncio
async def test_all_null_row_behaves_like_settings(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(session)
    service = ChatService(session, _settings())
    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_tool_then_text_llm()))
    events = [e async for e in service.stream_chat(user, "list my books", None)]
    assert events[-1].event == "done"
    assert events[-1].data["status"] == "complete"
    assert events[-1].data["membership"] == "free"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tier_row_tightens_iters_without_restart(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The fake needs 2 LLM rounds (tool round + answer); tier allows 1.
    await _tighten_free_tier(session, max_tool_iters=1)
    user = await _user(session)
    service = ChatService(session, _settings())
    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_tool_then_text_llm()))
    events = [e async for e in service.stream_chat(user, "list my books", None)]
    error = next(e for e in events if e.event == "error")
    assert error.data["code"] == "budget_exceeded"
    assert "iterations" in error.data["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tier_row_tightens_cost_cap(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _tighten_free_tier(session, max_turn_cost_usd=0.000001)
    user = await _user(session)
    service = ChatService(session, _settings())

    async def _costly(req: ToolCallingRequest, **_kwargs: Any) -> ToolCallingResponse:
        del req
        return ToolCallingResponse(
            text=None,
            tool_calls=[ToolCall(id="c1", name="search_user_books", arguments={"query": "x"})],
            usage=Usage(10, 5, cost_usd=0.01),
            model="gemini-3.5-flash-lite",
            provider="gemini",
        )

    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_costly))
    events = [e async for e in service.stream_chat(user, "hello", None)]
    error = next(e for e in events if e.event == "error")
    assert error.data["code"] == "budget_exceeded"
