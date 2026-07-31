"""Each module reports correct per-day facts from its own tables (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.modules.downloads.models import DownloadJob
from app.modules.downloads.service import DownloadService
from app.modules.imports.repository import EpubImportRepository
from app.modules.imports.service import ImportService
from app.modules.llm.models import LlmExecution
from app.modules.llm.service import LlmService
from app.modules.scraping.models import ScrapingJob, ScrapingSource
from app.modules.scraping.service import ScrapingService
from app.modules.usage.kinds import UsageFact, UsageMetric
from app.modules.users.schemas import UserCreate
from app.modules.users.service import UserService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.factories import make_settings


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
        await db.rollback()
    await engine.dispose()


async def _uid(session: AsyncSession) -> UUID:
    user = await UserService(session).ensure_user(
        UserCreate(username=f"fac_{uuid4().hex[:8]}", password="test-pass-123")
    )
    return user.id


def _metric_map(facts: list[UsageFact], uid: UUID) -> dict[UsageMetric, float]:
    return {f.metric: f.amount for f in facts if f.user_id == uid}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_llm_daily_facts(session: AsyncSession) -> None:
    uid = await _uid(session)
    session.add_all(
        [
            LlmExecution(
                user_id=uid,
                task="chat_tools",
                provider="gemini",
                model="m1",
                tokens_in=100,
                tokens_out=40,
                cost=0.5,
                latency_ms=1,
                status="ok",
            ),
            LlmExecution(
                user_id=uid,
                task="summarize",
                provider="gemini",
                model="m2",
                tokens_in=10,
                tokens_out=5,
                cost=0.1,
                latency_ms=1,
                status="error",
            ),
        ]
    )
    await session.flush()
    today = datetime.now(UTC).date()

    facts = _metric_map(await LlmService(session, make_settings()).daily_usage_facts(today), uid)
    assert facts[UsageMetric.LLM_TOKENS_IN] == 110.0
    assert facts[UsageMetric.LLM_TOKENS_OUT] == 45.0
    assert facts[UsageMetric.LLM_COST_USD] == pytest.approx(0.6)
    assert facts[UsageMetric.LLM_EXECUTIONS] == 2.0
    assert facts[UsageMetric.LLM_FAILURES] == 1.0

    models = await LlmService(session, make_settings()).daily_model_facts(today)
    m1 = next(m for m in models if m.model == "m1")
    assert (m1.tokens_in, m1.executions) == (100, 1)
    tasks = await LlmService(session, make_settings()).daily_task_facts(today)
    assert {t.task for t in tasks} >= {"chat_tools", "summarize"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_download_daily_facts_include_soft_deleted(session: AsyncSession) -> None:
    uid = await _uid(session)
    from app.modules.books.schemas import BookCreate
    from app.modules.library.service import LibraryService

    book = await LibraryService(session).add_book(
        uid, BookCreate(title="Facts", author="A", description="d")
    )
    session.add_all(
        [
            DownloadJob(
                user_id=uid,
                book_id=book.id,
                chapter_from=1,
                chapter_to=3,
                provider="edge",
                voice="v",
                rate="1.0",
                status="complete",
                total_count=3,
            ),
            DownloadJob(
                user_id=uid,
                book_id=book.id,
                chapter_from=1,
                chapter_to=2,
                provider="edge",
                voice="v",
                rate="1.0",
                status="failed",
                total_count=2,
                deleted_at=datetime.now(UTC),
            ),
        ]
    )
    await session.flush()
    facts = _metric_map(
        await DownloadService(session).daily_usage_facts(datetime.now(UTC).date()), uid
    )
    assert facts[UsageMetric.AUDIO_CHAPTERS] == 5.0  # deleted row still counts
    assert facts[UsageMetric.AUDIO_JOBS] == 2.0
    assert facts[UsageMetric.AUDIO_JOBS_FAILED] == 1.0


async def _any_source(session: AsyncSession) -> ScrapingSource:
    source = (await session.execute(select(ScrapingSource).limit(1))).scalar_one_or_none()
    if source is None:
        source = ScrapingSource(name=f"src_{uuid4().hex[:8]}", base_domains=["example.com"])
        session.add(source)
        await session.flush()
    return source


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scrape_and_epub_daily_facts(session: AsyncSession) -> None:
    uid = await _uid(session)
    source = await _any_source(session)
    session.add(
        ScrapingJob(
            user_id=uid,
            source_id=source.id,
            start_url="https://x/y",
            mode="range",
            status="failed",
            chapters_done=40,
        )
    )
    repo = EpubImportRepository(session)
    done = await repo.add(uid)
    await repo.set_terminal(done.id, status="completed", chapter_count=9)
    failed = await repo.add(uid)
    await repo.set_terminal(failed.id, status="failed", chapter_count=0)
    await session.flush()
    today = datetime.now(UTC).date()

    scrape = _metric_map(await ScrapingService(session).daily_usage_facts(today), uid)
    assert scrape[UsageMetric.SCRAPE_CHAPTERS] == 40.0
    assert scrape[UsageMetric.SCRAPE_JOBS] == 1.0
    assert scrape[UsageMetric.SCRAPE_JOBS_FAILED] == 1.0

    epub = _metric_map(await ImportService(session).daily_usage_facts(today), uid)
    assert epub[UsageMetric.EPUB_IMPORTS] == 1.0
    assert epub[UsageMetric.EPUB_IMPORTS_FAILED] == 1.0
