"""Parse FreeWebNovel search result HTML (no network)."""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.modules.discovery.types import ExternalSearchHit

_SOURCE = "freewebnovel"
_BASE = "https://freewebnovel.com"
_SEARCH_URL = f"{_BASE}/search/"


def freewebnovel_search_url() -> str:
    """POST target for FreeWebNovel title search."""
    return _SEARCH_URL


def freewebnovel_search_form(query: str) -> dict[str, str]:
    """Form body for FreeWebNovel search."""
    return {"searchkey": query}


def parse_freewebnovel_search(html: str, *, base_url: str = _BASE) -> list[ExternalSearchHit]:
    """Extract title hits from a FreeWebNovel search results page."""
    soup = BeautifulSoup(html, "html.parser")
    hits: list[ExternalSearchHit] = []
    for link in soup.select(".col-content .con .txt h3 a"):
        href = link.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        title = link.get_text(strip=True)
        if not title:
            continue
        hits.append(
            ExternalSearchHit(
                source=_SOURCE,
                title=title,
                author=_author_near(link),
                book_url=urljoin(base_url, href.strip()),
            )
        )
    return hits


def _author_near(link: object) -> str:
    parent = getattr(link, "parent", None)
    block = getattr(parent, "parent", None) if parent is not None else None
    if block is None:
        return ""
    author = block.select_one(".author, a[href*='/authors/']")
    if author is None:
        return ""
    text = author.get_text(strip=True)
    return text if isinstance(text, str) else ""
