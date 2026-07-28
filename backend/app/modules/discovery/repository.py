"""DB access for discovered books and sources."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.discovery.models import BookSource, DiscoveredBook


class DiscoveryRepository:
    """Owns discovered_books / book_sources queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_book(self, book_id: UUID) -> DiscoveredBook | None:
        result = await self._session.execute(
            select(DiscoveredBook).where(DiscoveredBook.id == book_id)
        )
        return result.scalar_one_or_none()

    async def find_by_normalized_title(self, normalized: str) -> DiscoveredBook | None:
        result = await self._session.execute(
            select(DiscoveredBook).where(DiscoveredBook.normalized_title == normalized)
        )
        return result.scalar_one_or_none()

    async def search_by_title(self, normalized_query: str, *, limit: int) -> list[DiscoveredBook]:
        pattern = f"%{normalized_query}%"
        result = await self._session.execute(
            select(DiscoveredBook)
            .where(DiscoveredBook.normalized_title.like(pattern))
            .order_by(DiscoveredBook.normalized_title)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_sources(self, book_ids: list[UUID]) -> list[BookSource]:
        if not book_ids:
            return []
        result = await self._session.execute(
            select(BookSource).where(BookSource.discovered_book_id.in_(book_ids))
        )
        return list(result.scalars().all())

    async def get_source_by_url(self, source: str, book_url: str) -> BookSource | None:
        result = await self._session.execute(
            select(BookSource).where(
                BookSource.source == source,
                BookSource.book_url == book_url,
            )
        )
        return result.scalar_one_or_none()

    async def add_book(self, book: DiscoveredBook) -> DiscoveredBook:
        self._session.add(book)
        await self._session.flush()
        return book

    async def add_source(self, source: BookSource) -> BookSource:
        self._session.add(source)
        await self._session.flush()
        return source
