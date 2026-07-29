"""Chapter business logic."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chapters.exceptions import (
    ChapterNotFoundError,
    ChapterNumberConflictError,
)
from app.modules.chapters.models import Chapter
from app.modules.chapters.repository import ChapterRepository
from app.modules.chapters.schemas import (
    ChapterContentHit,
    ChapterCreate,
    ChapterRead,
    ChapterSummary,
    ChapterUpdate,
)


def _word_count(content: str) -> int:
    return len(content.split())


class ChapterService:
    """Owns chapter CRUD rules."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = ChapterRepository(session)

    async def count_for_book(self, book_id: UUID) -> int:
        """Count chapters for one book."""
        return await self._repo.count_for_book(book_id)

    async def count_for_books(self, book_ids: list[UUID]) -> dict[UUID, int]:
        """Count chapters for many books."""
        return await self._repo.counts_for_books(book_ids)

    async def content_digest(self, book_id: UUID) -> str:
        """Return a stable database-side digest of active chapter content."""
        return await self._repo.content_digest(book_id)

    async def list_summaries(self, book_id: UUID) -> list[ChapterSummary]:
        """List chapter summaries for a book."""
        chapters = await self._repo.list_for_book(book_id)
        return [ChapterSummary.model_validate(chapter) for chapter in chapters]

    async def list_content_for_summary(self, book_id: UUID) -> list[ChapterRead]:
        """List full chapter data for a derived summary."""
        chapters = await self._repo.list_for_book(book_id)
        return [ChapterRead.model_validate(chapter) for chapter in chapters]

    async def get(self, chapter_id: UUID) -> ChapterRead:
        """Get full chapter content."""
        chapter = await self._require(chapter_id)
        return ChapterRead.model_validate(chapter)

    async def get_by_number(self, book_id: UUID, chapter_number: int) -> ChapterRead:
        """Get chapter by book + number."""
        chapter = await self._repo.get_by_number(book_id, chapter_number)
        if chapter is None:
            raise ChapterNotFoundError(f"{book_id}:{chapter_number}")
        return ChapterRead.model_validate(chapter)

    async def create(
        self,
        book_id: UUID,
        data: ChapterCreate,
        *,
        starting_chapter_number: int,
    ) -> ChapterRead:
        """Create a chapter with auto or explicit numbering."""
        number = await self._resolve_number(
            book_id,
            data.chapter_number,
            starting_chapter_number,
        )
        chapter = Chapter(
            book_id=book_id,
            chapter_number=number,
            title=data.title.strip(),
            content=data.content,
            word_count=_word_count(data.content),
        )
        created = await self._repo.add(chapter)
        return ChapterRead.model_validate(created)

    async def update(self, chapter_id: UUID, data: ChapterUpdate) -> ChapterRead:
        """Update chapter fields."""
        chapter = await self._require(chapter_id)
        await self._apply_update(chapter, data)
        await self._repo.flush()
        await self._repo.refresh(chapter)
        return ChapterRead.model_validate(chapter)

    async def soft_delete(self, chapter_id: UUID) -> None:
        """Soft-delete one chapter."""
        chapter = await self._require(chapter_id)
        await self._repo.soft_delete(chapter)

    async def soft_delete_for_book(self, book_id: UUID) -> None:
        """Soft-delete all chapters for a book."""
        await self._repo.soft_delete_for_book(book_id)

    async def upsert_by_number(
        self,
        book_id: UUID,
        chapter_number: int,
        title: str,
        content: str,
    ) -> ChapterRead:
        """Create or update a chapter by book + number (used by scraping)."""
        existing = await self._repo.get_by_number(book_id, chapter_number)
        if existing is not None:
            existing.title = title.strip()
            existing.content = content
            existing.word_count = _word_count(content)
            await self._repo.flush()
            await self._repo.refresh(existing)
            return ChapterRead.model_validate(existing)
        chapter = Chapter(
            book_id=book_id,
            chapter_number=chapter_number,
            title=title.strip(),
            content=content,
            word_count=_word_count(content),
        )
        created = await self._repo.add(chapter)
        return ChapterRead.model_validate(created)

    async def search_in_books(
        self,
        book_ids: list[UUID],
        query: str,
        *,
        limit: int = 20,
    ) -> list[ChapterContentHit]:
        """Search chapter text within the given books (caller enforces ownership)."""
        rows = await self._repo.search_content(book_ids, query, limit=limit)
        return [
            ChapterContentHit(
                chapter_id=chapter.id,
                book_id=chapter.book_id,
                chapter_number=chapter.chapter_number,
                chapter_title=chapter.title,
                snippet=snippet,
            )
            for chapter, snippet in rows
        ]

    async def _require(self, chapter_id: UUID) -> Chapter:
        chapter = await self._repo.get_by_id(chapter_id)
        if chapter is None:
            raise ChapterNotFoundError(str(chapter_id))
        return chapter

    async def _resolve_number(
        self,
        book_id: UUID,
        explicit: int | None,
        starting_chapter_number: int,
    ) -> int:
        if explicit is not None:
            existing = await self._repo.get_by_number(book_id, explicit)
            if existing is not None:
                raise ChapterNumberConflictError(str(explicit))
            return explicit
        current_max = await self._repo.max_chapter_number(book_id)
        if current_max is None:
            return starting_chapter_number
        return current_max + 1

    async def _apply_update(self, chapter: Chapter, data: ChapterUpdate) -> None:
        if data.chapter_number is not None:
            conflict = await self._repo.get_by_number(
                chapter.book_id,
                data.chapter_number,
            )
            if conflict is not None and conflict.id != chapter.id:
                raise ChapterNumberConflictError(str(data.chapter_number))
            chapter.chapter_number = data.chapter_number
        if data.title is not None:
            chapter.title = data.title.strip()
        if data.content is not None:
            chapter.content = data.content
            chapter.word_count = _word_count(data.content)
