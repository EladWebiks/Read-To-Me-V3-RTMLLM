"""Orchestration loop tests (offline LLM)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.modules.books.schemas import BookCreate
from app.modules.library.service import LibraryService
from app.modules.llm.chat_service import ChatService
from app.modules.llm.models import ToolCallRecord
from app.modules.llm.types import (
    ToolCall,
    ToolCallingRequest,
    ToolCallingResponse,
    ToolCallingStreamChunk,
    Usage,
)
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.factories import make_settings
from tests.llm.stream_fakes import stream_from_call


@pytest.fixture
async def orch_session() -> AsyncIterator[AsyncSession]:
    settings = get_settings()
    engine = create_async_engine(settings.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _seed_user_with_book(session: AsyncSession) -> UserRead:
    user = await UserService(session).ensure_user(
        UserCreate(username=f"orch_{uuid4().hex[:8]}", password="test-pass-123")
    )
    await LibraryService(session).add_book(
        user.id,
        BookCreate(title="Cultivation Modern", author="A", description="d"),
    )
    await session.commit()
    return user


def _fake_tools_llm() -> Any:
    calls = {"n": 0}

    async def _fake_call_tools(
        req: ToolCallingRequest,
        **_kwargs: Any,
    ) -> ToolCallingResponse:
        del req
        calls["n"] += 1
        if calls["n"] == 1:
            return ToolCallingResponse(
                text=None,
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name="search_user_books",
                        arguments={"query": "Cultivation"},
                    )
                ],
                usage=Usage(10, 5),
                model="gemini-3.5-flash-lite",
                provider="gemini",
            )
        return ToolCallingResponse(
            text="You have Cultivation Modern in your library.",
            tool_calls=[],
            usage=Usage(20, 8),
            model="gemini-3.5-flash-lite",
            provider="gemini",
        )

    return _fake_call_tools


@pytest.mark.integration
@pytest.mark.asyncio
async def test_orchestration_runs_search_user_books(
    orch_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(
        llm_enabled=True,
        gemini_api_key="test-key",
        llm_provider="gemini",
        llm_model="gemini-3.5-flash-lite",
    )
    user = await _seed_user_with_book(orch_session)
    service = ChatService(orch_session, settings)
    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_fake_tools_llm()))

    events = [e async for e in service.stream_chat(user.id, "what books?", None)]
    kinds = [e.event for e in events]
    assert kinds[0] == "meta"
    assert "tool_result" in kinds
    assert kinds[-1] == "done"

    rows = (
        (
            await orch_session.execute(
                select(ToolCallRecord).where(ToolCallRecord.tool_name == "search_user_books")
            )
        )
        .scalars()
        .all()
    )
    assert rows[-1].status == "success"

    conv_id = UUID(str(events[0].data["conversation_id"]))
    payload = await service.get_conversation(user.id, conv_id)
    assert "Cultivation Modern" in payload["messages"][-1]["content"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_thinking_step_is_sent_before_llm_finishes(
    orch_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(
        llm_enabled=True,
        gemini_api_key="test-key",
        llm_provider="gemini",
        llm_model="gemini-3.5-flash-lite",
    )
    user = await _seed_user_with_book(orch_session)
    service = ChatService(orch_session, settings)
    calls = {"count": 0}

    async def _call(
        _req: ToolCallingRequest,
        **_kwargs: Any,
    ) -> ToolCallingResponse:
        calls["count"] += 1
        return ToolCallingResponse(text="Done.", usage=Usage(1, 1))

    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_call))
    stream = service.stream_chat(user.id, "hello", None)
    assert (await anext(stream)).event == "meta"
    step = await anext(stream)
    assert step.event == "step"
    assert step.data["label"] == "Understanding your request…"
    assert calls["count"] == 0
    _remaining = [event async for event in stream]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_final_answer_is_not_discarded_when_usage_crosses_soft_limit(
    orch_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(
        llm_enabled=True,
        gemini_api_key="test-key",
        llm_max_turn_tokens_in=5,
    )
    user = await _seed_user_with_book(orch_session)
    service = ChatService(orch_session, settings)

    async def _call(
        _req: ToolCallingRequest,
        **_kwargs: Any,
    ) -> ToolCallingResponse:
        return ToolCallingResponse(text="Useful final answer.", usage=Usage(10, 1))

    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_call))
    events = [event async for event in service.stream_chat(user.id, "question", None)]

    assert not any(event.event == "error" for event in events)
    assert (
        "".join(str(event.data["text"]) for event in events if event.event == "delta")
        == "Useful final answer."
    )
    assert events[-1].event == "done"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_text_delta_arrives_before_tool_stream_finishes(
    orch_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(llm_enabled=True, gemini_api_key="test-key")
    user = await _seed_user_with_book(orch_session)
    service = ChatService(orch_session, settings)
    release = asyncio.Event()

    async def _stream(
        _req: ToolCallingRequest,
        **_kwargs: Any,
    ) -> AsyncIterator[ToolCallingStreamChunk]:
        yield ToolCallingStreamChunk(text="Early")
        await release.wait()
        response = ToolCallingResponse(text="Early", usage=Usage(2, 1))
        yield ToolCallingStreamChunk(done=True, response=response)

    monkeypatch.setattr(service._llm, "stream_tools", _stream)
    events = service.stream_chat(user.id, "question", None)
    assert (await anext(events)).event == "meta"
    assert (await anext(events)).event == "step"

    delta = await anext(events)

    assert delta.event == "delta"
    assert delta.data["text"] == "Early"
    assert not release.is_set()
    release.set()
    remaining = [event async for event in events]
    assert remaining[-1].event == "done"
