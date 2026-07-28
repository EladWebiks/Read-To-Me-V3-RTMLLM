"""Reading progress business logic."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chapters.exceptions import ChapterNotFoundError
from app.modules.chapters.service import ChapterService
from app.modules.library.service import LibraryService
from app.modules.reader.exceptions import ProgressNotFoundError
from app.modules.reader.models import ReadingProgress
from app.modules.reader.repository import ProgressRepository
from app.modules.reader.schemas import ProgressRead, ProgressUpsert


class ReaderService:
    """Owns reading progress get/upsert with ownership checks."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = ProgressRepository(session)
        self._library = LibraryService(session)
        self._chapters = ChapterService(session)

    async def get_progress(self, user_id: UUID, book_id: UUID) -> ProgressRead:
        """Return progress or raise if none saved yet."""
        await self._library.assert_access(user_id, book_id)
        progress = await self._repo.get(user_id, book_id)
        if progress is None:
            raise ProgressNotFoundError(str(book_id))
        return ProgressRead.model_validate(progress)

    async def continue_reading(self, user_id: UUID) -> ProgressRead | None:
        """Most recent progress, or None if the user has never read."""
        progress = await self._repo.get_latest_for_user(user_id)
        if progress is None:
            return None
        return ProgressRead.model_validate(progress)

    async def list_recent(self, user_id: UUID, *, limit: int = 10) -> list[ProgressRead]:
        """Recently updated reading positions for this user."""
        rows = await self._repo.list_recent_for_user(user_id, limit=limit)
        return [ProgressRead.model_validate(row) for row in rows]

    async def upsert_progress(
        self,
        user_id: UUID,
        book_id: UUID,
        data: ProgressUpsert,
    ) -> ProgressRead:
        """Create or update reading position for a book."""
        await self._library.assert_access(user_id, book_id)
        chapter = await self._chapters.get(data.chapter_id)
        if chapter.book_id != book_id:
            raise ChapterNotFoundError(str(data.chapter_id))
        existing = await self._repo.get(user_id, book_id)
        if existing is None:
            created = await self._repo.add(
                ReadingProgress(
                    user_id=user_id,
                    book_id=book_id,
                    chapter_id=data.chapter_id,
                    chapter_number=data.chapter_number,
                    paragraph_index=data.paragraph_index,
                    word_index=data.word_index,
                )
            )
            return ProgressRead.model_validate(created)
        existing.chapter_id = data.chapter_id
        existing.chapter_number = data.chapter_number
        existing.paragraph_index = data.paragraph_index
        existing.word_index = data.word_index
        await self._repo.flush()
        await self._repo.refresh(existing)
        return ProgressRead.model_validate(existing)
