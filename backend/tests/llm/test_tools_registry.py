"""Unit tests for B3.0 tools + registry."""

from __future__ import annotations

from uuid import uuid4

import pytest
from app.modules.tools.base import Mode
from app.modules.tools.catalog import build_default_registry
from app.modules.tools.definitions.get_book_details import GetBookDetailsInput
from app.modules.tools.definitions.search_user_books import SearchUserBooksInput
from app.modules.tools.exceptions import ToolNotFoundError
from pydantic import ValidationError


@pytest.mark.unit
def test_default_registry_exposes_read_only_specs() -> None:
    registry = build_default_registry()
    specs = registry.list_specs(Mode.INTERNAL_ONLY)
    names = {s.name for s in specs}
    assert names == {
        "search_user_books",
        "get_book_details",
        "search_library_content",
        "get_reading_progress",
        "get_recently_read_chapters",
        "list_available_chapters",
        "get_chapter_content",
        "get_download_status",
        "play_chapter",
        "resume_book",
        "create_chapter_download",
        "propose_choices",
    }
    assert "scrape_book_range" not in names


@pytest.mark.unit
def test_scrape_visible_in_external_mode() -> None:
    registry = build_default_registry()
    names = {s.name for s in registry.list_specs(Mode.EXTERNAL_ALLOWED)}
    assert "scrape_book_range" in names


@pytest.mark.unit
def test_registry_resolve_unknown() -> None:
    registry = build_default_registry()
    with pytest.raises(ToolNotFoundError):
        registry.resolve("nope")


@pytest.mark.unit
def test_search_input_accepts_empty_query() -> None:
    inp = SearchUserBooksInput.model_validate({})
    assert inp.query is None


@pytest.mark.unit
def test_get_book_details_requires_uuid() -> None:
    with pytest.raises(ValidationError):
        GetBookDetailsInput.model_validate({"book_id": "not-a-uuid"})
    GetBookDetailsInput.model_validate({"book_id": str(uuid4())})
