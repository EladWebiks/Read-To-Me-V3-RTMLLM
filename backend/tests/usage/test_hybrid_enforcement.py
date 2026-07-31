"""Rolled days count toward quotas even with no raw rows (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.modules.books.schemas import BookCreate
from app.modules.chapters.service import ChapterService
from app.modules.downloads.schemas import DownloadCreate
from app.modules.downloads.service import DownloadService
from app.modules.library.service import LibraryService
from app.modules.llm.chat_service import ChatService
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.seed import seed_membership_policies
from app.modules.quotas.exceptions import QuotaExceededError
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
from app.modules.quotas.service import QuotaService
from app.modules.usage.kinds import UsageFact, UsageMetric
from app.modules.usage.models import UsageDaily
from app.modules.usage.repository import UsageRepository
from app.modules.users.membership import Membership
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
        for model in (UsageDaily, MembershipQuota, MembershipPolicy):
            await db.execute(delete(model))
        await db.commit()
        await seed_membership_policies(db)
        yield db
        await db.rollback()
        for model in (UsageDaily, MembershipQuota, MembershipPolicy):
            await db.execute(delete(model))
        await db.commit()
        await seed_membership_policies(db)
    await engine.dispose()


async def _user(session: AsyncSession) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(username=f"hyb_{uuid4().hex[:8]}", password="test-pass-123")
    )


async def _set_quota(session: AsyncSession, kind: QuotaKind, limit: float) -> None:
    session.add(
        MembershipQuota(membership=Membership.FREE.value, quota_kind=kind.value, limit_value=limit)
    )
    await session.commit()


async def _seed_rolled_closed_day(
    session: AsyncSession, user_id: Any, metric: UsageMetric, amount: float
) -> None:
    """A rolled row for a PAST day of this month (no raw rows exist for it)."""
    now = datetime.now(UTC)
    month_start, _ = QuotaService.current_month_window(now)
    day = month_start.date()  # first of month: always < today unless day 1...
    if day == now.date():
        pytest.skip("first day of month: no closed days in the current month")
    await UsageRepository(session).replace_day(day, [UsageFact(user_id, metric, amount)])
    await session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chat_quota_counts_rolled_days(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(session)
    await _set_quota(session, QuotaKind.LLM_TOKENS, 100)
    await _seed_rolled_closed_day(session, user.id, UsageMetric.LLM_TOKENS_IN, 150.0)

    service = ChatService(
        session,
        make_settings(
            llm_enabled=True,
            gemini_api_key="test-key",
            llm_provider="gemini",
            llm_model="gemini-3.5-flash-lite",
        ),
    )

    async def _never(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("provider must not be called")

    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_never))
    events = [e async for e in service.stream_chat(user, "hi", None)]
    assert next(e for e in events if e.event == "error").data["code"] == "quota_exceeded"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audio_quota_counts_rolled_days(session: AsyncSession) -> None:
    user = await _user(session)
    book = await LibraryService(session).add_book(
        user.id, BookCreate(title="Hybrid", author="A", description="d")
    )
    await ChapterService(session).upsert_by_number(book.id, 1, "Ch 1", "text " * 50)
    await session.commit()
    await _set_quota(session, QuotaKind.AUDIO_CHAPTERS, 10)
    await _seed_rolled_closed_day(session, user.id, UsageMetric.AUDIO_CHAPTERS, 10.0)

    with pytest.raises(QuotaExceededError):
        await DownloadService(session).create(
            user.id, DownloadCreate(book_id=book.id, chapter_from=1, chapter_to=1)
        )
