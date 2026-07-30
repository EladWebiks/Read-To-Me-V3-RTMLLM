"""Book business logic."""

from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.normalize import normalize_title
from app.core.storage import presigned_get
from app.modules.books.exceptions import BookNotFoundError
from app.modules.books.models import Book
from app.modules.books.repository import BookRepository
from app.modules.books.schemas import BookCreate, BookRead, BookUpdate


class BookService:
    """Owns book create/update/delete rules."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = BookRepository(session)

    async def get(self, book_id: UUID) -> Book:
        """Return ORM book or raise."""
        book = await self._repo.get_by_id(book_id)
        if book is None:
            raise BookNotFoundError(str(book_id))
        return book

    async def get_read(self, book_id: UUID, *, chapter_count: int = 0) -> BookRead:
        """Return public book DTO."""
        book = await self.get(book_id)
        return await _to_read(book, chapter_count)

    async def list_read(
        self,
        book_ids: list[UUID],
        counts: dict[UUID, int],
    ) -> list[BookRead]:
        """Return public DTOs for many books."""
        books = await self._repo.list_by_ids(book_ids)
        by_id = {book.id: book for book in books}
        present = [bid for bid in book_ids if bid in by_id]
        results = await asyncio.gather(
            *[_to_read(by_id[bid], counts.get(bid, 0)) for bid in present]
        )
        return list(results)

    async def create(self, data: BookCreate) -> Book:
        """Create and return a new book entity."""
        book = Book(
            title=data.title.strip(),
            normalized_title=normalize_title(data.title),
            author=data.author.strip(),
            description=data.description,
            language=data.language,
            starting_chapter_number=data.starting_chapter_number,
        )
        return await self._repo.add(book)

    async def update(self, book_id: UUID, data: BookUpdate) -> Book:
        """Apply a partial update."""
        book = await self.get(book_id)
        _apply_update(book, data)
        await self._repo.flush()
        return book

    async def set_cover_key(self, book_id: UUID, cover_object_key: str) -> None:
        """Set the cover_object_key on a book."""
        book = await self.get(book_id)
        book.cover_object_key = cover_object_key
        await self._repo.flush()

    async def soft_delete(self, book_id: UUID) -> None:
        """Soft-delete a book."""
        book = await self.get(book_id)
        await self._repo.soft_delete(book)


async def _to_read(book: Book, chapter_count: int) -> BookRead:
    payload = BookRead.model_validate(book)
    cover_url: str | None = None
    if book.cover_object_key:
        expires = get_settings().storage.signed_url_expires_seconds
        cover_url = await presigned_get(book.cover_object_key, expires)
    return payload.model_copy(
        update={"chapter_count": chapter_count, "cover_url": cover_url},
    )


def _apply_update(book: Book, data: BookUpdate) -> None:
    if data.title is not None:
        book.title = data.title.strip()
        book.normalized_title = normalize_title(data.title)
    if data.author is not None:
        book.author = data.author.strip()
    if data.description is not None:
        book.description = data.description
    if data.language is not None:
        book.language = data.language
    if data.starting_chapter_number is not None:
        book.starting_chapter_number = data.starting_chapter_number
