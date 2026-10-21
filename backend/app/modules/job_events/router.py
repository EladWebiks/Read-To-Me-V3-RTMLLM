"""HTTP routes for job-events SSE."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.deps import get_current_user
from app.modules.job_events.service import iter_user_job_events
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _sse(events: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        events,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/events")
async def stream_job_events(
    user: Annotated[UserRead, Depends(get_current_user)],
) -> StreamingResponse:
    """Stream job progress events for the signed-in user."""

    async def _events() -> AsyncIterator[str]:
        async for frame in iter_user_job_events(user.id):
            yield frame

    return _sse(_events())
