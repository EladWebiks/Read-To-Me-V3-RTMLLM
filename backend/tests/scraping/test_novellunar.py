"""Unit tests for novellunar adapter — pure HTML parsing, no network."""

import pytest
from app.modules.scraping.adapters.novellunar import NovellunarAdapter

pytestmark = pytest.mark.unit


@pytest.fixture
def adapter() -> NovellunarAdapter:
    return NovellunarAdapter()


class TestMatches:
    def test_matches_novellunar_url(self, adapter: NovellunarAdapter) -> None:
        assert adapter.matches("https://novellunar.com/novel/space-voyage/chapter/7")

    def test_rejects_other_domain(self, adapter: NovellunarAdapter) -> None:
        assert not adapter.matches("https://example.com/novel/test")


class TestDeriveBookUrl:
    def test_derives_from_chapter(self, adapter: NovellunarAdapter) -> None:
        url = adapter.derive_book_url("https://novellunar.com/novel/space-voyage/chapter/7")
        assert url == "https://novellunar.com/novel/space-voyage"

    def test_returns_none_for_unrecognised(self, adapter: NovellunarAdapter) -> None:
        assert adapter.derive_book_url("https://novellunar.com/") is None


class TestParseBookPage:
    def test_extracts_metadata(
        self, adapter: NovellunarAdapter, novellunar_book_html: str
    ) -> None:
        meta = adapter.parse_book_page(
            novellunar_book_html, "https://novellunar.com/novel/space-voyage"
        )
        assert meta.title == "Space Voyage"
        assert meta.author == "Alice Wonder"
        assert "space-voyage.jpg" in meta.cover_url


class TestParseChapterPage:
    def test_extracts_content(
        self, adapter: NovellunarAdapter, novellunar_chapter_html: str
    ) -> None:
        data = adapter.parse_chapter_page(
            novellunar_chapter_html,
            "https://novellunar.com/novel/space-voyage/chapter/7",
        )
        assert "Chapter 7" in data.title
        assert "hyperspace" in data.content
        assert data.chapter_number == 7
        assert data.next_url is not None
        assert "chapter/8" in data.next_url
        assert data.book_title == "Space Voyage"
        assert not data.is_placeholder
