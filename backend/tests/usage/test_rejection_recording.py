"""Rejections leave rows: chat path (same session) + detached path (own txn)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from app.core.config import Settings, get_settings
from app.modules.llm.chat_service import ChatService
from app.modules.llm.models import LlmExecution
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.seed import seed_membership_policies
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
from app.modules.usage.models import QuotaRejection
from app.modules.usage.read_service import record_rejection_detached
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
        for model in (QuotaRejection, MembershipQuota, MembershipPolicy):
            await db.execute(delete(model))
        await db.commit()
        await seed_membership_policies(db)
        yield db
        await db.rollback()
        for model in (QuotaRejection, MembershipQuota, MembershipPolicy):
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
        UserCreate(username=f"rej_{uuid4().hex[:8]}", password="test-pass-123")
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chat_rejection_writes_row(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(session)
    session.add(
        MembershipQuota(
            membership="free",
            quota_kind=QuotaKind.LLM_TOKENS.value,
            limit_value=10.0,
        )
    )
    session.add(
        LlmExecution(
            user_id=user.id,
            task="chat_tools",
            provider="gemini",
            model="m",
            tokens_in=50,
            tokens_out=50,
            cost=0.0,
            latency_ms=1,
            status="ok",
        )
    )
    await session.commit()

    service = ChatService(session, _settings())

    async def _never_called(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("provider must not be called")

    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_never_called))
    events = [e async for e in service.stream_chat(user, "hi", None)]
    assert next(e for e in events if e.event == "error").data["code"] == "quota_exceeded"

    row = (
        await session.execute(select(QuotaRejection).where(QuotaRejection.user_id == user.id))
    ).scalar_one()
    assert row.quota_kind == "llm_tokens"
    assert row.source == "chat"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_detached_recording_survives_caller_rollback(
    session: AsyncSession,
) -> None:
    """The 429 handler's write must not die with the request transaction."""
    user = await _user(session)
    await session.commit()  # the user must be visible to the detached txn (FK)
    await record_rejection_detached(user.id, QuotaKind.AUDIO_CHAPTERS, "api")
    await session.rollback()  # simulate the request txn rolling back afterwards

    row = (
        await session.execute(select(QuotaRejection).where(QuotaRejection.user_id == user.id))
    ).scalar_one()
    assert row.quota_kind == "audio_chapters"
    assert row.source == "api"
