"""Scraping module persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scraping.models import ScrapingJob, ScrapingJobItem, ScrapingSource


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

    # ── job items ────────────────────────────────────────

    async def add_item(self, item: ScrapingJobItem) -> ScrapingJobItem:
        self._session.add(item)
        await self._session.flush()
        return item

    async def flush(self) -> None:
        await self._session.flush()
