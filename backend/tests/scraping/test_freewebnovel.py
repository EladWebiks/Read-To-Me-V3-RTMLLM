"""Unit tests for freewebnovel adapter — pure HTML parsing, no network."""

import pytest
from app.modules.scraping.adapters.freewebnovel import FreewebnovelAdapter

pytestmark = pytest.mark.unit


@pytest.fixture
def adapter() -> FreewebnovelAdapter:
    return FreewebnovelAdapter()


class TestMatches:
    def test_matches_freewebnovel_url(self, adapter: FreewebnovelAdapter) -> None:
        assert adapter.matches("https://freewebnovel.com/novel/epic-tale/chapter-1")

    def test_rejects_other_domain(self, adapter: FreewebnovelAdapter) -> None:
        assert not adapter.matches("https://example.com/novel/test")


class TestDeriveBookUrl:
    def test_derives_from_chapter(self, adapter: FreewebnovelAdapter) -> None:
        url = adapter.derive_book_url("https://freewebnovel.com/novel/epic-tale/chapter-3")
        assert url == "https://freewebnovel.com/novel/epic-tale"

    def test_returns_none_for_unrecognised(self, adapter: FreewebnovelAdapter) -> None:
        assert adapter.derive_book_url("https://freewebnovel.com/") is None


class TestParseBookPage:
    def test_extracts_metadata(
        self, adapter: FreewebnovelAdapter, freewebnovel_book_html: str
    ) -> None:
        meta = adapter.parse_book_page(
            freewebnovel_book_html, "https://freewebnovel.com/novel/epic-tale"
        )
        assert meta.title == "Epic Tale"
        assert meta.author == "John Smith"
        assert "epic-tale.jpg" in meta.cover_url


class TestParseChapterPage:
    def test_extracts_content(
        self, adapter: FreewebnovelAdapter, freewebnovel_chapter_html: str
    ) -> None:
        data = adapter.parse_chapter_page(
            freewebnovel_chapter_html,
            "https://freewebnovel.com/novel/epic-tale/chapter-3",
        )
        assert "Chapter 3" in data.title
        assert "dark forest" in data.content
        assert data.chapter_number == 3
        assert data.next_url is not None
        assert "chapter-4" in data.next_url
        assert data.book_title == "Epic Tale"
        assert not data.is_placeholder
