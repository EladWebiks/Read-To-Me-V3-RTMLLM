"""Unit tests for ranobes adapter — pure HTML parsing, no network."""

import pytest
from app.modules.scraping.adapters.ranobes import (
    RanobesAdapter,
    extract_novel_id,
    find_chapter_link_in_toc,
    toc_page_for_chapter,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def adapter() -> RanobesAdapter:
    return RanobesAdapter()


class TestMatches:
    def test_matches_top(self, adapter: RanobesAdapter) -> None:
        assert adapter.matches("https://ranobes.top/novels/250389-cultivation-chat.html")

    def test_matches_net(self, adapter: RanobesAdapter) -> None:
        assert adapter.matches("https://ranobes.net/chapters/250389/")

    def test_rejects_other(self, adapter: RanobesAdapter) -> None:
        assert not adapter.matches("https://example.com/novels/1")


class TestIds:
    def test_extract_from_novels_path(self) -> None:
        assert extract_novel_id("https://ranobes.top/novels/250389-foo.html") == "250389"

    def test_extract_from_chapter_path(self) -> None:
        url = "https://ranobes.top/cultivation-chat-250389/376700.html"
        assert extract_novel_id(url) == "250389"

    def test_toc_page_math(self) -> None:
        assert toc_page_for_chapter(1, 3163) == 127
        assert toc_page_for_chapter(3163, 3163) == 1


class TestDeriveBookUrl:
    def test_derives_from_chapter(self, adapter: RanobesAdapter) -> None:
        url = adapter.derive_book_url("https://ranobes.top/cultivation-chat-250389/376700.html")
        assert url is not None
        assert "/novels/250389-" in url


class TestParseBookPage:
    def test_extracts_metadata(self, adapter: RanobesAdapter, ranobes_book_html: str) -> None:
        meta = adapter.parse_book_page(
            ranobes_book_html,
            "https://ranobes.top/novels/250389-cultivation-chat.html",
        )
        assert meta.title == "Cultivation Chat"
        assert "Legend" in meta.author
        assert "cover.jpg" in meta.cover_url
        assert meta.first_chapter_url.endswith("/chapters/250389/first")


class TestParseChapterPage:
    def test_extracts_content(self, adapter: RanobesAdapter, ranobes_chapter_html: str) -> None:
        data = adapter.parse_chapter_page(
            ranobes_chapter_html,
            "https://ranobes.top/cultivation-chat-250389/376702.html",
        )
        assert "Chapter 3" in data.title
        assert "pill recipe" in data.content.lower()
        assert data.chapter_number == 3
        assert data.next_url is not None
        assert data.book_title == "Cultivation Chat"
        assert not data.is_placeholder


class TestTocFind:
    def test_finds_from_data_script(self) -> None:
        html = (
            "<script>window.__DATA__ = "
            '{"chapters":[{"title":"Chapter 42: Mid","link":"https://ranobes.top/x/42.html"}],'
            '"pages_count":1,"count_all":42};</script>'
        )
        assert find_chapter_link_in_toc(html, 42) == "https://ranobes.top/x/42.html"
