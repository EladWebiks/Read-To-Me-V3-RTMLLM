"""Unit tests for HITL confirmation presentation helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.modules.orchestration.hitl_pause import confirmation_event_data
from app.modules.scraping.exceptions import PreviewError
from app.modules.tools.base import ConfirmationPresentation
from app.modules.tools.definitions.create_audio_download import (
    CreateAudioDownloadInput,
    _audio_presentation,
)
from app.modules.tools.definitions.import_discovered_book import (
    ImportDiscoveredBookInput,
    _import_presentation,
)
from app.modules.tools.definitions.scrape_book_range import _scrape_presentation

pytestmark = pytest.mark.unit


def _ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.user_id = uuid4()
    ctx.session = MagicMock()
    return ctx


@pytest.mark.asyncio
async def test_scrape_presentation_uses_preview_title() -> None:
    preview = SimpleNamespace(title="Shadow Blade", source="novelfull")
    with patch("app.modules.tools.definitions.scrape_book_range.ScrapingService") as svc_cls:
        svc_cls.return_value.preview = AsyncMock(return_value=preview)
        result = await _scrape_presentation(_ctx(), "https://novelfull.net/book/x")
    assert result == ConfirmationPresentation(
        action="Scrape book",
        title="Shadow Blade",
        subtitle="novelfull",
    )


@pytest.mark.asyncio
async def test_scrape_presentation_falls_back_to_host() -> None:
    with patch("app.modules.tools.definitions.scrape_book_range.ScrapingService") as svc_cls:
        svc_cls.return_value.preview = AsyncMock(side_effect=PreviewError("boom"))
        result = await _scrape_presentation(_ctx(), "https://novelfull.net/book/x")
    assert result.action == "Scrape book"
    assert result.title is None
    assert result.subtitle == "novelfull.net"


@pytest.mark.asyncio
async def test_import_presentation_uses_discovered_title() -> None:
    book = SimpleNamespace(title="Starfall")
    src = SimpleNamespace(source="novelbin")
    data = ImportDiscoveredBookInput(discovered_book_id=uuid4())
    with patch("app.modules.tools.definitions.import_discovered_book.DiscoveryService") as svc_cls:
        svc_cls.return_value.pick_source = AsyncMock(return_value=(book, src))
        result = await _import_presentation(_ctx(), data)
    assert result == ConfirmationPresentation(
        action="Import book",
        title="Starfall",
        subtitle="novelbin",
    )


@pytest.mark.asyncio
async def test_audio_presentation_includes_title_and_range() -> None:
    book = SimpleNamespace(title="Echoes")
    data = CreateAudioDownloadInput(
        book_id=uuid4(),
        chapter_from=2,
        chapter_to=5,
    )
    with patch("app.modules.tools.definitions.create_audio_download.LibraryService") as svc_cls:
        svc_cls.return_value.get_book = AsyncMock(return_value=book)
        result = await _audio_presentation(_ctx(), data)
    assert result == ConfirmationPresentation(
        action="Create audio",
        title="Echoes",
        subtitle="Chapters 2-5",
    )


def test_confirmation_event_data_includes_presentation_fields() -> None:
    row = SimpleNamespace(
        id=uuid4(),
        input={"url": "https://example.com"},
        output={
            "summary": "Scrape book: Foo",
            "action": "Scrape book",
            "title": "Foo",
            "subtitle": "novelfull",
            "form": {"fields": []},
        },
    )
    tool = SimpleNamespace(
        name="scrape_book_range", risk_level=SimpleNamespace(value="confirmation_required")
    )
    payload = confirmation_event_data(row, tool)  # type: ignore[arg-type]
    assert payload["action"] == "Scrape book"
    assert payload["title"] == "Foo"
    assert payload["subtitle"] == "novelfull"
