"""Unit tests for job-events channel helpers and SSE framing."""

from __future__ import annotations

from uuid import uuid4

import pytest
from app.core.job_events import JobEvent, JobProgress, user_jobs_channel
from app.modules.job_events.service import encode_heartbeat, encode_sse


@pytest.mark.unit
def test_user_jobs_channel_is_namespaced() -> None:
    user_id = uuid4()
    assert user_jobs_channel(user_id) == f"rtm:user:{user_id}:jobs"


@pytest.mark.unit
def test_job_event_json_roundtrip() -> None:
    user_id = uuid4()
    event = JobEvent(
        kind="scrape",
        job_id=str(uuid4()),
        user_id=user_id,
        status="running",
        progress=JobProgress(done=3, total=10),
        book_id=uuid4(),
    )
    parsed = JobEvent.model_validate_json(event.model_dump_json())
    assert parsed.kind == "scrape"
    assert parsed.progress is not None
    assert parsed.progress.done == 3
    assert parsed.user_id == user_id


@pytest.mark.unit
def test_sse_framing() -> None:
    assert encode_sse("ready", "{}") == "event: ready\ndata: {}\n\n"
    assert encode_heartbeat() == ": heartbeat\n\n"
