"""Unit tests for chunked EPUB staging."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from app.modules.imports import chunk_store
from app.modules.imports.exceptions import InvalidEpubUploadError
from app.modules.imports.jobs import ImportRequest, start_job


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_job_schedules_on_running_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: sync FastAPI handlers had no loop → create_task 500."""

    async def _noop(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr("app.modules.imports.jobs._run_import", _noop)
    progress = await start_job(
        ImportRequest(user_id=uuid4(), title=None, author=None, starting_chapter=1),
        [("part.epub", b"PK\x03\x04")],
    )
    assert progress.status == "running"
    await asyncio.sleep(0)


@pytest.mark.unit
def test_chunked_upload_roundtrip() -> None:
    user_id = uuid4()
    payload = b"abcdefghij" * 1000  # 10_000 bytes
    session = chunk_store.prepare_upload(user_id, "part.epub", len(payload))
    chunk = chunk_store.chunk_size_bytes()
    for index in range(session.total_chunks):
        start = index * chunk
        end = min(start + chunk, len(payload))
        chunk_store.write_chunk(user_id, session.upload_id, index, payload[start:end])
    chunk_store.complete_upload(user_id, session.upload_id)
    files = chunk_store.take_payloads(user_id, [session.upload_id])
    assert files == [("part.epub", payload)]


@pytest.mark.unit
def test_chunk_size_mismatch_rejected() -> None:
    user_id = uuid4()
    session = chunk_store.prepare_upload(user_id, "x.epub", 1000)
    with pytest.raises(InvalidEpubUploadError, match="size mismatch"):
        chunk_store.write_chunk(user_id, session.upload_id, 0, b"short")
