"""Unit tests for scrape job start-URL resolution."""

from __future__ import annotations

from app.modules.scraping.adapters.novelfull import NovelfullAdapter
from app.modules.scraping.service import resolve_walk_start

_BOOK = "https://novelfull.net/martial-peak.html"
_CH1 = "https://novelfull.net/martial-peak/chapter-1-martial-peak.html"
_CH5 = "https://novelfull.net/martial-peak/chapter-5-something.html"


def test_book_page_resolves_to_first_chapter() -> None:
    assert resolve_walk_start(NovelfullAdapter(), _BOOK, _CH1) == _CH1


def test_chapter_url_kept() -> None:
    assert resolve_walk_start(NovelfullAdapter(), _CH5, _CH1) == _CH5


def test_missing_first_chapter_keeps_request() -> None:
    assert resolve_walk_start(NovelfullAdapter(), _BOOK, "") == _BOOK
