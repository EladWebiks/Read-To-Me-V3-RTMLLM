"""Object-key helpers for download jobs."""

from uuid import UUID


def job_prefix(user_id: UUID, job_id: UUID) -> str:
    """MinIO key prefix for all objects belonging to a download job."""
    return f"downloads/{user_id}/{job_id}/"


def chapter_object_key(user_id: UUID, job_id: UUID, chapter_number: int) -> str:
    """MinIO key for a per-chapter MP3 within a download job."""
    return f"{job_prefix(user_id, job_id)}ch-{chapter_number}.mp3"


def combined_object_key(user_id: UUID, job_id: UUID) -> str:
    """MinIO key for the merged MP3."""
    return f"{job_prefix(user_id, job_id)}combined.mp3"
