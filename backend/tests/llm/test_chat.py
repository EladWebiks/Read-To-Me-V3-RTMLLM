"""Chat SSE and conversation persistence tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.modules.llm.chat_service import ChatService, ChatSseEvent
from app.modules.llm.repository import LlmRepository
from app.modules.llm.types import ToolCallingRequest, ToolCallingResponse, Usage
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.factories import make_settings
from tests.llm.stream_fakes import stream_from_call


@pytest.mark.unit
def test_chat_sse_event_encode() -> None:
    raw = ChatSseEvent("delta", {"text": "hi"}).encode()
    assert "event: delta" in raw
    assert '"text": "hi"' in raw


@pytest.fixture
async def chat_session() -> AsyncIterator[AsyncSession]:
    settings = get_settings()
    engine = create_async_engine(settings.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _user(session: AsyncSession) -> UserRead:
    svc = UserService(session)
    return await svc.ensure_user(
        UserCreate(username=f"chat_{uuid4().hex[:8]}", password="test-pass-123")
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_conversation_persistence(chat_session: AsyncSession) -> None:
    user = await _user(chat_session)
    repo = LlmRepository(chat_session)
    conv = await repo.create_conversation(user.id, title="hello")
    await repo.add_message(conv.id, role="user", content="hello")
    await repo.add_message(conv.id, role="assistant", content="hi")
    await chat_session.commit()

    loaded = await repo.get_conversation_for_user(conv.id, user.id)
    assert loaded is not None
    messages = await repo.list_messages(conv.id)
    assert len(messages) == 2
    assert messages[0].content == "hello"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stream_chat_persists_with_fake_llm(
    chat_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(
        llm_enabled=True,
        gemini_api_key="test-key",
        llm_provider="gemini",
        llm_model="gemini-3.5-flash-lite",
    )
    user = await _user(chat_session)
    service = ChatService(chat_session, settings)

    async def _fake_call_tools(
        req: ToolCallingRequest,
        **_kwargs: Any,
    ) -> ToolCallingResponse:
        assert req.tools
        return ToolCallingResponse(
            text="Hello world",
            tool_calls=[],
            usage=Usage(3, 2),
            model="gemini-3.5-flash-lite",
            provider="gemini",
        )

    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_fake_call_tools))

    events: list[ChatSseEvent] = []
    async for event in service.stream_chat(user, "Say hi", None):
        events.append(event)

    kinds = [e.event for e in events]
    assert kinds[0] == "meta"
    assert "delta" in kinds
    assert kinds[-1] == "done"
    conv_id = events[0].data["conversation_id"]
    payload = await service.get_conversation(user.id, UUID(str(conv_id)))
    assert len(payload["messages"]) == 2
    assert payload["messages"][1]["content"] == "Hello world"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_conversations_newest_first(chat_session: AsyncSession) -> None:
    user = await _user(chat_session)
    service = ChatService(chat_session, make_settings())
    await service._repo.create_conversation(user.id, title="older ask")
    await chat_session.commit()
    newer = await service._repo.create_conversation(user.id, title="newer ask")
    await service._repo.set_conversation_title(newer.id, "newer ask")
    await chat_session.commit()

    listed = await service.list_conversations(user.id, limit=10, offset=0)
    assert listed.total == 2
    assert listed.items[0].id == newer.id
    assert listed.items[0].title == "newer ask"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_conversation_title_tracks_latest_user_message(
    chat_session: AsyncSession,
) -> None:
    user = await _user(chat_session)
    repo = LlmRepository(chat_session)
    conv = await repo.create_conversation(user.id, title="first")
    await repo.set_conversation_title(conv.id, "second message here")
    await chat_session.commit()
    reloaded = await repo.get_conversation_for_user(conv.id, user.id)
    assert reloaded is not None
    assert reloaded.title == "second message here"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_conversation_removes_from_list(chat_session: AsyncSession) -> None:
    user = await _user(chat_session)
    service = ChatService(chat_session, make_settings())
    kept = await service._repo.create_conversation(user.id, title="keep me")
    doomed = await service._repo.create_conversation(user.id, title="delete me")
    await service._repo.add_message(doomed.id, role="user", content="delete me")
    await chat_session.commit()

    await service.delete_conversation(user.id, doomed.id)
    listed = await service.list_conversations(user.id, limit=10, offset=0)
    assert listed.total == 1
    assert listed.items[0].id == kept.id
    assert await service._repo.get_conversation_for_user(doomed.id, user.id) is None
