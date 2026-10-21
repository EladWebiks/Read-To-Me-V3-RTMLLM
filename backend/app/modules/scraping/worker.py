"""Scraping job worker task — runs inside arq."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.fetcher import FetchError, FetchSession, looks_like_bot_block
from app.core.storage import put_bytes
from app.modules.books.service import BookService
from app.modules.chapters.service import ChapterService
from app.modules.scraping.adapters.base import ScrapeAdapter
from app.modules.scraping.cleaning import clean_content
from app.modules.scraping.job_events import publish_scrape_job
from app.modules.scraping.job_messages import public_scrape_error
from app.modules.scraping.models import ScrapingJob, ScrapingJobItem
from app.modules.scraping.registry import get_adapter
from app.modules.scraping.repository import ScrapingRepository
from app.modules.scraping.types import ChapterData
from app.modules.scraping.walk_start import chapter_number_from_url

logger = logging.getLogger(__name__)

_MAX_CHAPTER_FETCH_ATTEMPTS = 4
_RETRY_BACKOFF_SECONDS = (2.0, 4.0, 8.0)


@dataclass(frozen=True, slots=True)
class _WalkCtx:
    adapter: ScrapeAdapter
    hosts: set[str]
    http: FetchSession


async def run_scrape_job(_ctx: object, job_id: str) -> None:
    """Top-level arq entry point for scraping."""
    from app.core.orm import import_all_models

    import_all_models()
    settings = get_settings()
    engine = create_async_engine(settings.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with factory() as session:
            await _process(session, UUID(job_id))
            await session.commit()
    except asyncio.CancelledError:
        # arq job_timeout cancels the task; without this the row stays "running".
        await _fail_aborted(factory, UUID(job_id))
        raise
    finally:
        await engine.dispose()


async def _fail_aborted(
    factory: async_sessionmaker[AsyncSession],
    job_id: UUID,
) -> None:
    try:
        async with factory() as session:
            repo = ScrapingRepository(session)
            job = await repo.get_job(job_id)
            if job is None or job.status not in {"pending", "running"}:
                return
            job.status = "failed"
            job.error = "Scrape timed out or was interrupted before finishing."
            job.message = "Failed"
            await repo.flush()
            await session.commit()
            await publish_scrape_job(job)
    except Exception:
        logger.exception("Could not mark aborted scrape job %s as failed", job_id)


async def _process(session: AsyncSession, job_id: UUID) -> None:
    repo = ScrapingRepository(session)
    job = await repo.get_job(job_id)
    if job is None or job.status == "cancelled":
        return
    job.status = "running"
    job.message = "Starting…"
    await repo.flush()
    await session.commit()
    await publish_scrape_job(job)
    try:
        await _walk(session, repo, job)
        if job.status != "cancelled":
            job.status = "complete"
            job.message = f"Finished. {job.chapters_done} chapter(s) scraped."
    except Exception as exc:
        logger.exception("Scrape job %s failed", job_id)
        job.status = "failed"
        job.error = public_scrape_error(str(exc)) or "Scrape failed"
        job.message = "Failed"
    await repo.flush()
    await publish_scrape_job(job)


async def _walk(session: AsyncSession, repo: ScrapingRepository, job: ScrapingJob) -> None:
    adapter = get_adapter(job.start_url)
    source = await repo.get_source(job.source_id)
    delay = source.rate_limit_seconds if source else get_settings().scrape.delay_seconds
    async with FetchSession() as http:
        ctx = _WalkCtx(adapter=adapter, hosts=_build_hosts(source), http=http)
        await _maybe_cover(session, job, ctx)
        url: str | None = job.start_url
        while url:
            await session.refresh(job)
            if job.status == "cancelled":
                job.message = f"Cancelled after {job.chapters_done} chapter(s)."
                return
            if _reached_limit(job):
                return
            url = await _one(session, repo, job, ctx, url)
            if url:
                await asyncio.sleep(delay)


def _build_hosts(source: object | None) -> set[str]:
    """Build allowlist from source domains."""
    from app.modules.scraping.registry import ALL_ALLOWED_HOSTS

    if source is None:
        return ALL_ALLOWED_HOSTS
    domains: list[str] = getattr(source, "base_domains", []) or []
    hosts = {d.lower() for d in domains}
    for d in list(hosts):
        hosts.add(f"www.{d}")
        hosts.add(f"img.{d}")
        hosts.add(f"cdn.{d}")
    hosts.update(ALL_ALLOWED_HOSTS)
    return hosts


def _reached_limit(job: ScrapingJob) -> bool:
    return job.max_chapters is not None and job.chapters_done >= job.max_chapters


async def _fetch_chapter_html(http: FetchSession, url: str, hosts: set[str]) -> str:
    """Fetch with retries — NovelFire/CF often drops connections or serves interstitials."""
    last_error = "Chapter page blocked or empty"
    for attempt in range(_MAX_CHAPTER_FETCH_ATTEMPTS):
        try:
            html = await http.fetch_html(url, hosts)
        except FetchError as exc:
            last_error = str(exc)
            await http.reset()
        else:
            if not looks_like_bot_block(html):
                return html
            last_error = "Chapter page blocked or empty"
        if attempt + 1 >= _MAX_CHAPTER_FETCH_ATTEMPTS:
            break
        await asyncio.sleep(_RETRY_BACKOFF_SECONDS[min(attempt, len(_RETRY_BACKOFF_SECONDS) - 1)])
    raise FetchError(f"{last_error} after {_MAX_CHAPTER_FETCH_ATTEMPTS} attempts")


async def _one(
    session: AsyncSession,
    repo: ScrapingRepository,
    job: ScrapingJob,
    ctx: _WalkCtx,
    url: str,
) -> str | None:
    html = await _fetch_chapter_html(ctx.http, url, ctx.hosts)
    data: ChapterData = ctx.adapter.parse_chapter_page(html, url)
    if data.is_placeholder or not data.content.strip():
        if data.next_url:
            raise FetchError("Chapter body empty but a next-chapter link was present")
        if job.chapters_done == 0 and chapter_number_from_url(url) is None:
            raise FetchError(
                "Start URL is not a chapter page (empty body). "
                "Re-queue with a chapter URL or fix start resolution."
            )
        job.message = "No more published content."
        return None
    number = _number(data, job)
    if job.chapter_to is not None and number > job.chapter_to:
        return None
    if job.chapter_from is not None and number < job.chapter_from:
        # Mid-book jobs must resolve the start URL up front — never walk 1..N.
        raise RuntimeError(
            f"Start URL is chapter {number}, but this job starts at "
            f"chapter {job.chapter_from}. Re-queue after fixing start resolution."
        )
    return await _save_chapter(session, repo, job, data, url, number)


async def _save_chapter(
    session: AsyncSession,
    repo: ScrapingRepository,
    job: ScrapingJob,
    data: ChapterData,
    url: str,
    number: int,
) -> str | None:
    assert job.book_id is not None
    body = clean_content(data.content)
    title = data.title or f"Chapter {number}"
    await ChapterService(session).upsert_by_number(job.book_id, number, title, body)
    digest = hashlib.sha256(body.encode()).hexdigest()
    await repo.add_item(
        ScrapingJobItem(
            job_id=job.id,
            chapter_number=number,
            url=url,
            status="ok",
            attempts=1,
            content_hash=digest,
        )
    )
    job.chapters_done += 1
    job.message = f"Scraped Chapter {number}"
    await repo.flush()
    await session.commit()
    await publish_scrape_job(job)
    return data.next_url


def _number(data: ChapterData, job: ScrapingJob) -> int:
    if data.chapter_number is not None:
        return data.chapter_number
    match = re.search(r"(?:Chapter|C)[\s\-]*(\d+)", data.title, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return job.chapters_done + (job.chapter_from or 1)


async def _maybe_cover(session: AsyncSession, job: ScrapingJob, ctx: _WalkCtx) -> None:
    if job.book_id is None:
        return
    book = await BookService(session).get(job.book_id)
    if book.cover_object_key:
        return
    book_url = ctx.adapter.derive_book_url(job.start_url)
    if not book_url:
        return
    try:
        await _download_cover(session, job.book_id, ctx, book_url)
        await session.commit()
    except Exception:
        logger.warning("Cover download failed for job %s", job.id, exc_info=True)


async def _download_cover(
    session: AsyncSession,
    book_id: UUID,
    ctx: _WalkCtx,
    book_url: str,
) -> None:
    from urllib.parse import urlparse

    html = await ctx.http.fetch_html(book_url, ctx.hosts)
    meta = ctx.adapter.parse_book_page(html, book_url)
    if not meta.cover_url:
        return
    cover_hosts = set(ctx.hosts)
    cover_host = (urlparse(meta.cover_url).hostname or "").lower()
    if cover_host:
        cover_hosts.add(cover_host)
    raw = await ctx.http.fetch_bytes(meta.cover_url, cover_hosts)
    key = f"covers/{book_id}.jpg"
    await put_bytes(key, raw, "image/jpeg")
    await BookService(session).set_cover_key(book_id, key)
