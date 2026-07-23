"""Chapter persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chapters.models import Chapter


class ChapterRepository:
    """DB access for the chapters table only."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, chapter_id: UUID) -> Chapter | None:
        """Return a non-deleted chapter."""
        stmt = select(Chapter).where(
            Chapter.id == chapter_id,
            Chapter.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_book(self, book_id: UUID) -> list[Chapter]:
        """List chapters for a book ordered by number."""
        stmt = (
            select(Chapter)
            .where(Chapter.book_id == book_id, Chapter.deleted_at.is_(None))
            .order_by(Chapter.chapter_number.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_number(self, book_id: UUID, chapter_number: int) -> Chapter | None:
        """Find chapter by book + number."""
        stmt = select(Chapter).where(
            Chapter.book_id == book_id,
            Chapter.chapter_number == chapter_number,
            Chapter.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def max_chapter_number(self, book_id: UUID) -> int | None:
        """Highest chapter number for a book, or None."""
        stmt = select(func.max(Chapter.chapter_number)).where(
            Chapter.book_id == book_id,
            Chapter.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def count_for_book(self, book_id: UUID) -> int:
        """Count non-deleted chapters."""
        stmt = (
            select(func.count())
            .select_from(Chapter)
            .where(
                Chapter.book_id == book_id,
                Chapter.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def counts_for_books(self, book_ids: list[UUID]) -> dict[UUID, int]:
        """Chapter counts keyed by book id."""
        if not book_ids:
            return {}
        stmt = (
            select(Chapter.book_id, func.count())
            .where(Chapter.book_id.in_(book_ids), Chapter.deleted_at.is_(None))
            .group_by(Chapter.book_id)
        )
        result = await self._session.execute(stmt)
        return {book_id: int(count) for book_id, count in result.all()}

    async def add(self, chapter: Chapter) -> Chapter:
        """Persist a chapter."""
        self._session.add(chapter)
        await self._session.flush()
        await self._session.refresh(chapter)
        return chapter

    async def flush(self) -> None:
        """Flush pending changes."""
        await self._session.flush()

    async def soft_delete(self, chapter: Chapter) -> None:
        """Soft-delete one chapter."""
        chapter.deleted_at = datetime.now(UTC)
        await self._session.flush()

    async def soft_delete_for_book(self, book_id: UUID) -> None:
        """Soft-delete all chapters for a book."""
        stmt = (
            update(Chapter)
            .where(Chapter.book_id == book_id, Chapter.deleted_at.is_(None))
            .values(deleted_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)
