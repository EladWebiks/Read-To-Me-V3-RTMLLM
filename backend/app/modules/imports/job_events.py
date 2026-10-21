"""Publish EPUB import progress onto the per-user job-events channel."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.job_events import JobEvent, JobProgress, publish_job_event


async def publish_import_job(job: dict[str, Any], *, book_id: UUID | None = None) -> None:
    """Emit an import event from the in-memory EPUB job dict."""
    result = job.get("result")
    resolved_book = book_id
    if resolved_book is None and result is not None:
        raw = getattr(result, "book_id", None)
        if isinstance(raw, str) and raw:
            resolved_book = UUID(raw)
    total_raw = job.get("total_chapters")
    total = int(total_raw) if isinstance(total_raw, int) else None
    await publish_job_event(
        JobEvent(
            kind="import",
            job_id=str(job["job_id"]),
            user_id=UUID(str(job["user_id"])),
            status=str(job["status"]),
            progress=JobProgress(
                done=int(job.get("chapters_imported") or 0),
                total=total,
            ),
            book_id=resolved_book,
        )
    )
