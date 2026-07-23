"""Novelbin adapter contract tests (offline fixtures)."""

from pathlib import Path

import pytest
from app.modules.scraping.adapters.novelbin import NovelbinAdapter

FIXTURES = Path(__file__).parent / "fixtures" / "scraping" / "novelbin"


@pytest.mark.unit
def test_novelbin_parse_chapter() -> None:
    html = (FIXTURES / "chapter.html").read_text(encoding="utf-8")
    data = NovelbinAdapter().parse_chapter_page(html, "https://novelbin.com/b/foo/chapter-1")
    assert "first paragraph of chapter one" in data.content.lower()
    assert data.next_url is not None
    assert "chapter-2" in data.next_url


@pytest.mark.unit
def test_novelbin_parse_book() -> None:
    html = (FIXTURES / "book.html").read_text(encoding="utf-8")
    meta = NovelbinAdapter().parse_book_page(html, "https://novelbin.com/b/foo")
    assert meta.title == "Test Novel Title"
    assert meta.author == "Test Author"
