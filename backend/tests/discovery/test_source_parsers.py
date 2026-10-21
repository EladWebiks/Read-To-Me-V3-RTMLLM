"""Unit tests for all discovery source parsers."""

from pathlib import Path

import pytest
from app.modules.discovery.sources.freewebnovel_search import parse_freewebnovel_search
from app.modules.discovery.sources.novelbin_search import (
    novelbin_search_url,
    parse_novelbin_search,
)
from app.modules.discovery.sources.novelfire_search import (
    novelfire_search_url,
    parse_novelfire_search,
)
from app.modules.discovery.sources.novelfull_search import parse_novelfull_search
from app.modules.discovery.sources.novellunar_search import parse_novellunar_search
from app.modules.discovery.sources.ranobes_search import (
    parse_ranobes_search,
    ranobes_search_url,
)
from app.modules.discovery.sources.registry import SOURCE_SEARCHERS
from app.modules.discovery.sources.scribblehub_search import (
    parse_scribblehub_search,
    scribblehub_search_url,
)
from app.modules.scraping.registry import SOURCE_DOMAINS

pytestmark = pytest.mark.unit

_FIX = Path(__file__).parent / "fixtures"


def test_registry_covers_all_scrape_sources() -> None:
    names = {name for name, _ in SOURCE_SEARCHERS}
    assert names == set(SOURCE_DOMAINS)


def test_parse_novelfull_fixture() -> None:
    html = (_FIX / "novelfull_search.html").read_text(encoding="utf-8")
    hits = parse_novelfull_search(html)
    assert len(hits) == 2
    assert hits[0].source == "novelfull"


def test_parse_novelbin_fixture() -> None:
    html = (_FIX / "novelbin_search.html").read_text(encoding="utf-8")
    hits = parse_novelbin_search(html)
    assert len(hits) == 1
    assert hits[0].source == "novelbin"
    assert hits[0].book_url.endswith("/b/shadow-slave")
    assert "keyword=" in novelbin_search_url("Shadow Slave")


def test_parse_freewebnovel_fixture() -> None:
    html = (_FIX / "freewebnovel_search.html").read_text(encoding="utf-8")
    hits = parse_freewebnovel_search(html)
    assert len(hits) == 2
    assert hits[0].source == "freewebnovel"
    assert "/novel/shadow-slave" in hits[0].book_url


def test_parse_novellunar_fixture() -> None:
    payload = (_FIX / "novellunar_search.json").read_text(encoding="utf-8")
    hits = parse_novellunar_search(payload)
    assert len(hits) == 2
    assert hits[0].source == "novellunar"
    assert hits[0].book_url.endswith("/novel/shadow-slave")
    assert hits[0].chapter_count_estimate == 2000


def test_parse_novelfire_fixture() -> None:
    html = (_FIX / "novelfire_search.html").read_text(encoding="utf-8")
    hits = parse_novelfire_search(html)
    assert len(hits) == 2
    assert hits[0].source == "novelfire"
    assert hits[0].book_url.endswith("/book/reverend-insanity")
    assert hits[0].chapter_count_estimate == 2334
    assert "type=title" in novelfire_search_url("Reverend Insanity")


def test_parse_ranobes_fixture() -> None:
    html = (_FIX / "ranobes_search.html").read_text(encoding="utf-8")
    hits = parse_ranobes_search(html)
    assert len(hits) == 2
    assert hits[0].source == "ranobes"
    assert "/novels/244924-" in hits[0].book_url
    assert "search/" in ranobes_search_url("Reverend Insanity")


def test_canonicalize_ranobes_book_url() -> None:
    from app.modules.discovery.sources.ranobes_search import canonicalize_ranobes_book_url

    raw = "https://ranobes.top/novels/244924-reverend-insanity-v812312.html?x=1#y"
    assert canonicalize_ranobes_book_url(raw) == (
        "https://ranobes.top/novels/244924-reverend-insanity-v812312.html"
    )
    assert canonicalize_ranobes_book_url("/novels/250389-foo.html").endswith(
        "/novels/250389-foo.html"
    )


def test_parse_scribblehub_fixture() -> None:
    html = (_FIX / "scribblehub_search.html").read_text(encoding="utf-8")
    hits = parse_scribblehub_search(html)
    assert len(hits) == 2
    assert hits[0].source == "scribblehub"
    assert hits[0].book_url.endswith("/series/52931/rupegia/")
    assert "post_type=fictionposts" in scribblehub_search_url("Rupegia")
