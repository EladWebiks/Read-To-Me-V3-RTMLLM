"""Override resolution: user row beats tier row, looser or tighter (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota, UserQuotaOverride
from app.modules.quotas.service import QuotaService
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        for model in (UserQuotaOverride, MembershipQuota):
            await db.execute(delete(model))
        await db.commit()
        yield db
        await db.rollback()
        for model in (UserQuotaOverride, MembershipQuota):
            await db.execute(delete(model))
        await db.commit()
    await engine.dispose()


async def _user(session: AsyncSession, *, is_admin: bool = False) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(username=f"ovr_{uuid4().hex[:8]}", password="test-pass-123", is_admin=is_admin)
    )


async def _tier_quota(session: AsyncSession, kind: QuotaKind, limit: float) -> None:
    session.add(MembershipQuota(membership="free", quota_kind=kind.value, limit_value=limit))
    await session.commit()


async def _seed_used_chapter(session: AsyncSession, user_id: UUID, book_id: UUID) -> None:
    """A completed this-month audio job for one chapter (the metered usage)."""
    from app.modules.downloads.models import DownloadJob

    session.add(
        DownloadJob(
            user_id=user_id,
            book_id=book_id,
            chapter_from=1,
            chapter_to=1,
            provider="edge",
            voice="v",
            rate="1.0",
            status="complete",
            total_count=1,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    await session.commit()


async def _override(session: AsyncSession, user_id: UUID, kind: str, limit: float) -> None:
    session.add(UserQuotaOverride(user_id=user_id, quota_kind=kind, limit_value=limit))
    await session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_override_beats_tier_looser_and_tighter(session: AsyncSession) -> None:
    await _tier_quota(session, QuotaKind.LLM_TOKENS, 1000.0)
    await _tier_quota(session, QuotaKind.AUDIO_CHAPTERS, 50.0)
    user = await _user(session)
    await _override(session, user.id, QuotaKind.LLM_TOKENS.value, 9000.0)  # looser
    await _override(session, user.id, QuotaKind.AUDIO_CHAPTERS.value, 5.0)  # tighter

    limits = await QuotaService(session).limits_for(user)
    assert limits.limit(QuotaKind.LLM_TOKENS) == 9000.0
    assert limits.limit(QuotaKind.AUDIO_CHAPTERS) == 5.0
    assert limits.limit(QuotaKind.SCRAPE_CHAPTERS) is None  # neither row = unlimited


@pytest.mark.integration
@pytest.mark.asyncio
async def test_absent_override_falls_back_to_tier(session: AsyncSession) -> None:
    await _tier_quota(session, QuotaKind.LLM_TOKENS, 1000.0)
    user = await _user(session)
    limits = await QuotaService(session).limits_for(user)
    assert limits.limit(QuotaKind.LLM_TOKENS) == 1000.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_stays_exempt_despite_override(session: AsyncSession) -> None:
    user = await _user(session, is_admin=True)
    await _override(session, user.id, QuotaKind.LLM_TOKENS.value, 1.0)
    limits = await QuotaService(session).limits_for(user)
    assert limits.exempt is True
    assert limits.limit(QuotaKind.LLM_TOKENS) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unknown_kind_override_rows_are_skipped(session: AsyncSession) -> None:
    user = await _user(session)
    await _override(session, user.id, "retired_kind", 1.0)
    limits = await QuotaService(session).limits_for(user)
    assert limits.values == {}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_limits_for_user_id_sees_overrides(session: AsyncSession) -> None:
    user = await _user(session)
    await _override(session, user.id, QuotaKind.EPUB_IMPORTS.value, 2.0)
    limits = await QuotaService(session).limits_for_user_id(user.id)
    assert limits.limit(QuotaKind.EPUB_IMPORTS) == 2.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enforcement_honors_override_without_restart(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec §7.5: a blocking tier limit is lifted by an override on the very
    next attempt — limits are read fresh per check (no cache, no restart).
    Uses the real downloads choke point.

    Enforcement meters usage ALREADY consumed this month (not the requested
    range), so blocking needs a prior job at the cap — same shape as
    tests/quotas/test_audio_quota.py::test_over_cap_blocks_new_audio_job.
    """
    from app.modules.books.schemas import BookCreate
    from app.modules.chapters.service import ChapterService
    from app.modules.downloads.schemas import DownloadCreate
    from app.modules.downloads.service import DownloadService
    from app.modules.library.service import LibraryService
    from app.modules.quotas.exceptions import QuotaExceededError

    monkeypatch.setattr(DownloadService, "_enqueue", AsyncMock(return_value=None))
    user = await _user(session)
    book = await LibraryService(session).add_book(
        user.id, BookCreate(title="Override", author="A", description="d")
    )
    await ChapterService(session).upsert_by_number(book.id, 1, "Ch 1", "text " * 50)
    await _seed_used_chapter(session, user.id, book.id)
    await _tier_quota(session, QuotaKind.AUDIO_CHAPTERS, 1.0)  # 1 used >= 1

    body = DownloadCreate(book_id=book.id, chapter_from=1, chapter_to=1)
    with pytest.raises(QuotaExceededError):
        await DownloadService(session).create(user.id, body)

    await _override(session, user.id, QuotaKind.AUDIO_CHAPTERS.value, 100.0)
    job = await DownloadService(session).create(user.id, body)  # next attempt passes
    assert job is not None
