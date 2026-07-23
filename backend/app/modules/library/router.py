"""Library HTTP routes (owned books)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.modules.books.schemas import BookCreate, BookRead, BookUpdate
from app.modules.library.service import LibraryService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/library/books", tags=["library"])

_MAX_COVER_BYTES = 2_000_000


def _library(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LibraryService:
    return LibraryService(session)


@router.get("", response_model=list[BookRead])
async def list_books(
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[LibraryService, Depends(_library)],
) -> list[BookRead]:
    """List books in the current user's library."""
    return await service.list_books(user.id)


@router.post("", response_model=BookRead, status_code=status.HTTP_201_CREATED)
async def create_book(
    body: BookCreate,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[LibraryService, Depends(_library)],
) -> BookRead:
    """Create a book and add it to the library."""
    return await service.add_book(user.id, body)


@router.get("/{book_id}", response_model=BookRead)
async def get_book(
    book_id: UUID,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[LibraryService, Depends(_library)],
) -> BookRead:
    """Get one owned book."""
    return await service.get_book(user.id, book_id)


@router.put("/{book_id}", response_model=BookRead)
async def update_book(
    book_id: UUID,
    body: BookUpdate,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[LibraryService, Depends(_library)],
) -> BookRead:
    """Update an owned book."""
    return await service.update_book(user.id, book_id, body)


@router.post("/{book_id}/cover", response_model=BookRead)
async def upload_cover(
    book_id: UUID,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[LibraryService, Depends(_library)],
    file: Annotated[UploadFile, File()],
) -> BookRead:
    """Upload a cover image for an owned book."""
    raw = await file.read(_MAX_COVER_BYTES + 1)
    if len(raw) > _MAX_COVER_BYTES:
        raise HTTPException(status_code=400, detail="Cover too large (max 2MB)")
    content_type = file.content_type or "image/jpeg"
    return await service.upload_cover(user.id, book_id, raw, content_type)


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book_id: UUID,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[LibraryService, Depends(_library)],
) -> Response:
    """Remove a book from the library (soft-delete)."""
    await service.remove_book(user.id, book_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
