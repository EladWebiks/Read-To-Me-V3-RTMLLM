"""Publish download job progress onto the per-user job-events channel."""

from __future__ import annotations

from app.core.job_events import JobEvent, JobProgress, publish_job_event
from app.modules.downloads.models import DownloadJob


async def publish_download_job(job: DownloadJob) -> None:
    """Emit a download event after a durable status/progress write."""
    await publish_job_event(
        JobEvent(
            kind="download",
            job_id=str(job.id),
            user_id=job.user_id,
            status=job.status,
            progress=JobProgress(done=job.ready_count, total=job.total_count or None),
            book_id=job.book_id,
        )
    )
