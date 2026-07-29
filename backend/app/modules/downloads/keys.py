"""Object-key helpers for download jobs."""

import re
from uuid import UUID

_MAX_TITLE_LENGTH = 80


def job_prefix(user_id: UUID, job_id: UUID) -> str:
    """MinIO key prefix for all objects belonging to a download job."""
    return f"downloads/{user_id}/{job_id}/"


def chapter_object_key(user_id: UUID, job_id: UUID, chapter_number: int) -> str:
    """MinIO key for a per-chapter MP3 within a download job."""
    return f"{job_prefix(user_id, job_id)}ch-{chapter_number}.mp3"


def combined_object_key(user_id: UUID, job_id: UUID) -> str:
    """MinIO key for the merged MP3."""
    return f"{job_prefix(user_id, job_id)}combined.mp3"


def download_filename(
    book_title: str,
    chapter_from: int,
    chapter_to: int,
    job_id: UUID,
) -> str:
    """Build a readable, filesystem-safe, unique combined MP3 filename."""
    title = re.sub(r"[^\w.-]+", "-", book_title, flags=re.UNICODE).strip(".-_")
    title = title[:_MAX_TITLE_LENGTH].rstrip(".-_") or "book"
    chapters = (
        f"chapter-{chapter_from}"
        if chapter_from == chapter_to
        else f"chapters-{chapter_from}-{chapter_to}"
    )
    return f"{title}-{chapters}-{str(job_id)[:8]}.mp3"
