"""Per-user job progress events (Redis pub/sub → SSE)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

JobKind = Literal["scrape", "download", "import"]


class JobProgress(BaseModel):
    """Optional numeric progress for a job event."""

    done: int | None = None
    total: int | None = None


class JobEvent(BaseModel):
    """Compact job progress payload for SSE clients."""

    v: Literal[1] = 1
    kind: JobKind
    job_id: str
    user_id: UUID
    status: str
    progress: JobProgress | None = None
    book_id: UUID | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def user_jobs_channel(user_id: UUID) -> str:
    """Redis pub/sub channel for one user's job events."""
    return f"rtm:user:{user_id}:jobs"


async def publish_job_event(event: JobEvent) -> None:
    """Best-effort publish; never fails the calling job worker."""
    try:
        client = Redis.from_url(get_settings().redis.url, decode_responses=True)
        try:
            await client.publish(user_jobs_channel(event.user_id), event.model_dump_json())
        finally:
            await client.aclose()
    except Exception:
        logger.warning(
            "job event publish failed",
            extra={"kind": event.kind, "job_id": event.job_id},
            exc_info=True,
        )
