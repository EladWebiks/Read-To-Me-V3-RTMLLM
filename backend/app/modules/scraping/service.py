"""Scraping business logic."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.fetcher import FetchError, fetch_html
from app.modules.books.schemas import BookCreate
from app.modules.library.service import LibraryService
from app.modules.scraping.exceptions import (
    PreviewError,
    ScrapeJobAlreadyCancelledError,
    ScrapeJobNotFoundError,
    UnsupportedSourceError,
)
from app.modules.scraping.models import ScrapingJob
from app.modules.scraping.registry import ALL_ALLOWED_HOSTS, get_adapter
from app.modules.scraping.repository import ScrapingRepository
from app.modules.scraping.schemas import (
    ScrapeJobCreate,
    ScrapeJobRead,
    ScrapePreviewResponse,
)
from app.modules.scraping.types import BookMetadata

_TERMINAL = {"complete", "failed", "cancelled"}


class ScrapingService:
    """Owns scraping preview, job creation, and status."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ScrapingRepository(session)
        self._library = LibraryService(session)

    async def preview(self, url: str) -> ScrapePreviewResponse:
        """Fetch and parse a book/chapter URL into a preview."""
        adapter = get_adapter(url)
        source = await self._repo.get_source_by_name(adapter.name)
        if source is None or not source.enabled:
            raise UnsupportedSourceError(adapter.name)
        book_url, meta = await _fetch_book_meta(adapter, url)
        return ScrapePreviewResponse(
            source=adapter.name,
            book_url=book_url,
            title=meta.title or "Untitled",
            author=meta.author,
            cover_url=meta.cover_url,
            first_chapter_url=meta.first_chapter_url or url,
        )

    async def create_job(self, user_id: UUID, data: ScrapeJobCreate) -> ScrapeJobRead:
        """Create a pending scrape job and enqueue it."""
        adapter = get_adapter(data.url)
        source = await self._repo.get_source_by_name(adapter.name)
        if source is None or not source.enabled:
            raise UnsupportedSourceError(adapter.name)
        meta_url = data.book_url or data.url
        book_url, meta = await _fetch_book_meta(adapter, meta_url)
        book = await self._library.add_book(
            user_id,
            BookCreate(title=meta.title or book_url, author=meta.author),
        )
        if meta.cover_url:
            await _store_cover_from_url(self._session, book.id, meta.cover_url)
        start_chapter = (
            data.starting_chapter if data.starting_chapter is not None else data.chapter_from
        )
        job = ScrapingJob(
            user_id=user_id,
            source_id=source.id,
            book_id=book.id,
            start_url=data.url,
            mode=data.mode,
            chapter_from=start_chapter,
            chapter_to=data.chapter_to,
            max_chapters=data.max_chapters,
            status="pending",
            message="Queued…",
        )
        created = await self._repo.add_job(job)
        await self._session.commit()
        await _enqueue(created.id)
        return ScrapeJobRead.model_validate(created)

    async def get_job(self, user_id: UUID, job_id: UUID) -> ScrapeJobRead:
        job = await self._require(user_id, job_id)
        return ScrapeJobRead.model_validate(job)

    async def list_jobs(self, user_id: UUID) -> list[ScrapeJobRead]:
        jobs = await self._repo.list_jobs_for_user(user_id)
        return [ScrapeJobRead.model_validate(job) for job in jobs]

    async def cancel(self, user_id: UUID, job_id: UUID) -> ScrapeJobRead:
        job = await self._require(user_id, job_id)
        if job.status in _TERMINAL:
            raise ScrapeJobAlreadyCancelledError(str(job_id))
        job.status = "cancelled"
        job.message = "Cancel requested"
        await self._repo.flush()
        await self._session.commit()
        return ScrapeJobRead.model_validate(job)

    async def _require(self, user_id: UUID, job_id: UUID) -> ScrapingJob:
        job = await self._repo.get_job_for_user(job_id, user_id)
        if job is None:
            raise ScrapeJobNotFoundError(str(job_id))
        return job


async def _fetch_book_meta(adapter: object, url: str) -> tuple[str, BookMetadata]:
    book_url: str | None = adapter.derive_book_url(url)  # type: ignore[attr-defined]
    target = book_url or url
    try:
        html = await fetch_html(target, ALL_ALLOWED_HOSTS)
    except FetchError as exc:
        raise PreviewError(str(exc)) from exc
    meta: BookMetadata = adapter.parse_book_page(html, target)  # type: ignore[attr-defined]
    return target, meta


async def _store_cover_from_url(session: AsyncSession, book_id: UUID, cover_url: str) -> None:
    """Best-effort cover download into MinIO; never fails the scrape job."""
    import logging
    from urllib.parse import urlparse

    from app.core.fetcher import fetch_bytes
    from app.core.storage import put_bytes
    from app.modules.books.service import BookService

    try:
        hosts = set(ALL_ALLOWED_HOSTS)
        host = (urlparse(cover_url).hostname or "").lower()
        if host:
            hosts.add(host)
        raw = await fetch_bytes(cover_url, hosts)
        key = f"covers/{book_id}.jpg"
        await put_bytes(key, raw, "image/jpeg")
        await BookService(session).set_cover_key(book_id, key)
    except Exception:
        logging.getLogger(__name__).warning(
            "Cover download failed for book %s", book_id, exc_info=True
        )


async def _enqueue(job_id: UUID) -> None:
    from app.jobs.queue import enqueue_scrape_job

    await enqueue_scrape_job(job_id)
