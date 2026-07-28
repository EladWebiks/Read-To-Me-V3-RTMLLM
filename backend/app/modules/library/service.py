"""Library business logic."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.books.schemas import BookCreate, BookRead, BookUpdate
from app.modules.books.service import BookService
from app.modules.chapters.service import ChapterService
from app.modules.library.exceptions import BookAccessDeniedError
from app.modules.library.models import UserBook
from app.modules.library.repository import LibraryRepository
from app.modules.library.schemas import LibraryContentHit, LibraryContentSearchResult

_CONTENT_SEARCH_LIMIT = 20
_SNIPPET_MAX = 240


class LibraryService:
    """Owns user library membership and book access checks."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = LibraryRepository(session)
        self._books = BookService(session)
        self._chapters = ChapterService(session)

    async def assert_access(self, user_id: UUID, book_id: UUID) -> None:
        """Raise if the user does not own the book."""
        membership = await self._repo.get_membership(user_id, book_id)
        if membership is None:
            raise BookAccessDeniedError(str(book_id))

    async def list_books(self, user_id: UUID) -> list[BookRead]:
        """List books in the user's library."""
        from app.modules.reader.repository import ProgressRepository

        book_ids = await self._repo.list_book_ids(user_id)
        counts = await self._chapters.count_for_books(book_ids)
        books = await self._books.list_read(book_ids, counts)
        progress_rows = await ProgressRepository(self._session).list_for_user(user_id)
        by_book = {row.book_id: row for row in progress_rows}
        enriched: list[BookRead] = []
        for book in books:
            row = by_book.get(book.id)
            if row is None:
                enriched.append(book)
                continue
            enriched.append(
                book.model_copy(
                    update={
                        "last_read_chapter_number": row.chapter_number,
                        "last_read_at": row.updated_at,
                    }
                )
            )
        return enriched

    async def get_book(self, user_id: UUID, book_id: UUID) -> BookRead:
        """Get one owned book."""
        await self.assert_access(user_id, book_id)
        count = await self._chapters.count_for_book(book_id)
        return await self._books.get_read(book_id, chapter_count=count)

    async def search_content(
        self,
        user_id: UUID,
        query: str,
        *,
        limit: int = _CONTENT_SEARCH_LIMIT,
    ) -> LibraryContentSearchResult:
        """Search owned books by metadata and chapter text (snippets only)."""
        cleaned = query.strip()
        if not cleaned:
            return LibraryContentSearchResult(hits=[], total=0)
        book_ids = await self._repo.list_book_ids(user_id)
        if not book_ids:
            return LibraryContentSearchResult(hits=[], total=0)
        books = await self._books.list_read(book_ids, {})
        by_id = {book.id: book for book in books}
        hits = _metadata_hits(books, cleaned)
        chapter_hits = await self._chapters.search_in_books(
            book_ids,
            cleaned,
            limit=limit,
        )
        for ch in chapter_hits:
            book = by_id.get(ch.book_id)
            if book is None:
                continue
            hits.append(
                LibraryContentHit(
                    book_id=ch.book_id,
                    book_title=book.title,
                    match_source="chapter",
                    snippet=_clip(ch.snippet),
                    chapter_id=ch.chapter_id,
                    chapter_number=ch.chapter_number,
                    chapter_title=ch.chapter_title,
                )
            )
        capped = hits[:limit]
        return LibraryContentSearchResult(hits=capped, total=len(capped))

    async def add_book(self, user_id: UUID, data: BookCreate) -> BookRead:
        """Create a book and add it to the user's library."""
        book = await self._books.create(data)
        await self._repo.add(UserBook(user_id=user_id, book_id=book.id))
        return await self._books.get_read(book.id, chapter_count=0)

    async def update_book(
        self,
        user_id: UUID,
        book_id: UUID,
        data: BookUpdate,
    ) -> BookRead:
        """Update an owned book."""
        await self.assert_access(user_id, book_id)
        await self._books.update(book_id, data)
        count = await self._chapters.count_for_book(book_id)
        return await self._books.get_read(book_id, chapter_count=count)

    async def remove_book(self, user_id: UUID, book_id: UUID) -> None:
        """Remove membership and soft-delete the book + chapters."""
        from app.modules.scraping.service import ScrapingService

        membership = await self._repo.get_membership(user_id, book_id)
        if membership is None:
            raise BookAccessDeniedError(str(book_id))
        await ScrapingService(self._session).delete_jobs_for_book(book_id)
        await self._chapters.soft_delete_for_book(book_id)
        await self._books.soft_delete(book_id)
        await self._repo.soft_delete(membership)

    async def upload_cover(
        self,
        user_id: UUID,
        book_id: UUID,
        data: bytes,
        content_type: str,
    ) -> BookRead:
        """Store a cover image in MinIO and attach it to the book."""
        await self.assert_access(user_id, book_id)
        from app.core.storage import put_bytes

        key = f"covers/{book_id}.jpg"
        await put_bytes(key, data, content_type or "image/jpeg")
        await self._books.set_cover_key(book_id, key)
        count = await self._chapters.count_for_book(book_id)
        return await self._books.get_read(book_id, chapter_count=count)


def _metadata_hits(books: list[BookRead], query: str) -> list[LibraryContentHit]:
    needle = query.lower()
    hits: list[LibraryContentHit] = []
    for book in books:
        blob = f"{book.title}\n{book.author}\n{book.description}".lower()
        if needle not in blob:
            continue
        hits.append(
            LibraryContentHit(
                book_id=book.id,
                book_title=book.title,
                match_source="book_metadata",
                snippet=_clip(book.description or book.title),
            )
        )
    return hits


def _clip(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= _SNIPPET_MAX:
        return cleaned
    return cleaned[: _SNIPPET_MAX - 3] + "..."
