"""EPUB import orchestration (validate upload, start/poll/cancel jobs)."""

from __future__ import annotations

from uuid import UUID

from app.modules.imports import chunk_store
from app.modules.imports.exceptions import ImportJobNotFoundError, InvalidEpubUploadError
from app.modules.imports.jobs import ImportRequest, cancel_job, get_job, start_job, to_progress
from app.modules.imports.schemas import (
    EpubChunkAccepted,
    EpubImportStart,
    EpubUploadComplete,
    EpubUploadPrepare,
    EpubUploadPrepared,
    ImportProgress,
)

_MAX_FILES = 20
_MAX_BYTES_PER_FILE = 80 * 1024 * 1024


def max_bytes_per_file() -> int:
    """Per-file upload cap (also used for Starlette multipart part size)."""
    return _MAX_BYTES_PER_FILE


class ImportService:
    """Owns EPUB import job lifecycle for a user."""

    def prepare_upload(self, user_id: UUID, body: EpubUploadPrepare) -> EpubUploadPrepared:
        """Reserve staging space for a chunked EPUB upload."""
        session = chunk_store.prepare_upload(user_id, body.filename, body.size)
        return EpubUploadPrepared(
            upload_id=session.upload_id,
            filename=session.filename,
            size=session.size,
            chunk_size=chunk_store.chunk_size_bytes(),
            total_chunks=session.total_chunks,
        )

    def write_chunk(
        self,
        user_id: UUID,
        upload_id: str,
        index: int,
        data: bytes,
    ) -> EpubChunkAccepted:
        """Accept one chunk of a staged upload."""
        session = chunk_store.write_chunk(user_id, upload_id, index, data)
        return EpubChunkAccepted(
            upload_id=session.upload_id,
            index=index,
            received_chunks=len(session.received),
            total_chunks=session.total_chunks,
        )

    def complete_upload(self, user_id: UUID, upload_id: str) -> EpubUploadComplete:
        """Finalize a staged upload after all chunks arrived."""
        session = chunk_store.complete_upload(user_id, upload_id)
        return EpubUploadComplete(
            upload_id=session.upload_id,
            filename=session.filename,
            size=session.size,
        )

    async def start_from_uploads(self, user_id: UUID, body: EpubImportStart) -> ImportProgress:
        """Assemble completed uploads and start the import job."""
        payloads = chunk_store.take_payloads(user_id, body.upload_ids)
        return await self.start(
            user_id,
            payloads,
            title=body.title,
            author=body.author,
            starting_chapter=body.starting_chapter,
        )

    async def start(
        self,
        user_id: UUID,
        file_payloads: list[tuple[str, bytes]],
        *,
        title: str | None,
        author: str | None,
        starting_chapter: int,
    ) -> ImportProgress:
        """Validate payloads and start a background import job."""
        self._validate(file_payloads, starting_chapter)
        req = ImportRequest(
            user_id=user_id,
            title=title,
            author=author,
            starting_chapter=starting_chapter,
        )
        return await start_job(req, file_payloads)

    def get(self, user_id: UUID, job_id: str) -> ImportProgress:
        """Poll job progress."""
        job = get_job(job_id, user_id)
        if job is None:
            raise ImportJobNotFoundError(job_id)
        return to_progress(job)

    def cancel(self, user_id: UUID, job_id: str) -> ImportProgress:
        """Request cancel of a running import."""
        job = cancel_job(job_id, user_id)
        if job is None:
            raise ImportJobNotFoundError(job_id)
        return to_progress(job)

    def _validate(
        self,
        file_payloads: list[tuple[str, bytes]],
        starting_chapter: int,
    ) -> None:
        if not file_payloads:
            raise InvalidEpubUploadError("At least one EPUB file is required")
        if len(file_payloads) > _MAX_FILES:
            raise InvalidEpubUploadError(f"Too many files (max {_MAX_FILES})")
        if starting_chapter < 1:
            raise InvalidEpubUploadError("starting_chapter must be >= 1")
        for name, data in file_payloads:
            self._validate_file(name, data)

    def _validate_file(self, name: str, data: bytes) -> None:
        if not name.lower().endswith(".epub"):
            raise InvalidEpubUploadError(f"Invalid file type: {name} (expected .epub)")
        if not data:
            raise InvalidEpubUploadError(f"Empty file: {name}")
        if len(data) > _MAX_BYTES_PER_FILE:
            raise InvalidEpubUploadError(f"File too large: {name} (max 80MB)")
