"""Reader HTTP routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.modules.reader.schemas import ProgressRead, ProgressUpsert
from app.modules.reader.service import ReaderService
from app.modules.users.schemas import UserRead

router = APIRouter(tags=["reader"])


def _reader(session: Annotated[AsyncSession, Depends(get_db)]) -> ReaderService:
    return ReaderService(session)


@router.get("/library/reading/continue", response_model=ProgressRead | None)
async def continue_reading(
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[ReaderService, Depends(_reader)],
) -> ProgressRead | None:
    """Return the most recently updated reading position, if any."""
    return await service.continue_reading(user.id)


@router.get("/library/books/{book_id}/progress", response_model=ProgressRead)
async def get_progress(
    book_id: UUID,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[ReaderService, Depends(_reader)],
) -> ProgressRead:
    """Get saved reading progress for a book."""
    return await service.get_progress(user.id, book_id)


@router.put("/library/books/{book_id}/progress", response_model=ProgressRead)
async def upsert_progress(
    book_id: UUID,
    body: ProgressUpsert,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[ReaderService, Depends(_reader)],
) -> ProgressRead:
    """Save reading progress for a book."""
    return await service.upsert_progress(user.id, book_id, body)
