"""Unit tests for novelbin adapter — pure HTML parsing, no network."""

import pytest
from app.modules.scraping.adapters.novelbin import NovelbinAdapter

pytestmark = pytest.mark.unit


@pytest.fixture
def adapter() -> NovelbinAdapter:
    return NovelbinAdapter()


class TestMatches:
    def test_matches_novelbin_url(self, adapter: NovelbinAdapter) -> None:
        assert adapter.matches("https://novelbin.com/b/some-novel/chapter-1")

    def test_rejects_other_domain(self, adapter: NovelbinAdapter) -> None:
        assert not adapter.matches("https://example.com/book")


class TestDeriveBookUrl:
    def test_derives_from_chapter(self, adapter: NovelbinAdapter) -> None:
        url = adapter.derive_book_url("https://novelbin.com/b/my-novel/chapter-5")
        assert url == "https://novelbin.com/b/my-novel"

    def test_returns_none_for_unrecognised(self, adapter: NovelbinAdapter) -> None:
        assert adapter.derive_book_url("https://novelbin.com/other") is None


class TestParseBookPage:
    def test_extracts_metadata(self, adapter: NovelbinAdapter, novelbin_book_html: str) -> None:
        meta = adapter.parse_book_page(novelbin_book_html, "https://novelbin.com/b/test-novel")
        assert meta.title == "Test Novel Title"
        assert meta.author == "Test Author"
        assert "test-novel.jpg" in meta.cover_url
        assert "chapter-1" in meta.first_chapter_url


class TestParseChapterPage:
    def test_extracts_content(self, adapter: NovelbinAdapter, novelbin_chapter_html: str) -> None:
        data = adapter.parse_chapter_page(
            novelbin_chapter_html, "https://novelbin.com/b/test-novel/chapter-1"
        )
        assert "Chapter 1: The Beginning" in data.title
        assert "first paragraph" in data.content
        assert "second paragraph" in data.content
        assert data.next_url is not None
        assert "chapter-2" in data.next_url
        assert data.book_title == "Test Novel Title"
        assert data.book_author == "Test Author"
        assert data.chapter_number == 1
        assert not data.is_placeholder
