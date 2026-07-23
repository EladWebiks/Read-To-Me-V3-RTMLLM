"""Chapter HTTP routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.modules.books.service import BookService
from app.modules.chapters.schemas import (
    ChapterCreate,
    ChapterRead,
    ChapterSummary,
    ChapterUpdate,
)
from app.modules.chapters.service import ChapterService
from app.modules.library.service import LibraryService
from app.modules.users.schemas import UserRead

router = APIRouter(tags=["chapters"])


def _chapters(session: Annotated[AsyncSession, Depends(get_db)]) -> ChapterService:
    return ChapterService(session)


def _library(session: Annotated[AsyncSession, Depends(get_db)]) -> LibraryService:
    return LibraryService(session)


def _books(session: Annotated[AsyncSession, Depends(get_db)]) -> BookService:
    return BookService(session)


@router.get(
    "/library/books/{book_id}/chapters",
    response_model=list[ChapterSummary],
)
async def list_chapters(
    book_id: UUID,
    user: Annotated[UserRead, Depends(get_current_user)],
    library: Annotated[LibraryService, Depends(_library)],
    chapters: Annotated[ChapterService, Depends(_chapters)],
) -> list[ChapterSummary]:
    """List chapter summaries for an owned book."""
    await library.assert_access(user.id, book_id)
    return await chapters.list_summaries(book_id)


@router.post(
    "/library/books/{book_id}/chapters",
    response_model=ChapterRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_chapter(
    book_id: UUID,
    body: ChapterCreate,
    user: Annotated[UserRead, Depends(get_current_user)],
    library: Annotated[LibraryService, Depends(_library)],
    books: Annotated[BookService, Depends(_books)],
    chapters: Annotated[ChapterService, Depends(_chapters)],
) -> ChapterRead:
    """Create a chapter on an owned book."""
    await library.assert_access(user.id, book_id)
    book = await books.get(book_id)
    return await chapters.create(
        book_id,
        body,
        starting_chapter_number=book.starting_chapter_number,
    )


@router.get("/chapters/{chapter_id}", response_model=ChapterRead)
async def get_chapter(
    chapter_id: UUID,
    user: Annotated[UserRead, Depends(get_current_user)],
    library: Annotated[LibraryService, Depends(_library)],
    chapters: Annotated[ChapterService, Depends(_chapters)],
) -> ChapterRead:
    """Get full chapter content if the book is owned."""
    chapter = await chapters.get(chapter_id)
    await library.assert_access(user.id, chapter.book_id)
    return chapter


@router.put("/chapters/{chapter_id}", response_model=ChapterRead)
async def update_chapter(
    chapter_id: UUID,
    body: ChapterUpdate,
    user: Annotated[UserRead, Depends(get_current_user)],
    library: Annotated[LibraryService, Depends(_library)],
    chapters: Annotated[ChapterService, Depends(_chapters)],
) -> ChapterRead:
    """Update a chapter on an owned book."""
    existing = await chapters.get(chapter_id)
    await library.assert_access(user.id, existing.book_id)
    return await chapters.update(chapter_id, body)


@router.delete("/chapters/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chapter(
    chapter_id: UUID,
    user: Annotated[UserRead, Depends(get_current_user)],
    library: Annotated[LibraryService, Depends(_library)],
    chapters: Annotated[ChapterService, Depends(_chapters)],
) -> Response:
    """Soft-delete a chapter on an owned book."""
    existing = await chapters.get(chapter_id)
    await library.assert_access(user.id, existing.book_id)
    await chapters.soft_delete(chapter_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
