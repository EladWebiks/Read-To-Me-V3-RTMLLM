"""Parse NovelBin search result HTML (no network)."""

from __future__ import annotations

from app.modules.discovery.sources.list_page import (
    keyword_search_url,
    parse_list_page_title_links,
)
from app.modules.discovery.types import ExternalSearchHit

_SOURCE = "novelbin"
_BASE = "https://novelbin.com"


def novelbin_search_url(query: str) -> str:
    """Build the NovelBin title search URL."""
    return keyword_search_url(_BASE, query)


def parse_novelbin_search(html: str, *, base_url: str = _BASE) -> list[ExternalSearchHit]:
    """Extract title hits from a NovelBin search page (NovelFull-family markup)."""
    return parse_list_page_title_links(html, source=_SOURCE, base_url=base_url)
