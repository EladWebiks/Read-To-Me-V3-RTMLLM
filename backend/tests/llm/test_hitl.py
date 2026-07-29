"""B3.3 HITL confirmation lifecycle tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from app.core.config import Settings, get_settings
from app.modules.llm.chat_service import ChatService
from app.modules.llm.models import ToolCallRecord
from app.modules.llm.repository import LlmRepository
from app.modules.llm.types import ToolCall, ToolCallingRequest, ToolCallingResponse, Usage
from app.modules.scraping.schemas import ScrapeJobRead
from app.modules.scraping.service import ScrapingService
from app.modules.tools.base import Mode, ToolContext
from app.modules.tools.definitions.scrape_book_range import ScrapeBookRangeTool
from app.modules.tools.executor import execute_tool_call
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.llm.stream_fakes import stream_from_call

_URL = "https://novelfull.net/book/foo.html"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def _user(session: AsyncSession) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(username=f"hitl_{uuid4().hex[:8]}", password="test-pass-123", role="user")
    )


def _settings() -> Settings:
    return Settings(
        llm_enabled=True,
        gemini_api_key="test-key",
        llm_provider="gemini",
        llm_model="gemini-3.5-flash-lite",
        llm_assistant_mode="external_allowed",
    )


def _fake_scrape_then_reply() -> Any:
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
                        arguments={"url": _URL, "start_chapter": 1, "chapter_count": 10},
                    )
                ],
                usage=Usage(10, 5),
                model="gemini-3.5-flash-lite",
                provider="gemini",
            )
        return ToolCallingResponse(
            text="Queued your scrape.",
            tool_calls=[],
            usage=Usage(12, 6),
            model="gemini-3.5-flash-lite",
            provider="gemini",
        )

    return _fake


def _mock_job() -> ScrapeJobRead:
    now = datetime.now(UTC)
    return ScrapeJobRead(
        id=uuid4(),
        book_id=uuid4(),
        start_url=_URL,
        mode="range",
        chapter_from=1,
        chapter_to=None,
        max_chapters=5,
        status="pending",
        chapters_done=0,
        message="Queued…",
        error=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrape_never_runs_without_confirm(session: AsyncSession) -> None:
    user = await _user(session)
    ctx = ToolContext(
        user_id=user.id,
        conversation_id=uuid4(),
        run_id=uuid4(),
        mode=Mode.EXTERNAL_ALLOWED,
        session=session,
    )
    result = await execute_tool_call(
        ScrapeBookRangeTool(),
        ToolCall(id="x", name="scrape_book_range", arguments={"url": _URL}),
        ctx,
        LlmRepository(session),
    )
    assert result["ok"] is False
    err = str(result["error"]).lower()
    assert "confirmation" in err or "scrape_book_range" in err


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hitl_pause_and_approve(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ScrapingService, "create_job", AsyncMock(return_value=_mock_job()))
    user = await _user(session)
    service = ChatService(session, _settings())
    monkeypatch.setattr(
        service._llm,
        "stream_tools",
        stream_from_call(_fake_scrape_then_reply()),
    )

    events = [e async for e in service.stream_chat(user.id, "scrape this", None)]
    assert "confirmation_request" in [e.event for e in events]
    assert events[-1].data.get("status") == "awaiting_confirmation"
    call_id = UUID(str(events[-1].data["call_id"]))
    conv_id = UUID(str(events[0].data["conversation_id"]))
    pending = await session.get(ToolCallRecord, call_id)
    assert pending is not None
    assert pending.status == "pending_confirmation"

    resume = [
        e
        async for e in service.stream_confirm(
            user.id,
            conv_id,
            call_id,
            approved=True,
            values={"start_chapter": 1, "chapter_count": 5},
        )
    ]
    assert resume[-1].data.get("status") == "complete"
    await session.refresh(pending)
    assert pending.status == "confirmed"
    assert pending.input.get("chapter_count") == 5


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hitl_reject(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _user(session)
    service = ChatService(session, _settings())
    monkeypatch.setattr(
        service._llm,
        "stream_tools",
        stream_from_call(_fake_scrape_then_reply()),
    )
    events = [e async for e in service.stream_chat(user.id, "scrape url", None)]
    call_id = UUID(str(events[-1].data["call_id"]))
    conv_id = UUID(str(events[0].data["conversation_id"]))
    resume = [
        e
        async for e in service.stream_confirm(
            user.id, conv_id, call_id, approved=False, values=None
        )
    ]
    tool_event = next(e for e in resume if e.event == "tool_result")
    assert tool_event.data["ok"] is False
    row = (
        await session.execute(select(ToolCallRecord).where(ToolCallRecord.id == call_id))
    ).scalar_one()
    assert row.status == "rejected"
