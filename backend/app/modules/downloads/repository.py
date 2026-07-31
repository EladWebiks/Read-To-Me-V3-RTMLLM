"""Download job persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
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
            DownloadJob.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, job_id: UUID) -> DownloadJob | None:
        # Worker-internal lookup: deliberately unfiltered, so a job soft-deleted
        # mid-run is still updatable by the arq task that owns it.
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
            .where(DownloadJob.user_id == user_id, DownloadJob.deleted_at.is_(None))
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
            DownloadJob.deleted_at.is_(None),
            DownloadJob.expires_at.is_not(None),
            DownloadJob.expires_at <= now,
        )
        if book_id is not None:
            stmt = stmt.where(DownloadJob.book_id == book_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_all_expired(self, *, limit: int = 200) -> list[DownloadJob]:
        """Expired jobs across all users (for background purge)."""
        now = datetime.now(UTC)
        stmt = (
            select(DownloadJob)
            .where(
                DownloadJob.deleted_at.is_(None),
                DownloadJob.expires_at.is_not(None),
                DownloadJob.expires_at <= now,
            )
            .order_by(DownloadJob.expires_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, job: DownloadJob) -> None:
        """Soft delete: stamp deleted_at, keep the row for quota metering.

        Callers still purge the MinIO assets first (_delete_assets) — only
        the DB row survives, so the monthly audio meter cannot erode.
        """
        job.deleted_at = datetime.now(UTC)
        await self._session.flush()

    async def flush(self) -> None:
        await self._session.flush()

    async def list_jobs_admin(
        self, *, status: str | None, limit: int, offset: int
    ) -> tuple[list[DownloadJob], int]:
        """Backoffice page over ALL users' jobs, newest first (no expiry purge)."""
        conditions: list[ColumnElement[bool]] = [DownloadJob.deleted_at.is_(None)]
        if status is not None:
            conditions.append(DownloadJob.status == status)
        total_stmt = select(func.count()).select_from(DownloadJob).where(*conditions)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(DownloadJob)
            .where(*conditions)
            .order_by(DownloadJob.created_at.desc(), DownloadJob.id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows), total

    async def chapters_in_period(
        self,
        user_id: UUID,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        """Chapters covered by this user's jobs created in the window.

        Soft-deleted rows are INCLUDED on purpose: the synth work was already
        done, so deleting or TTL-purging a job never refunds the quota.
        total_count is stamped at creation, so pending/running jobs count
        immediately (no double-charge on retry — retries reuse the job row).
        """
        stmt = select(func.coalesce(func.sum(DownloadJob.total_count), 0)).where(
            DownloadJob.user_id == user_id,
            DownloadJob.created_at >= period_start,
            DownloadJob.created_at < period_end,
        )
        return int((await self._session.execute(stmt)).scalar_one())
