"""Reading progress persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reader.models import ReadingProgress


class ProgressRepository:
    """DB access for reading_progress only."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UUID, book_id: UUID) -> ReadingProgress | None:
        """Return progress for a user/book pair."""
        stmt = select(ReadingProgress).where(
            ReadingProgress.user_id == user_id,
            ReadingProgress.book_id == book_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add(self, progress: ReadingProgress) -> ReadingProgress:
        """Insert new progress row."""
        self._session.add(progress)
        await self._session.flush()
        await self._session.refresh(progress)
        return progress

    async def list_for_user(self, user_id: UUID) -> list[ReadingProgress]:
        """All progress rows for a user."""
        stmt = select(ReadingProgress).where(ReadingProgress.user_id == user_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_for_user(self, user_id: UUID) -> ReadingProgress | None:
        """Most recently updated progress row for this user."""
        stmt = (
            select(ReadingProgress)
            .where(ReadingProgress.user_id == user_id)
            .order_by(ReadingProgress.updated_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_recent_for_user(
        self,
        user_id: UUID,
        *,
        limit: int = 10,
    ) -> list[ReadingProgress]:
        """Recent progress rows, newest first."""
        stmt = (
            select(ReadingProgress)
            .where(ReadingProgress.user_id == user_id)
            .order_by(ReadingProgress.updated_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def flush(self) -> None:
        """Flush pending updates."""
        await self._session.flush()

    async def refresh(self, progress: ReadingProgress) -> None:
        """Reload ORM attributes after flush (e.g. updated_at)."""
        await self._session.refresh(progress)
