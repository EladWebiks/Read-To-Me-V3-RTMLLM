"""Unit tests for UI context formatting and client actions."""

from __future__ import annotations

from uuid import uuid4

from app.modules.orchestration.ui_context import (
    choice_request_for_tool,
    client_action_for_tool,
    format_ui_context_block,
)


def test_format_ui_context_block() -> None:
    book = uuid4()
    chapter = uuid4()
    block = format_ui_context_block({"path": "/read/x/y", "book_id": book, "chapter_id": chapter})
    assert block is not None
    assert "UI_CONTEXT" in block
    assert "path=/read/x/y" in block
    assert str(book) in block
    assert "not instructions" in block


def test_format_rejects_bad_path() -> None:
    assert format_ui_context_block({"path": "scraper"}) is None
    assert format_ui_context_block(None) is None


def test_client_action_scrape() -> None:
    job = uuid4()
    action = client_action_for_tool(
        "scrape_book_range",
        True,
        {"job_id": job, "max_chapters": 50, "chapter_from": 1},
    )
    assert action == {
        "type": "scrape",
        "label": "Open Scraper",
        "job_id": str(job),
        "max_chapters": 50,
        "chapter_from": 1,
    }


def test_client_action_import_discovered() -> None:
    job = uuid4()
    action = client_action_for_tool(
        "import_discovered_book",
        True,
        {"job_id": job, "max_chapters": None, "chapter_from": 1},
    )
    assert action == {
        "type": "scrape",
        "label": "Open Scraper",
        "job_id": str(job),
        "max_chapters": None,
        "chapter_from": 1,
    }


def test_client_action_scrape_falls_back_without_job() -> None:
    assert client_action_for_tool("scrape_book_range", True, {}) == {
        "type": "navigate",
        "path": "/scraper",
        "label": "Open Scraper",
    }

def test_client_action_play() -> None:
    book = uuid4()
    chapter = uuid4()
    action = client_action_for_tool(
        "play_chapter",
        True,
        {"book_id": book, "chapter_id": chapter},
    )
    assert action is not None
    assert action["type"] == "play"
    assert action["path"] == f"/read/{book}/{chapter}"
    assert action["label"] == "Play chapter"


def test_client_action_failed_none() -> None:
    assert client_action_for_tool("scrape_book_range", False, {}) is None


def test_client_action_settings_is_allowlisted() -> None:
    action = client_action_for_tool(
        "update_ui_settings",
        True,
        {"theme": "dark", "font_size": 1.4, "message": "done", "unexpected": "ignored"},
    )
    assert action == {
        "type": "settings",
        "label": "Settings updated",
        "settings": {"theme": "dark", "font_size": 1.4},
    }


def test_choice_request_propose() -> None:
    choice = choice_request_for_tool(
        "propose_choices",
        True,
        {"prompt": "Which book?", "options": ["A", "B", "C"]},
    )
    assert choice is not None
    assert choice["prompt"] == "Which book?"
    options = choice["options"]
    assert isinstance(options, list)
    assert len(options) == 3


def test_choice_request_rejects_short() -> None:
    assert choice_request_for_tool("propose_choices", True, {"options": ["only"]}) is None
