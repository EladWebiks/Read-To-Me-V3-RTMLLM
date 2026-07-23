"""Book persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.books.models import Book


class BookRepository:
    """DB access for the books table only."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, book_id: UUID) -> Book | None:
        """Return a non-deleted book."""
        stmt = select(Book).where(Book.id == book_id, Book.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_ids(self, book_ids: list[UUID]) -> list[Book]:
        """Return non-deleted books matching the given ids."""
        if not book_ids:
            return []
        stmt = select(Book).where(Book.id.in_(book_ids), Book.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, book: Book) -> Book:
        """Persist a new book."""
        self._session.add(book)
        await self._session.flush()
        await self._session.refresh(book)
        return book

    async def soft_delete(self, book: Book) -> None:
        """Soft-delete a book."""
        book.deleted_at = datetime.now(UTC)
        await self._session.flush()

    async def flush(self) -> None:
        """Flush pending changes."""
        await self._session.flush()
