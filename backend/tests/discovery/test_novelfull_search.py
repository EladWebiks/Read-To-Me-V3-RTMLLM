"""Unit tests for NovelFull discovery search parsing."""

from pathlib import Path

import pytest
from app.modules.discovery.sources.novelfull_search import (
    novelfull_search_url,
    parse_novelfull_search,
)

pytestmark = pytest.mark.unit

_FIXTURE = Path(__file__).parent / "fixtures" / "novelfull_search.html"


def test_novelfull_search_url() -> None:
    url = novelfull_search_url("Shadow Slave")
    assert url.startswith("https://novelfull.net/search?")
    assert "Shadow+Slave" in url or "Shadow%20Slave" in url


def test_parse_novelfull_search_hits() -> None:
    html = _FIXTURE.read_text(encoding="utf-8")
    hits = parse_novelfull_search(html)
    assert len(hits) == 2
    assert hits[0].title == "Shadow Slave"
    assert hits[0].source == "novelfull"
    assert hits[0].book_url.endswith("/shadow-slave.html")
    assert hits[1].title == "Shadow Slave Extra"
