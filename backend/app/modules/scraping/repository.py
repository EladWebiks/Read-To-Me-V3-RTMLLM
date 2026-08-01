"""Scraping module persistence."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scraping.models import ScrapingJob, ScrapingJobItem, ScrapingSource
from app.modules.usage.kinds import UsageFact, UsageMetric
from app.modules.usage.repository import day_window


class ScrapingRepository:
    """DB access for scraping tables only."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── sources ──────────────────────────────────────────

    async def get_source_by_name(self, name: str) -> ScrapingSource | None:
        stmt = select(ScrapingSource).where(ScrapingSource.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_source(self, source_id: UUID) -> ScrapingSource | None:
        stmt = select(ScrapingSource).where(ScrapingSource.id == source_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_sources(self) -> list[ScrapingSource]:
        stmt = select(ScrapingSource).order_by(ScrapingSource.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def add_source(self, source: ScrapingSource) -> ScrapingSource:
        self._session.add(source)
        await self._session.flush()
        await self._session.refresh(source)
        return source

    # ── jobs ─────────────────────────────────────────────

    async def add_job(self, job: ScrapingJob) -> ScrapingJob:
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def chapters_in_period(
        self,
        user_id: UUID,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        """Chapters fetched by this user's jobs created in the window."""
        stmt = select(func.coalesce(func.sum(ScrapingJob.chapters_done), 0)).where(
            ScrapingJob.user_id == user_id,
            ScrapingJob.created_at >= period_start,
            ScrapingJob.created_at < period_end,
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def chapters_for_users(
        self,
        user_ids: list[UUID],
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> dict[UUID, int]:
        """Per-user month chapter totals for the backoffice usage table."""
        if not user_ids:
            return {}
        stmt = (
            select(
                ScrapingJob.user_id,
                func.coalesce(func.sum(ScrapingJob.chapters_done), 0),
            )
            .where(
                ScrapingJob.user_id.in_(user_ids),
                ScrapingJob.created_at >= period_start,
                ScrapingJob.created_at < period_end,
            )
            .group_by(ScrapingJob.user_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return {row[0]: int(row[1]) for row in rows}

    async def get_job(self, job_id: UUID) -> ScrapingJob | None:
        stmt = select(ScrapingJob).where(ScrapingJob.id == job_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_job_for_user(self, job_id: UUID, user_id: UUID) -> ScrapingJob | None:
        stmt = select(ScrapingJob).where(
            ScrapingJob.id == job_id,
            ScrapingJob.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_jobs_for_user(self, user_id: UUID, *, limit: int = 20) -> list[ScrapingJob]:
        stmt = (
            select(ScrapingJob)
            .where(ScrapingJob.user_id == user_id)
            .order_by(ScrapingJob.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_job(self, job: ScrapingJob) -> None:
        """Hard-delete a job and its chapter items (book is kept)."""
        await self._session.execute(
            delete(ScrapingJobItem).where(ScrapingJobItem.job_id == job.id)
        )
        await self._session.delete(job)
        await self._session.flush()

    async def delete_jobs_for_book(self, book_id: UUID) -> None:
        """Hard-delete every scrape job tied to a book."""
        stmt = select(ScrapingJob).where(ScrapingJob.book_id == book_id)
        result = await self._session.execute(stmt)
        jobs = list(result.scalars().all())
        for job in jobs:
            await self.delete_job(job)

    # ── job items ────────────────────────────────────────

    async def add_item(self, item: ScrapingJobItem) -> ScrapingJobItem:
        self._session.add(item)
        await self._session.flush()
        return item

    async def flush(self) -> None:
        await self._session.flush()

    # ── backoffice reads ─────────────────────────────────

    async def list_jobs_admin(
        self, *, status: str | None, limit: int, offset: int
    ) -> tuple[list[ScrapingJob], int]:
        """Backoffice page over ALL users' jobs, newest first."""
        conditions = [] if status is None else [ScrapingJob.status == status]
        total_stmt = select(func.count()).select_from(ScrapingJob).where(*conditions)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(ScrapingJob)
            .where(*conditions)
            .order_by(ScrapingJob.created_at.desc(), ScrapingJob.id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows), total

    async def daily_usage_facts(self, day: date) -> list[UsageFact]:
        """Per-user scraping facts for one UTC day (builder-facing, spec §6)."""
        start, end = day_window(day)
        failed = func.count(ScrapingJob.id).filter(ScrapingJob.status == "failed")
        stmt = (
            select(
                ScrapingJob.user_id,
                func.coalesce(func.sum(ScrapingJob.chapters_done), 0),
                func.count(ScrapingJob.id),
                failed,
            )
            .where(ScrapingJob.created_at >= start, ScrapingJob.created_at < end)
            .group_by(ScrapingJob.user_id)
        )
        facts: list[UsageFact] = []
        for user_id, chapters, jobs, failed_count in (await self._session.execute(stmt)).all():
            facts.append(UsageFact(user_id, UsageMetric.SCRAPE_CHAPTERS, float(chapters)))
            facts.append(UsageFact(user_id, UsageMetric.SCRAPE_JOBS, float(jobs)))
            facts.append(UsageFact(user_id, UsageMetric.SCRAPE_JOBS_FAILED, float(failed_count)))
        return facts
