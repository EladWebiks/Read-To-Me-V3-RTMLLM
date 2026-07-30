"""Scraping job worker task — runs inside arq."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.fetcher import FetchError, fetch_bytes, fetch_html
from app.core.storage import put_bytes
from app.modules.books.service import BookService
from app.modules.chapters.service import ChapterService
from app.modules.scraping.adapters.base import ScrapeAdapter
from app.modules.scraping.cleaning import clean_content
from app.modules.scraping.job_messages import public_scrape_error
from app.modules.scraping.models import ScrapingJob, ScrapingJobItem
from app.modules.scraping.registry import get_adapter
from app.modules.scraping.repository import ScrapingRepository
from app.modules.scraping.types import ChapterData

logger = logging.getLogger(__name__)


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
    finally:
        await engine.dispose()


async def _process(session: AsyncSession, job_id: UUID) -> None:
    repo = ScrapingRepository(session)
    job = await repo.get_job(job_id)
    if job is None or job.status == "cancelled":
        return
    job.status = "running"
    job.message = "Starting…"
    await repo.flush()
    await session.commit()
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


async def _walk(session: AsyncSession, repo: ScrapingRepository, job: ScrapingJob) -> None:
    adapter = get_adapter(job.start_url)
    source = await repo.get_source(job.source_id)
    hosts = _build_hosts(source)
    await _maybe_cover(session, job, adapter, hosts)
    url: str | None = job.start_url
    delay = source.rate_limit_seconds if source else get_settings().scrape_delay_seconds
    while url:
        await session.refresh(job)
        if job.status == "cancelled":
            job.message = f"Cancelled after {job.chapters_done} chapter(s)."
            return
        if _reached_limit(job):
            return
        url = await _one(session, repo, job, adapter, hosts, url)
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


async def _one(
    session: AsyncSession,
    repo: ScrapingRepository,
    job: ScrapingJob,
    adapter: ScrapeAdapter,
    hosts: set[str],
    url: str,
) -> str | None:
    try:
        html = await fetch_html(url, hosts)
    except FetchError as exc:
        job.error = str(exc)[:2000]
        job.message = "No more published content."
        return None
    data: ChapterData = adapter.parse_chapter_page(html, url)
    if data.is_placeholder or not data.content.strip():
        job.message = "No more published content."
        return None
    number = _number(data, job)
    if job.chapter_to is not None and number > job.chapter_to:
        return None
    if job.chapter_from is not None and number < job.chapter_from:
        return data.next_url
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
    return data.next_url


def _number(data: ChapterData, job: ScrapingJob) -> int:
    if data.chapter_number is not None:
        return data.chapter_number
    match = re.search(r"(?:Chapter|C)[\s\-]*(\d+)", data.title, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return job.chapters_done + (job.chapter_from or 1)


async def _maybe_cover(
    session: AsyncSession, job: ScrapingJob, adapter: ScrapeAdapter, hosts: set[str]
) -> None:
    if job.book_id is None:
        return
    book = await BookService(session).get(job.book_id)
    if book.cover_object_key:
        return
    book_url = adapter.derive_book_url(job.start_url)
    if not book_url:
        return
    try:
        await _download_cover(session, job.book_id, adapter, book_url, hosts)
        await session.commit()
    except Exception:
        logger.warning("Cover download failed for job %s", job.id, exc_info=True)


async def _download_cover(
    session: AsyncSession,
    book_id: UUID,
    adapter: ScrapeAdapter,
    book_url: str,
    hosts: set[str],
) -> None:
    from urllib.parse import urlparse

    html = await fetch_html(book_url, hosts)
    meta = adapter.parse_book_page(html, book_url)
    if not meta.cover_url:
        return
    cover_hosts = set(hosts)
    cover_host = (urlparse(meta.cover_url).hostname or "").lower()
    if cover_host:
        cover_hosts.add(cover_host)
    raw = await fetch_bytes(meta.cover_url, cover_hosts)
    key = f"covers/{book_id}.jpg"
    await put_bytes(key, raw, "image/jpeg")
    await BookService(session).set_cover_key(book_id, key)
