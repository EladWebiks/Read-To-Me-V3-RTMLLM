"""Orchestration loop tests (offline LLM)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.core.config import Settings, get_settings
from app.modules.books.schemas import BookCreate
from app.modules.library.service import LibraryService
from app.modules.llm.chat_service import ChatService
from app.modules.llm.models import ToolCallRecord
from app.modules.llm.types import ToolCall, ToolCallingRequest, ToolCallingResponse, Usage
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def orch_session() -> AsyncIterator[AsyncSession]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _seed_user_with_book(session: AsyncSession) -> UserRead:
    user = await UserService(session).ensure_user(
        UserCreate(username=f"orch_{uuid4().hex[:8]}", password="test-pass-123", role="user")
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
    settings = Settings(
        llm_enabled=True,
        gemini_api_key="test-key",
        llm_provider="gemini",
        llm_model="gemini-3.5-flash-lite",
    )
    user = await _seed_user_with_book(orch_session)
    service = ChatService(orch_session, settings)
    monkeypatch.setattr(service._llm, "call_tools", _fake_tools_llm())

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
