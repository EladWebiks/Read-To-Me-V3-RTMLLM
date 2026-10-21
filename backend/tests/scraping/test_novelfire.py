"""Unit tests for novelfire adapter — pure HTML parsing, no network."""

import pytest
from app.modules.scraping.adapters.novelfire import NovelfireAdapter, canonicalize_novelfire_url

pytestmark = pytest.mark.unit


@pytest.fixture
def adapter() -> NovelfireAdapter:
    return NovelfireAdapter()


class TestCanonicalize:
    def test_mirror_novel_path(self) -> None:
        raw = "https://novelphoenix.com/novel/hell-difficulty-tutorial/chapter-1"
        assert canonicalize_novelfire_url(raw) == (
            "https://novelfire.net/book/hell-difficulty-tutorial/chapter-1"
        )

    def test_book_page(self) -> None:
        assert canonicalize_novelfire_url("https://novelfire.net/book/epic-fire") == (
            "https://novelfire.net/book/epic-fire"
        )


class TestMatches:
    def test_matches_novelfire_url(self, adapter: NovelfireAdapter) -> None:
        assert adapter.matches("https://novelfire.net/book/epic-fire/chapter-1")

    def test_matches_mirror_domain(self, adapter: NovelfireAdapter) -> None:
        assert adapter.matches("https://novelphoenix.com/novel/epic-fire/chapter-1")

    def test_rejects_other_domain(self, adapter: NovelfireAdapter) -> None:
        assert not adapter.matches("https://example.com/book/test")


class TestDeriveBookUrl:
    def test_derives_from_chapter(self, adapter: NovelfireAdapter) -> None:
        url = adapter.derive_book_url("https://novelfire.net/book/epic-fire/chapter-3")
        assert url == "https://novelfire.net/book/epic-fire"

    def test_derives_from_mirror_chapter(self, adapter: NovelfireAdapter) -> None:
        url = adapter.derive_book_url(
            "https://novelphoenix.com/novel/epic-fire/chapter-3",
        )
        assert url == "https://novelfire.net/book/epic-fire"

    def test_returns_none_for_unrecognised(self, adapter: NovelfireAdapter) -> None:
        assert adapter.derive_book_url("https://novelfire.net/") is None


class TestParseBookPage:
    def test_extracts_metadata(self, adapter: NovelfireAdapter, novelfire_book_html: str) -> None:
        meta = adapter.parse_book_page(novelfire_book_html, "https://novelfire.net/book/epic-fire")
        assert meta.title == "Epic Fire"
        assert meta.author == "Jane Doe"
        assert "epic-fire.jpg" in meta.cover_url
        assert meta.first_chapter_url == "https://novelfire.net/book/epic-fire/chapter-1"

    def test_canonicalizes_mirror_read_now_link(
        self, adapter: NovelfireAdapter, novelfire_book_html: str
    ) -> None:
        html = novelfire_book_html.replace(
            'href="/book/epic-fire/chapter-1"',
            'href="https://novelphoenix.com/novel/epic-fire/chapter-1"',
        )
        meta = adapter.parse_book_page(html, "https://novelfire.net/book/epic-fire")
        assert meta.first_chapter_url == "https://novelfire.net/book/epic-fire/chapter-1"


class TestParseChapterPage:
    def test_extracts_content(
        self, adapter: NovelfireAdapter, novelfire_chapter_html: str
    ) -> None:
        data = adapter.parse_chapter_page(
            novelfire_chapter_html,
            "https://novelfire.net/book/epic-fire/chapter-3",
        )
        assert "Chapter 3" in data.title
        assert "Embers" in data.content
        assert data.chapter_number == 3
        assert data.next_url is not None
        assert "chapter-4" in data.next_url
        assert not data.is_placeholder
