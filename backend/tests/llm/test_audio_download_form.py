"""Audio range confirmation form validation."""

from __future__ import annotations

from uuid import uuid4

import pytest
from app.modules.tools.definitions.create_audio_download import CreateAudioDownloadTool
from app.modules.tools.exceptions import ToolValidationError
from app.modules.tools.hitl import build_form_payload, merge_confirmed_args


@pytest.mark.unit
def test_audio_download_form_exposes_provider_choices_and_bounds() -> None:
    tool = CreateAudioDownloadTool()
    proposed = {
        "book_id": str(uuid4()),
        "chapter_from": 2,
        "chapter_to": 8,
        "provider": "edge",
        "voice": None,
        "rate": 1.0,
    }

    form = build_form_payload(tool, proposed)
    assert form is not None
    fields = {field["name"]: field for field in form["fields"]}
    assert fields["provider"]["options"] == [
        {"value": "edge", "label": "edge"},
        {"value": "sapi", "label": "sapi"},
    ]
    assert fields["rate"]["min"] == 0.5
    assert fields["rate"]["max"] == 2.0


@pytest.mark.unit
def test_audio_download_form_marks_model_provided_values() -> None:
    tool = CreateAudioDownloadTool()
    proposed = {
        "book_id": str(uuid4()),
        "chapter_from": 2,
        "chapter_to": 8,
        "provider": "edge",
        "voice": None,
        "rate": 1.0,
    }

    form = build_form_payload(tool, proposed, {"chapter_from", "chapter_to"})
    assert form is not None
    fields = {field["name"]: field for field in form["fields"]}
    assert fields["chapter_from"]["provided"] is True
    assert fields["provider"]["provided"] is False
    assert fields["voice"]["provided"] is False
    assert fields["rate"]["provided"] is False


@pytest.mark.unit
def test_audio_download_confirmed_values_are_revalidated() -> None:
    tool = CreateAudioDownloadTool()
    proposed = {
        "book_id": str(uuid4()),
        "chapter_from": 2,
        "chapter_to": 8,
        "provider": "edge",
        "voice": None,
        "rate": 1.0,
    }

    merged = merge_confirmed_args(
        tool,
        proposed,
        {"chapter_from": 3, "chapter_to": 9, "provider": "sapi", "rate": 1.5},
    )
    assert merged["chapter_from"] == 3
    assert merged["provider"] == "sapi"
    with pytest.raises(ToolValidationError):
        merge_confirmed_args(tool, proposed, {"rate": 9})
