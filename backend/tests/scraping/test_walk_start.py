"""Unit tests for scrape job start-URL resolution."""

from __future__ import annotations

from app.modules.scraping.adapters.freewebnovel import FreewebnovelAdapter
from app.modules.scraping.adapters.novelbin import NovelbinAdapter
from app.modules.scraping.adapters.novelfire import NovelfireAdapter
from app.modules.scraping.adapters.novelfull import (
    NovelfullAdapter,
    ajax_chapter_option_url,
    book_toc_page_url,
    extract_novel_id,
    toc_page_for_chapter,
)
from app.modules.scraping.adapters.novellunar import NovellunarAdapter
from app.modules.scraping.adapters.ranobes import RanobesAdapter
from app.modules.scraping.adapters.scribblehub import ScribblehubAdapter
from app.modules.scraping.walk_start import (
    chapter_number_from_url,
    construct_chapter_url,
    find_chapter_url_in_html,
    resolve_job_start_url,
    resolve_walk_start,
)

_BOOK = "https://novelfull.net/martial-peak.html"
_CH1 = "https://novelfull.net/martial-peak/chapter-1-martial-peak.html"
_CH5 = "https://novelfull.net/martial-peak/chapter-5-something.html"
_LUNAR_1 = "https://novellunar.com/novel/world-domination-system-v1/chapter/1"
_LUNAR_BOOK = "https://novellunar.com/novel/world-domination-system-v1"
_FWN_BOOK = "https://freewebnovel.com/novel/epic-tale"
_FWN_1 = "https://freewebnovel.com/novel/epic-tale/chapter-1"
_BIN_BOOK = "https://novelbin.com/b/test-novel"
_BIN_1 = "https://novelbin.com/b/test-novel/chapter-1"
_FIRE_BOOK = "https://novelfire.net/book/epic-fire"
_FIRE_1 = "https://novelfire.net/book/epic-fire/chapter-1"
_SH_BOOK = "https://www.scribblehub.com/series/52931/rupegia/"
_SH_HTML = (
    '<ol class="toc_ol">'
    '<li><a class="toc_a" href="/read/52931-rupegia/chapter/53051/">Chapter 3</a></li>'
    '<li><a class="toc_a" href="/read/52931-rupegia/chapter/53000/">Chapter 2</a></li>'
    '<li><a class="toc_a" href="/read/52931-rupegia/chapter/52941/">Chapter 1</a></li>'
    "</ol>"
)


def test_book_page_resolves_to_first_chapter() -> None:
    assert resolve_walk_start(NovelfullAdapter(), _BOOK, _CH1) == _CH1


def test_chapter_url_kept() -> None:
    assert resolve_walk_start(NovelfullAdapter(), _CH5, _CH1) == _CH5


def test_missing_first_chapter_keeps_request() -> None:
    assert resolve_walk_start(NovelfullAdapter(), _BOOK, "") == _BOOK


def test_freewebnovel_book_page_constructs_chapter_one() -> None:
    """When TOC first-chapter link is missing, still start at /chapter-1."""
    url = resolve_job_start_url(
        FreewebnovelAdapter(),
        _FWN_BOOK,
        "",
        start_chapter=1,
        book_url=_FWN_BOOK,
    )
    assert url == _FWN_1


def test_novelfire_book_page_constructs_chapter_one() -> None:
    url = resolve_job_start_url(
        NovelfireAdapter(),
        _FIRE_BOOK,
        "",
        start_chapter=1,
        book_url=_FIRE_BOOK,
    )
    assert url == _FIRE_1


def test_novellunar_jumps_to_start_chapter() -> None:
    url = resolve_job_start_url(
        NovellunarAdapter(),
        _LUNAR_BOOK,
        _LUNAR_1,
        start_chapter=137,
    )
    assert url.endswith("/chapter/137")
    assert chapter_number_from_url(url) == 137


def test_freewebnovel_constructs_chapter_url() -> None:
    url = resolve_job_start_url(
        FreewebnovelAdapter(),
        _FWN_BOOK,
        _FWN_1,
        start_chapter=42,
        book_url=_FWN_BOOK,
    )
    assert url == "https://freewebnovel.com/novel/epic-tale/chapter-42"
    assert construct_chapter_url(FreewebnovelAdapter(), _FWN_1, 10) is not None


def test_novelbin_constructs_chapter_url() -> None:
    url = resolve_job_start_url(
        NovelbinAdapter(),
        _BIN_BOOK,
        _BIN_1,
        start_chapter=88,
        book_url=_BIN_BOOK,
    )
    assert url == "https://novelbin.com/b/test-novel/chapter-88"
    assert chapter_number_from_url(url) == 88


def test_toc_html_finds_novelfull_chapter() -> None:
    html = (
        '<div id="list-chapter">'
        '<a href="/martial-peak/chapter-5-something.html">Chapter 5</a>'
        "</div>"
    )
    found = find_chapter_url_in_html(html, _BOOK, 5)
    assert found == _CH5


def test_job_start_uses_toc_when_present() -> None:
    html = '<a href="/martial-peak/chapter-137-foo.html">Chapter 137</a>'
    url = resolve_job_start_url(
        NovelfullAdapter(),
        _BOOK,
        _CH1,
        start_chapter=137,
        book_html=html,
        book_url=_BOOK,
    )
    assert "chapter-137" in url


def test_novelfull_ajax_and_toc_page_helpers() -> None:
    html = '<div id="rating" data-novel-id="951"></div>'
    assert extract_novel_id(html) == "951"
    assert ajax_chapter_option_url("951").endswith("novelId=951")
    assert toc_page_for_chapter(137) == 3
    assert toc_page_for_chapter(50) == 1
    assert toc_page_for_chapter(51) == 2
    assert book_toc_page_url(_BOOK, 1) == _BOOK
    assert book_toc_page_url(_BOOK, 3).endswith("?page=3")


def test_ajax_option_list_parses_chapter_href() -> None:
    html = (
        '<select id="chapter-select">'
        '<option value="/martial-peak/chapter-137-foo.html">Chapter 137</option>'
        "</select>"
    )
    found = find_chapter_url_in_html(html, _BOOK, 137)
    assert found is not None
    assert "chapter-137" in found


def test_novelfire_constructs_chapter_url() -> None:
    url = resolve_job_start_url(
        NovelfireAdapter(),
        _FIRE_BOOK,
        _FIRE_1,
        start_chapter=150,
        book_url=_FIRE_BOOK,
    )
    assert url == "https://novelfire.net/book/epic-fire/chapter-150"
    assert chapter_number_from_url(url) == 150


def test_scribblehub_toc_picks_start_chapter() -> None:
    url = resolve_job_start_url(
        ScribblehubAdapter(),
        _SH_BOOK,
        "https://www.scribblehub.com/read/52931-rupegia/chapter/52941/",
        start_chapter=2,
        book_html=_SH_HTML,
        book_url=_SH_BOOK,
    )
    assert url.endswith("/chapter/53000/")


def test_scribblehub_post_id_not_chapter_number() -> None:
    assert (
        chapter_number_from_url("https://www.scribblehub.com/read/52931-rupegia/chapter/52941/")
        is None
    )


def test_ranobes_construct_unavailable() -> None:
    assert (
        construct_chapter_url(RanobesAdapter(), "https://ranobes.top/novels/1-x.html", 10) is None
    )
