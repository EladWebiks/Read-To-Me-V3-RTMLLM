"""In-memory EPUB import jobs (v2 parity: poll + cancel)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.books.schemas import BookCreate
from app.modules.chapters.service import ChapterService
from app.modules.imports.epub import ParsedEpub, parse_epub
from app.modules.imports.job_events import publish_import_job
from app.modules.imports.repository import EpubImportRepository
from app.modules.imports.schemas import (
    EpubImportFileSummary,
    EpubImportResult,
    ImportProgress,
)
from app.modules.library.service import LibraryService
from app.modules.scraping.cleaning import clean_content

logger = logging.getLogger(__name__)

_jobs: dict[str, dict[str, Any]] = {}
_tasks: set[asyncio.Task[None]] = set()


@dataclass(frozen=True)
class ImportRequest:
    """User overrides for an EPUB import."""

    user_id: UUID
    title: str | None
    author: str | None
    starting_chapter: int
    record_id: UUID | None = None


def get_job(job_id: str, user_id: UUID) -> dict[str, Any] | None:
    """Return job dict if it exists and belongs to the user."""
    job = _jobs.get(job_id)
    if job is None or job.get("user_id") != str(user_id):
        return None
    return job


def cancel_job(job_id: str, user_id: UUID) -> dict[str, Any] | None:
    """Request cancel; returns job snapshot or None."""
    job = get_job(job_id, user_id)
    if job is None:
        return None
    if job["status"] == "running":
        job["cancelled"] = True
    return job


def to_progress(job: dict[str, Any]) -> ImportProgress:
    """Map internal job dict → API schema (omit user_id / cancelled)."""
    return ImportProgress(
        job_id=job["job_id"],
        status=job["status"],
        chapters_imported=job["chapters_imported"],
        total_chapters=job["total_chapters"],
        files_total=job["files_total"],
        files_parsed=job["files_parsed"],
        current_file=job["current_file"],
        book_title=job["book_title"],
        message=job["message"],
        result=job.get("result"),
    )


async def start_job(
    req: ImportRequest,
    file_payloads: list[tuple[str, bytes]],
) -> ImportProgress:
    """Create job row and schedule background import on the running event loop."""
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {
        "job_id": job_id,
        "user_id": str(req.user_id),
        "status": "running",
        "chapters_imported": 0,
        "total_chapters": None,
        "files_total": len(file_payloads),
        "files_parsed": 0,
        "current_file": "",
        "book_title": "",
        "message": "Starting import…",
        "cancelled": False,
        "result": None,
    }
    # Must be called from an async route — sync FastAPI handlers run in a
    # threadpool with no running loop, which makes create_task raise.
    task = asyncio.create_task(_run_import(job_id, req, file_payloads))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    await publish_import_job(_jobs[job_id])
    return to_progress(_jobs[job_id])


async def _run_import(
    job_id: str,
    req: ImportRequest,
    file_payloads: list[tuple[str, bytes]],
) -> None:
    job = _jobs[job_id]
    settings = get_settings()
    engine = create_async_engine(settings.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        await _import_with_session(factory, job, req, file_payloads)
    except Exception as exc:
        logger.exception("EPUB import %s failed", job_id)
        job["status"] = "failed"
        job["message"] = str(exc)
    finally:
        # Single terminal point: the job dict is "completed", "cancelled" or
        # "failed" by now, whichever branch above got us here.
        await _finish_record(factory, req.record_id, job)
        await publish_import_job(job)
        await engine.dispose()


_TERMINAL_STATUSES = frozenset({"completed", "cancelled", "failed"})


async def _finish_record(
    factory: async_sessionmaker[AsyncSession],
    record_id: UUID | None,
    job: dict[str, Any],
) -> None:
    """Stamp the durable epub_imports row; progress stays in-memory (v2 parity)."""
    if record_id is None:
        return
    status = job["status"]
    if status not in _TERMINAL_STATUSES:
        status = "failed"
    result = job.get("result")
    book_id = UUID(result.book_id) if result is not None else None
    async with factory() as session:
        await EpubImportRepository(session).set_terminal(
            record_id,
            status=status,
            chapter_count=int(job["chapters_imported"] or 0),
            book_id=book_id,
        )
        await session.commit()


async def _import_with_session(
    factory: async_sessionmaker[AsyncSession],
    job: dict[str, Any],
    req: ImportRequest,
    file_payloads: list[tuple[str, bytes]],
) -> None:
    parsed_files = await _parse_all(job, file_payloads)
    if parsed_files is None:
        return
    async with factory() as session:
        await _persist_book(session, job, req, parsed_files)
        await session.commit()


async def _parse_all(
    job: dict[str, Any],
    file_payloads: list[tuple[str, bytes]],
) -> list[tuple[str, ParsedEpub]] | None:
    parsed_files: list[tuple[str, ParsedEpub]] = []
    for i, (filename, data) in enumerate(file_payloads):
        if job.get("cancelled"):
            job["status"] = "cancelled"
            job["message"] = "Cancelled while parsing."
            return None
        job["current_file"] = filename
        job["files_parsed"] = i + 1  # current file index (1-based) while parsing
        job["message"] = f"Parsing {filename} ({i + 1}/{len(file_payloads)})…"
        await publish_import_job(job)
        parsed = await asyncio.to_thread(parse_epub, data)
        parsed_files.append((filename, parsed))
    job["total_chapters"] = sum(len(p.chapters) for _, p in parsed_files)
    return parsed_files


async def _persist_book(
    session: AsyncSession,
    job: dict[str, Any],
    req: ImportRequest,
    parsed_files: list[tuple[str, ParsedEpub]],
) -> None:
    first = parsed_files[0][1]
    book_title = (req.title or "").strip() or first.title or parsed_files[0][0]
    book_author = (req.author or "").strip() or first.author or ""
    job["book_title"] = book_title
    library = LibraryService(session)
    book = await library.add_book(
        req.user_id,
        BookCreate(
            title=book_title,
            author=book_author,
            language=first.language or "en",
            starting_chapter_number=req.starting_chapter,
        ),
    )
    if first.cover:
        await library.upload_cover(req.user_id, book.id, first.cover, "image/jpeg")
    await _write_chapters(session, job, book.id, parsed_files, req, book_author)


async def _write_chapters(
    session: AsyncSession,
    job: dict[str, Any],
    book_id: UUID,
    parsed_files: list[tuple[str, ParsedEpub]],
    req: ImportRequest,
    book_author: str,
) -> None:
    chapters = ChapterService(session)
    chapter_num = req.starting_chapter
    total_imported = 0
    total_chapters = int(job["total_chapters"] or 0)
    file_summaries: list[EpubImportFileSummary] = []
    for filename, parsed in parsed_files:
        count = 0
        for chapter in parsed.chapters:
            if job.get("cancelled"):
                _mark_cancelled(job, total_imported, total_chapters)
                return
            cleaned = clean_content(chapter.text)
            await chapters.upsert_by_number(book_id, chapter_num, chapter.title, cleaned)
            chapter_num += 1
            count += 1
            total_imported += 1
            await _touch_progress_and_publish(job, total_imported, total_chapters)
            await session.commit()
        file_summaries.append(EpubImportFileSummary(name=filename, chapters=count))
    _mark_completed(job, book_id, book_author, total_imported, file_summaries, req)


def _mark_cancelled(job: dict[str, Any], done: int, total: int) -> None:
    job["status"] = "cancelled"
    job["message"] = f"Cancelled after {done} of {total}."


def _touch_progress(job: dict[str, Any], done: int, total: int) -> None:
    job["chapters_imported"] = done
    job["message"] = f"Importing chapter {done} of {total}…"


async def _touch_progress_and_publish(job: dict[str, Any], done: int, total: int) -> None:
    _touch_progress(job, done, total)
    await publish_import_job(job)


def _mark_completed(
    job: dict[str, Any],
    book_id: UUID,
    book_author: str,
    total_imported: int,
    file_summaries: list[EpubImportFileSummary],
    req: ImportRequest,
) -> None:
    job["status"] = "completed"
    job["message"] = f"Finished. {total_imported} chapter(s) imported."
    job["result"] = EpubImportResult(
        book_id=str(book_id),
        book_title=job["book_title"],
        author=book_author,
        chapters_imported=total_imported,
        files=file_summaries,
        starting_chapter=req.starting_chapter,
    )
