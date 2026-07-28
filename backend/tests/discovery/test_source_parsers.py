"""Unit tests for all discovery source parsers."""

from pathlib import Path

import pytest
from app.modules.discovery.sources.freewebnovel_search import parse_freewebnovel_search
from app.modules.discovery.sources.novelbin_search import (
    novelbin_search_url,
    parse_novelbin_search,
)
from app.modules.discovery.sources.novelfull_search import parse_novelfull_search
from app.modules.discovery.sources.novellunar_search import parse_novellunar_search
from app.modules.discovery.sources.registry import SOURCE_SEARCHERS

pytestmark = pytest.mark.unit

_FIX = Path(__file__).parent / "fixtures"


def test_registry_covers_all_scrape_sources() -> None:
    names = {name for name, _ in SOURCE_SEARCHERS}
    assert names == {"novelfull", "novelbin", "freewebnovel", "novellunar"}


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
