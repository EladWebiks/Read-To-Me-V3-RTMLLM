"""Publish scrape job progress onto the per-user job-events channel."""

from __future__ import annotations

from app.core.job_events import JobEvent, JobProgress, publish_job_event
from app.modules.scraping.models import ScrapingJob


async def publish_scrape_job(job: ScrapingJob) -> None:
    """Emit a scrape event after a durable status/progress write."""
    total = job.max_chapters
    if total is None and job.chapter_from is not None and job.chapter_to is not None:
        total = max(0, job.chapter_to - job.chapter_from + 1)
    await publish_job_event(
        JobEvent(
            kind="scrape",
            job_id=str(job.id),
            user_id=job.user_id,
            status=job.status,
            progress=JobProgress(done=job.chapters_done, total=total),
            book_id=job.book_id,
        )
    )
