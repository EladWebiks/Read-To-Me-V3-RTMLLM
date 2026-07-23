"""Download job persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.downloads.models import DownloadJob


class DownloadRepository:
    """DB access for download_jobs only."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, job: DownloadJob) -> DownloadJob:
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def get_for_user(self, job_id: UUID, user_id: UUID) -> DownloadJob | None:
        stmt = select(DownloadJob).where(
            DownloadJob.id == job_id,
            DownloadJob.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, job_id: UUID) -> DownloadJob | None:
        stmt = select(DownloadJob).where(DownloadJob.id == job_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: UUID,
        book_id: UUID | None = None,
        *,
        limit: int = 20,
        include_expired: bool = False,
    ) -> list[DownloadJob]:
        stmt = (
            select(DownloadJob)
            .where(DownloadJob.user_id == user_id)
            .order_by(DownloadJob.created_at.desc())
            .limit(limit)
        )
        if book_id is not None:
            stmt = stmt.where(DownloadJob.book_id == book_id)
        if not include_expired:
            now = datetime.now(UTC)
            stmt = stmt.where(or_(DownloadJob.expires_at.is_(None), DownloadJob.expires_at > now))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_expired(
        self,
        user_id: UUID,
        book_id: UUID | None = None,
    ) -> list[DownloadJob]:
        now = datetime.now(UTC)
        stmt = select(DownloadJob).where(
            DownloadJob.user_id == user_id,
            DownloadJob.expires_at.is_not(None),
            DownloadJob.expires_at <= now,
        )
        if book_id is not None:
            stmt = stmt.where(DownloadJob.book_id == book_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, job: DownloadJob) -> None:
        await self._session.delete(job)

    async def flush(self) -> None:
        await self._session.flush()
