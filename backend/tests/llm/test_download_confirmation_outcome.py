"""Deterministic post-confirmation download UI outcome."""

from __future__ import annotations

import pytest
from app.modules.orchestration.service import _confirmed_terminal_text
from app.modules.orchestration.ui_context import client_action_for_tool


@pytest.mark.unit
def test_confirmed_audio_download_emits_tracking_action_and_terminal_copy() -> None:
    data: dict[str, object] = {
        "job_id": "job-1",
        "book_id": "book-1",
        "chapter_from": 1,
        "chapter_to": 5,
        "message": "Queued audio download for chapters 1-5.",
    }
    result: dict[str, object] = {"ok": True, "data": data}

    action = client_action_for_tool("create_audio_download", True, data)
    assert action == {
        "type": "download",
        "label": "Audio download",
        "job_id": "job-1",
        "book_id": "book-1",
        "chapter_from": 1,
        "chapter_to": 5,
    }
    assert _confirmed_terminal_text("create_audio_download", result) == (
        "Queued audio download for chapters 1-5. "
        "Progress will appear here, and the MP3 will download when ready."
    )


@pytest.mark.unit
def test_failed_audio_download_does_not_claim_it_was_queued() -> None:
    result: dict[str, object] = {"ok": False, "error": "queue unavailable"}

    assert _confirmed_terminal_text("create_audio_download", result) is None
