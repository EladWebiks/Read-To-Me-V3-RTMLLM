"""Scraping business logic."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.fetcher import FetchError, fetch_html
from app.modules.books.schemas import BookCreate
from app.modules.library.service import LibraryService
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.service import QuotaService
from app.modules.scraping.exceptions import (
    PreviewError,
    ScrapeJobAlreadyCancelledError,
    ScrapeJobNotDeletableError,
    ScrapeJobNotFoundError,
    UnsupportedSourceError,
)
from app.modules.scraping.job_messages import public_scrape_error
from app.modules.scraping.models import ScrapingJob
from app.modules.scraping.registry import ALL_ALLOWED_HOSTS, get_adapter
from app.modules.scraping.repository import ScrapingRepository
from app.modules.scraping.schemas import (
    ScrapeJobAdminRead,
    ScrapeJobCreate,
    ScrapeJobRead,
    ScrapePreviewResponse,
)
from app.modules.scraping.types import BookMetadata
from app.modules.usage.kinds import UsageFact

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
        await self._enforce_quota(user_id)
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
            start_url=resolve_walk_start(adapter, data.url, meta.first_chapter_url),
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
        title = (meta.title or book_url or "Untitled").strip() or "Untitled"
        return _to_read(created, title)

    async def _enforce_quota(self, user_id: UUID) -> None:
        """Tier quota gate for new scrape work. Runs before any network fetch.

        Enforced at creation only: a running job may finish past the line
        (bounded by its own chapter range) — accepted, spec §3.5.
        """
        limits = await QuotaService(self._session).limits_for_user_id(user_id)
        if not limits.any_limited(QuotaKind.SCRAPE_CHAPTERS):
            return
        start, end = QuotaService.current_month_window(datetime.now(UTC))
        used = await self._repo.chapters_in_period(user_id, period_start=start, period_end=end)
        QuotaService.enforce(
            QuotaKind.SCRAPE_CHAPTERS, used, limits, resets_at=end, user_id=user_id
        )

    async def month_chapters_for_users(
        self,
        user_ids: list[UUID],
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> dict[UUID, int]:
        """Backoffice: per-user scraped chapters in a window."""
        return await self._repo.chapters_for_users(
            user_ids, period_start=period_start, period_end=period_end
        )

    async def get_job(self, user_id: UUID, job_id: UUID) -> ScrapeJobRead:
        job = await self._require(user_id, job_id)
        return await self._read_with_title(job)

    async def list_jobs(self, user_id: UUID) -> list[ScrapeJobRead]:
        await self._prune_jobs_for_missing_books(user_id)
        jobs = await self._repo.list_jobs_for_user(user_id)
        titles = await self._book_titles(jobs)
        return [_to_read(job, titles.get(job.book_id) if job.book_id else None) for job in jobs]

    async def cancel(self, user_id: UUID, job_id: UUID) -> ScrapeJobRead:
        job = await self._require(user_id, job_id)
        if job.status in _TERMINAL:
            raise ScrapeJobAlreadyCancelledError(str(job_id))
        job.status = "cancelled"
        job.message = "Cancel requested"
        await self._repo.flush()
        await self._session.commit()
        return await self._read_with_title(job)

    async def delete_job(self, user_id: UUID, job_id: UUID) -> None:
        """Remove a finished job from history (does not delete the book)."""
        job = await self._require(user_id, job_id)
        if job.status not in _TERMINAL:
            raise ScrapeJobNotDeletableError(str(job_id))
        await self._repo.delete_job(job)
        await self._session.commit()

    async def delete_jobs_for_book(self, book_id: UUID) -> None:
        """Drop scrape history when the library book is removed."""
        await self._repo.delete_jobs_for_book(book_id)

    async def _prune_jobs_for_missing_books(self, user_id: UUID) -> None:
        """Remove orphan jobs whose book was soft-deleted earlier."""
        from app.modules.books.service import BookService

        jobs = await self._repo.list_jobs_for_user(user_id)
        book_ids = [job.book_id for job in jobs if job.book_id is not None]
        if not book_ids:
            return
        alive = {book.id for book in await BookService(self._session).list_read(book_ids, {})}
        removed = False
        for job in jobs:
            if job.book_id is not None and job.book_id not in alive:
                await self._repo.delete_job(job)
                removed = True
        if removed:
            await self._session.commit()

    async def _require(self, user_id: UUID, job_id: UUID) -> ScrapingJob:
        job = await self._repo.get_job_for_user(job_id, user_id)
        if job is None:
            raise ScrapeJobNotFoundError(str(job_id))
        return job

    async def _read_with_title(self, job: ScrapingJob) -> ScrapeJobRead:
        titles = await self._book_titles([job])
        title = titles.get(job.book_id) if job.book_id is not None else None
        return _to_read(job, title)

    async def _book_titles(self, jobs: list[ScrapingJob]) -> dict[UUID, str]:
        from app.modules.books.service import BookService

        book_ids = [job.book_id for job in jobs if job.book_id is not None]
        if not book_ids:
            return {}
        books = await BookService(self._session).list_read(book_ids, {})
        return {book.id: book.title for book in books}

    # ── backoffice reads ─────────────────────────────────

    async def list_jobs_admin(
        self, *, status: str | None, limit: int, offset: int
    ) -> tuple[list[ScrapeJobAdminRead], int]:
        """Backoffice: all users' jobs with book titles; no pruning, raw errors."""
        jobs, total = await self._repo.list_jobs_admin(status=status, limit=limit, offset=offset)
        titles = await self._book_titles(jobs)
        items = [
            ScrapeJobAdminRead.model_validate(job).model_copy(
                update={"book_title": titles.get(job.book_id) if job.book_id else None}
            )
            for job in jobs
        ]
        return items, total

    async def daily_usage_facts(self, day: date) -> list[UsageFact]:
        """Usage-rollup facts for one UTC day (builder-facing, spec §6)."""
        return await self._repo.daily_usage_facts(day)


def _to_read(job: ScrapingJob, book_title: str | None = None) -> ScrapeJobRead:
    read = ScrapeJobRead.model_validate(job)
    return read.model_copy(
        update={
            "error": public_scrape_error(job.error),
            "book_title": book_title,
        }
    )


def resolve_walk_start(adapter: object, requested_url: str, first_chapter_url: str) -> str:
    """Walk from the first chapter when the request URL is a book page.

    Chapter URLs (where ``derive_book_url`` succeeds) are used as-is so mid-book
    starts still work. Book pages have no chapter body, so using them as
    ``start_url`` finishes with 0 chapters scraped.
    """
    if not first_chapter_url:
        return requested_url
    derived = adapter.derive_book_url(requested_url)  # type: ignore[attr-defined]
    if derived is None:
        return first_chapter_url
    return requested_url


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
