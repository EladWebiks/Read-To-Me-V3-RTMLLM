"""Download job business logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.storage import delete_prefix, presigned_get
from app.modules.audio.providers import default_voice
from app.modules.chapters.service import ChapterService
from app.modules.downloads.exceptions import (
    DownloadJobNotFoundError,
    DownloadNotReadyError,
    InvalidChapterRangeError,
)
from app.modules.downloads.keys import chapter_object_key, job_prefix
from app.modules.downloads.models import DownloadJob
from app.modules.downloads.repository import DownloadRepository
from app.modules.downloads.schemas import (
    DownloadCleanResult,
    DownloadCreate,
    DownloadJobRead,
    DownloadUrlRead,
)
from app.modules.library.service import LibraryService


class DownloadService:
    """Owns MP3 download job creation and signed URLs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = DownloadRepository(session)
        self._library = LibraryService(session)
        self._chapters = ChapterService(session)

    async def create(self, user_id: UUID, data: DownloadCreate) -> DownloadJobRead:
        """Create a pending job after ownership + range checks."""
        if data.chapter_to < data.chapter_from:
            raise InvalidChapterRangeError("chapter_to < chapter_from")
        await self._library.assert_access(user_id, data.book_id)
        chapters = await self._chapters.list_summaries(data.book_id)
        selected = [
            chapter
            for chapter in chapters
            if data.chapter_from <= chapter.chapter_number <= data.chapter_to
        ]
        if not selected:
            raise InvalidChapterRangeError("no chapters in range")
        voice = data.voice or default_voice(data.provider)
        job = DownloadJob(
            user_id=user_id,
            book_id=data.book_id,
            chapter_from=data.chapter_from,
            chapter_to=data.chapter_to,
            provider=data.provider,
            voice=voice,
            rate=str(data.rate),
            status="pending",
            ready_count=0,
            total_count=len(selected),
            expires_at=_ttl_deadline(),
        )
        created = await self._repo.add(job)
        await self._session.commit()
        await self._enqueue(created.id)
        return DownloadJobRead.model_validate(created)

    async def get(self, user_id: UUID, job_id: UUID) -> DownloadJobRead:
        job = await self._require(user_id, job_id)
        return DownloadJobRead.model_validate(job)

    async def list_jobs(
        self,
        user_id: UUID,
        book_id: UUID | None = None,
    ) -> list[DownloadJobRead]:
        """List non-expired jobs; purge expired ones for this scope first."""
        if book_id is not None:
            await self._library.assert_access(user_id, book_id)
        await self._purge_expired(user_id, book_id)
        jobs = await self._repo.list_for_user(user_id, book_id)
        return [DownloadJobRead.model_validate(job) for job in jobs]

    async def delete(self, user_id: UUID, job_id: UUID) -> None:
        """Delete one job and its MinIO objects."""
        job = await self._require(user_id, job_id)
        await self._delete_assets(job)
        await self._repo.delete(job)
        await self._session.commit()

    async def clean_book(self, user_id: UUID, book_id: UUID) -> DownloadCleanResult:
        """Delete all jobs for a book (user-owned)."""
        await self._library.assert_access(user_id, book_id)
        jobs = await self._repo.list_for_user(
            user_id,
            book_id,
            limit=100,
            include_expired=True,
        )
        for job in jobs:
            await self._delete_assets(job)
            await self._repo.delete(job)
        await self._session.commit()
        return DownloadCleanResult(deleted=len(jobs))

    async def signed_url(self, user_id: UUID, job_id: UUID) -> DownloadUrlRead:
        job = await self._require(user_id, job_id)
        if job.status != "complete" or not job.object_key:
            raise DownloadNotReadyError(str(job_id))
        return await self._presign(job.object_key)

    async def chapter_signed_url(
        self,
        user_id: UUID,
        job_id: UUID,
        chapter_number: int,
    ) -> DownloadUrlRead:
        """Signed URL for a chapter MP3 once the worker has uploaded it."""
        job = await self._require(user_id, job_id)
        if not await self._chapter_ready(job, chapter_number):
            raise DownloadNotReadyError(str(job_id))
        key = chapter_object_key(job.user_id, job.id, chapter_number)
        return await self._presign(key)

    async def _purge_expired(self, user_id: UUID, book_id: UUID | None) -> None:
        expired = await self._repo.list_expired(user_id, book_id)
        for job in expired:
            await self._delete_assets(job)
            await self._repo.delete(job)
        if expired:
            await self._session.commit()

    async def _delete_assets(self, job: DownloadJob) -> None:
        await delete_prefix(job_prefix(job.user_id, job.id))

    async def _presign(self, object_key: str) -> DownloadUrlRead:
        settings = get_settings()
        expires = settings.signed_url_expires_seconds
        url = await presigned_get(object_key, expires)
        return DownloadUrlRead(
            url=url,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires),
        )

    async def _chapter_ready(self, job: DownloadJob, chapter_number: int) -> bool:
        chapters = await self._chapters.list_summaries(job.book_id)
        selected = sorted(
            chapter.chapter_number
            for chapter in chapters
            if job.chapter_from <= chapter.chapter_number <= job.chapter_to
        )
        if chapter_number not in selected:
            return False
        return selected.index(chapter_number) < job.ready_count

    async def _require(self, user_id: UUID, job_id: UUID) -> DownloadJob:
        job = await self._repo.get_for_user(job_id, user_id)
        if job is None:
            raise DownloadJobNotFoundError(str(job_id))
        return job

    async def _enqueue(self, job_id: UUID) -> None:
        from app.jobs.queue import enqueue_download_job

        await enqueue_download_job(job_id)


def _ttl_deadline() -> datetime:
    hours = get_settings().download_job_ttl_hours
    return datetime.now(UTC) + timedelta(hours=hours)
