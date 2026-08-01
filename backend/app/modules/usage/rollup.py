"""Nightly usage rollup + backfill. The ONLY usage file importing domain modules.

Idempotent per day (delete + insert); the cron re-rolls a trailing window
because facts land late (running scrape jobs, next-day EPUB completions).
Raw tables stay the source of truth — this is a rebuildable cache (spec §6).

Runbook: after worker downtime longer than the window, run
    uv run python -m app.modules.usage.rollup <YYYY-MM-DD>
to backfill from that date (also the initial-deploy backfill).
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import UsageSettings, get_settings
from app.modules.downloads.service import DownloadService
from app.modules.imports.service import ImportService
from app.modules.llm.service import LlmService
from app.modules.runtime_config.service import RuntimeConfigService
from app.modules.scraping.service import ScrapingService
from app.modules.usage.repository import UsageRepository

logger = logging.getLogger(__name__)


async def roll_day(session: AsyncSession, day: date) -> None:
    """Collect every module's facts for one UTC day and replace that day."""
    settings = get_settings()
    llm = LlmService(session, settings)
    repo = UsageRepository(session)
    facts = [
        *await llm.daily_usage_facts(day),
        *await DownloadService(session).daily_usage_facts(day),
        *await ScrapingService(session).daily_usage_facts(day),
        *await ImportService(session).daily_usage_facts(day),
        *await repo.rejection_facts(day),
    ]
    await repo.replace_day(day, facts)
    await repo.replace_llm_day(
        day, await llm.daily_model_facts(day), await llm.daily_task_facts(day)
    )


async def _roll_range(session: AsyncSession, start: date, end: date) -> int:
    """Roll [start, end) one day at a time, committing per day."""
    rolled = 0
    day = start
    while day < end:
        await roll_day(session, day)
        await session.commit()
        rolled += 1
        day += timedelta(days=1)
    return rolled


async def roll_usage_window(_ctx: object) -> None:
    """arq cron: re-roll the trailing window (late facts converge, spec §6)."""
    from app.core.orm import import_all_models

    import_all_models()
    settings = get_settings()
    engine = create_async_engine(settings.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with factory() as session:
            effective = await RuntimeConfigService(session, settings).get_effective(UsageSettings)
            today = datetime.now(UTC).date()
            start = today - timedelta(days=effective.rollup_window_days)
            rolled = await _roll_range(session, start, today)
        logger.info("usage rollup complete", extra={"days": rolled})
    finally:
        await engine.dispose()


async def backfill(start: date) -> None:
    """Roll [start, today). Initial deploy + downtime recovery (see runbook)."""
    from app.core.orm import import_all_models

    import_all_models()
    settings = get_settings()
    engine = create_async_engine(settings.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with factory() as session:
            rolled = await _roll_range(session, start, datetime.now(UTC).date())
        logger.info(
            "usage backfill complete",
            extra={"start": start.isoformat(), "days": rolled},
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 2:  # noqa: PLR2004 — argv is [module, date]
        raise SystemExit("usage: python -m app.modules.usage.rollup <YYYY-MM-DD>")
    asyncio.run(backfill(date.fromisoformat(sys.argv[1])))
