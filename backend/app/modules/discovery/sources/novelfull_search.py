"""Parse NovelFull search result HTML (no network)."""

from __future__ import annotations

from app.modules.discovery.sources.list_page import (
    keyword_search_url,
    parse_list_page_title_links,
)
from app.modules.discovery.types import ExternalSearchHit

_SOURCE = "novelfull"
_BASE = "https://novelfull.net"


def novelfull_search_url(query: str) -> str:
    """Build the NovelFull title search URL."""
    return keyword_search_url(_BASE, query)


def parse_novelfull_search(html: str, *, base_url: str = _BASE) -> list[ExternalSearchHit]:
    """Extract title hits from a NovelFull search page."""
    return parse_list_page_title_links(html, source=_SOURCE, base_url=base_url)
