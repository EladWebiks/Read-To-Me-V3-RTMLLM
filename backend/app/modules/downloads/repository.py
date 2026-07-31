"""Download job persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
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

    async def list_all_expired(self, *, limit: int = 200) -> list[DownloadJob]:
        """Expired jobs across all users (for background purge)."""
        now = datetime.now(UTC)
        stmt = (
            select(DownloadJob)
            .where(
                DownloadJob.expires_at.is_not(None),
                DownloadJob.expires_at <= now,
            )
            .order_by(DownloadJob.expires_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, job: DownloadJob) -> None:
        await self._session.delete(job)

    async def flush(self) -> None:
        await self._session.flush()

    async def list_jobs_admin(
        self, *, status: str | None, limit: int, offset: int
    ) -> tuple[list[DownloadJob], int]:
        """Backoffice page over ALL users' jobs, newest first (no expiry purge)."""
        conditions = [] if status is None else [DownloadJob.status == status]
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
