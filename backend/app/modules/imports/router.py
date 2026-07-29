"""EPUB import HTTP routes (chunked upload + job poll/cancel)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_current_user
from app.modules.imports.schemas import (
    EpubChunkAccepted,
    EpubImportStart,
    EpubUploadComplete,
    EpubUploadPrepare,
    EpubUploadPrepared,
    ImportProgress,
)
from app.modules.imports.service import ImportService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/import", tags=["import"])


def _imports() -> ImportService:
    return ImportService()


@router.post("/epub/uploads", response_model=EpubUploadPrepared)
def prepare_epub_upload(
    body: EpubUploadPrepare,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[ImportService, Depends(_imports)],
) -> EpubUploadPrepared:
    """Start a chunked upload for one EPUB file."""
    return service.prepare_upload(user.id, body)


@router.put(
    "/epub/uploads/{upload_id}/chunks/{index}",
    response_model=EpubChunkAccepted,
)
async def put_epub_chunk(
    upload_id: str,
    index: int,
    request: Request,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[ImportService, Depends(_imports)],
) -> EpubChunkAccepted:
    """Upload one binary chunk (raw body)."""
    data = await request.body()
    return service.write_chunk(user.id, upload_id, index, data)


@router.post(
    "/epub/uploads/{upload_id}/complete",
    response_model=EpubUploadComplete,
)
def complete_epub_upload(
    upload_id: str,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[ImportService, Depends(_imports)],
) -> EpubUploadComplete:
    """Mark a chunked upload finished."""
    return service.complete_upload(user.id, upload_id)


@router.post("/epub/start", response_model=ImportProgress)
async def start_epub_import(
    body: EpubImportStart,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[ImportService, Depends(_imports)],
) -> ImportProgress:
    """Start import from completed chunked uploads."""
    return await service.start_from_uploads(user.id, body)


@router.get("/{job_id}", response_model=ImportProgress)
def import_status(
    job_id: str,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[ImportService, Depends(_imports)],
) -> ImportProgress:
    """Check EPUB import progress."""
    return service.get(user.id, job_id)


@router.post("/{job_id}/cancel", response_model=ImportProgress)
def cancel_import(
    job_id: str,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[ImportService, Depends(_imports)],
) -> ImportProgress:
    """Cancel a running EPUB import."""
    return service.cancel(user.id, job_id)
