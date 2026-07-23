"""Download HTTP routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.modules.downloads.schemas import (
    DownloadCleanResult,
    DownloadCreate,
    DownloadJobRead,
    DownloadUrlRead,
)
from app.modules.downloads.service import DownloadService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/downloads", tags=["downloads"])


def _downloads(session: Annotated[AsyncSession, Depends(get_db)]) -> DownloadService:
    return DownloadService(session)


@router.post("", response_model=DownloadJobRead, status_code=201)
async def create_download(
    body: DownloadCreate,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[DownloadService, Depends(_downloads)],
) -> DownloadJobRead:
    """Enqueue a chapter-range MP3 download job."""
    return await service.create(user.id, body)


@router.get("", response_model=list[DownloadJobRead])
async def list_downloads(
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[DownloadService, Depends(_downloads)],
    book_id: Annotated[UUID | None, Query()] = None,
) -> list[DownloadJobRead]:
    """List recent non-expired download/listen jobs."""
    return await service.list_jobs(user.id, book_id)


@router.delete("", response_model=DownloadCleanResult)
async def clean_downloads(
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[DownloadService, Depends(_downloads)],
    book_id: Annotated[UUID, Query()],
) -> DownloadCleanResult:
    """Delete all jobs (and objects) for a book."""
    return await service.clean_book(user.id, book_id)


@router.get("/{job_id}", response_model=DownloadJobRead)
async def get_download(
    job_id: UUID,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[DownloadService, Depends(_downloads)],
) -> DownloadJobRead:
    """Get download job status."""
    return await service.get(user.id, job_id)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_download(
    job_id: UUID,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[DownloadService, Depends(_downloads)],
) -> Response:
    """Delete one job and its stored MP3s."""
    await service.delete(user.id, job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{job_id}/url", response_model=DownloadUrlRead)
async def get_download_url(
    job_id: UUID,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[DownloadService, Depends(_downloads)],
) -> DownloadUrlRead:
    """Return a signed MinIO URL for a completed job."""
    return await service.signed_url(user.id, job_id)


@router.get("/{job_id}/chapters/{chapter_number}/url", response_model=DownloadUrlRead)
async def get_chapter_download_url(
    job_id: UUID,
    chapter_number: int,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[DownloadService, Depends(_downloads)],
) -> DownloadUrlRead:
    """Return a signed URL for one chapter once it is synthesized."""
    return await service.chapter_signed_url(user.id, job_id, chapter_number)
