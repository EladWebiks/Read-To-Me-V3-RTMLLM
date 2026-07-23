"""Unit tests for novelfull adapter — pure HTML parsing, no network."""

import pytest
from app.modules.scraping.adapters.novelfull import NovelfullAdapter

pytestmark = pytest.mark.unit


@pytest.fixture
def adapter() -> NovelfullAdapter:
    return NovelfullAdapter()


class TestMatches:
    def test_matches_novelfull_url(self, adapter: NovelfullAdapter) -> None:
        assert adapter.matches("https://novelfull.net/great-story/chapter-1")

    def test_rejects_other_domain(self, adapter: NovelfullAdapter) -> None:
        assert not adapter.matches("https://example.com/book")


class TestDeriveBookUrl:
    def test_derives_from_chapter(self, adapter: NovelfullAdapter) -> None:
        url = adapter.derive_book_url("https://novelfull.net/great-story/chapter-5")
        assert url == "https://novelfull.net/great-story.html"

    def test_returns_none_for_unrecognised(self, adapter: NovelfullAdapter) -> None:
        assert adapter.derive_book_url("https://novelfull.net/") is None


class TestParseBookPage:
    def test_extracts_metadata(self, adapter: NovelfullAdapter, novelfull_book_html: str) -> None:
        meta = adapter.parse_book_page(
            novelfull_book_html, "https://novelfull.net/great-story.html"
        )
        assert meta.title == "Great Story"
        assert meta.author == "Jane Doe"
        assert "great-story.jpg" in meta.cover_url


class TestParseChapterPage:
    def test_extracts_content(
        self, adapter: NovelfullAdapter, novelfull_chapter_html: str
    ) -> None:
        data = adapter.parse_chapter_page(
            novelfull_chapter_html, "https://novelfull.net/great-story/chapter-5"
        )
        assert "Chapter 5" in data.title
        assert "sun rose" in data.content
        assert data.chapter_number == 5
        assert data.next_url is not None
        assert "chapter-6" in data.next_url
        assert data.book_title == "Great Story"
        assert not data.is_placeholder
