"""Unit tests for scribblehub adapter — pure HTML parsing, no network."""

import pytest
from app.modules.scraping.adapters.scribblehub import (
    ScribblehubAdapter,
    extract_mypostid,
    find_chapter_in_toc,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def adapter() -> ScribblehubAdapter:
    return ScribblehubAdapter()


class TestMatches:
    def test_matches_series(self, adapter: ScribblehubAdapter) -> None:
        assert adapter.matches("https://www.scribblehub.com/series/52931/rupegia/")

    def test_rejects_other(self, adapter: ScribblehubAdapter) -> None:
        assert not adapter.matches("https://example.com/series/1/x/")


class TestDeriveBookUrl:
    def test_derives_from_chapter(self, adapter: ScribblehubAdapter) -> None:
        url = adapter.derive_book_url(
            "https://www.scribblehub.com/read/52931-rupegia/chapter/52941/"
        )
        assert url == "https://www.scribblehub.com/series/52931/rupegia/"


class TestParseBookPage:
    def test_extracts_metadata(
        self, adapter: ScribblehubAdapter, scribblehub_book_html: str
    ) -> None:
        meta = adapter.parse_book_page(
            scribblehub_book_html,
            "https://www.scribblehub.com/series/52931/rupegia/",
        )
        assert meta.title == "Rupegia"
        assert meta.author == "AuthorName"
        assert "rupegia.jpg" in meta.cover_url
        assert "/chapter/52941/" in meta.first_chapter_url
        assert extract_mypostid(scribblehub_book_html) == "52931"


class TestParseChapterPage:
    def test_extracts_content(
        self, adapter: ScribblehubAdapter, scribblehub_chapter_html: str
    ) -> None:
        data = adapter.parse_chapter_page(
            scribblehub_chapter_html,
            "https://www.scribblehub.com/read/52931-rupegia/chapter/52941/",
        )
        assert "Chapter 1" in data.title
        assert "Rupegia" in data.content
        assert data.chapter_number == 1
        assert data.next_url is not None
        assert "/chapter/53000/" in data.next_url
        assert not data.is_placeholder


class TestToc:
    def test_picks_nth_chapter(self, scribblehub_book_html: str) -> None:
        base = "https://www.scribblehub.com/series/52931/rupegia/"
        first = find_chapter_in_toc(scribblehub_book_html, base, 1)
        third = find_chapter_in_toc(scribblehub_book_html, base, 3)
        assert first is not None
        assert first.endswith("/52941/")
        assert third is not None
        assert third.endswith("/53051/")
