"""Discovery business logic — title search + persist candidates."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.normalize import normalize_title
from app.modules.discovery.models import BookSource, DiscoveredBook
from app.modules.discovery.repository import DiscoveryRepository
from app.modules.discovery.schemas import (
    BookSourceRead,
    DiscoveredBookRead,
    DiscoverySearchResponse,
)
from app.modules.discovery.sources.registry import search_all_sources
from app.modules.discovery.types import ExternalSearchHit
from app.modules.library.service import LibraryService

_DEFAULT_LIMIT = 8


class DiscoveryService:
    """Owns discovery search and candidate upsert."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = DiscoveryRepository(session)
        self._library = LibraryService(session)

    async def search_by_title(
        self,
        user_id: UUID,
        query: str,
        *,
        external: bool = True,
        limit: int = _DEFAULT_LIMIT,
    ) -> DiscoverySearchResponse:
        """Search internal candidates; optionally refresh from all scrape sources."""
        cleaned = query.strip()
        if not cleaned:
            return DiscoverySearchResponse(query=cleaned, results=[])
        if external:
            await self._ingest_external(cleaned)
            await self._session.commit()
        books = await self._repo.search_by_title(normalize_title(cleaned), limit=limit)
        owned = await self._owned_titles(user_id)
        return DiscoverySearchResponse(
            query=cleaned,
            results=await self._to_reads(books, owned),
        )

    async def _ingest_external(self, query: str) -> None:
        for hit in await search_all_sources(query):
            await self._upsert_hit(hit)

    async def _upsert_hit(self, hit: ExternalSearchHit) -> None:
        existing_source = await self._repo.get_source_by_url(hit.source, hit.book_url)
        if existing_source is not None:
            if hit.chapter_count_estimate is not None:
                existing_source.chapter_count_estimate = hit.chapter_count_estimate
            return
        normalized = normalize_title(hit.title)
        book = await self._repo.find_by_normalized_title(normalized)
        if book is None:
            book = await self._repo.add_book(
                DiscoveredBook(
                    title=hit.title.strip(),
                    normalized_title=normalized,
                    author=hit.author.strip(),
                )
            )
        await self._repo.add_source(
            BookSource(
                discovered_book_id=book.id,
                source=hit.source,
                book_url=hit.book_url,
                first_chapter_url=hit.first_chapter_url,
                chapter_count_estimate=hit.chapter_count_estimate,
            )
        )

    async def _owned_titles(self, user_id: UUID) -> set[str]:
        books = await self._library.list_books(user_id)
        return {normalize_title(book.title) for book in books}

    async def _to_reads(
        self,
        books: list[DiscoveredBook],
        owned: set[str],
    ) -> list[DiscoveredBookRead]:
        sources = await self._repo.list_sources([book.id for book in books])
        by_book: dict[UUID, list[BookSourceRead]] = {book.id: [] for book in books}
        for src in sources:
            by_book.setdefault(src.discovered_book_id, []).append(
                BookSourceRead.model_validate(src)
            )
        return [
            DiscoveredBookRead(
                id=book.id,
                title=book.title,
                author=book.author,
                description=book.description,
                language=book.language,
                already_owned=book.normalized_title in owned,
                sources=by_book.get(book.id, []),
                created_at=book.created_at,
                updated_at=book.updated_at,
            )
            for book in books
        ]
