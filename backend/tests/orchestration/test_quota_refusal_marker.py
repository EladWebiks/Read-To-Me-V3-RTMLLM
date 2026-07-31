"""Quota refusals persist a marker message; context building excludes it (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.core.config import Settings, get_settings
from app.modules.llm.chat_service import ChatService
from app.modules.llm.models import ConversationMessage, LlmExecution
from app.modules.llm.types import ToolCallingRequest, ToolCallingResponse
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.seed import seed_membership_policies
from app.modules.orchestration.service import QUOTA_REFUSAL_ROLE, _to_llm_messages
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
from app.modules.users.membership import Membership
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
        for model in (MembershipQuota, MembershipPolicy, LlmExecution):
            await db.execute(delete(model))
        await db.commit()
        await seed_membership_policies(db)
        yield db
        await db.rollback()
        for model in (MembershipQuota, MembershipPolicy, LlmExecution):
            await db.execute(delete(model))
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
        UserCreate(username=f"ref_{uuid4().hex[:8]}", password="test-pass-123")
    )


async def _block_user(session: AsyncSession, user_id: UUID) -> None:
    """Tiny token quota + existing usage puts the user at/over the cap."""
    session.add(
        MembershipQuota(
            membership=Membership.FREE.value,
            quota_kind=QuotaKind.LLM_TOKENS.value,
            limit_value=10.0,
        )
    )
    session.add(
        LlmExecution(
            user_id=user_id,
            task="chat_tools",
            provider="gemini",
            model="m",
            tokens_in=10,
            tokens_out=5,
            cost=0.0,
            latency_ms=10,
            status="ok",
        )
    )
    await session.commit()


def _never_llm() -> Any:
    async def _fake(req: ToolCallingRequest, **_kwargs: Any) -> ToolCallingResponse:
        raise AssertionError("provider must not be called")

    return _fake


@pytest.mark.integration
async def test_refusal_persists_marker_matching_sse_detail(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(session)
    await _block_user(session, user.id)
    service = ChatService(session, _settings())
    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_never_llm()))

    events = [e async for e in service.stream_chat(user, "hello", None)]
    error = next(e for e in events if e.event == "error")
    assert error.data["code"] == "quota_exceeded"
    conv_id = UUID(str(events[0].data["conversation_id"]))

    rows = (
        (
            await session.execute(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conv_id)
                .order_by(ConversationMessage.created_at)
            )
        )
        .scalars()
        .all()
    )
    roles = [row.role for row in rows]
    assert roles == ["user", QUOTA_REFUSAL_ROLE]  # orphan explained, nothing else
    assert rows[-1].content == error.data["detail"]  # same user copy as the SSE event


@pytest.mark.unit
def test_context_builder_excludes_quota_refusal_rows() -> None:
    """The unknown-role filter (service.py Role(row.role) -> ValueError -> skip)
    must keep refusal copy out of LLM prompts. This test pins that contract."""
    rows = [
        ConversationMessage(
            conversation_id=uuid4(),
            role=role,
            content=content,
            created_at=datetime.now(UTC),
        )
        for role, content in (
            ("user", "hi"),
            (QUOTA_REFUSAL_ROLE, "Monthly AI tokens quota reached (15/10 tokens)."),
            ("assistant", "hello"),
        )
    ]
    contents = [m.content for m in _to_llm_messages(rows)]
    assert "hi" in contents
    assert "hello" in contents
    assert not any("quota" in c for c in contents)
