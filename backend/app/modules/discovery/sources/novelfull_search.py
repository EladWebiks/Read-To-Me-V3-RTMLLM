"""Parse NovelFull search result HTML (no network)."""

from __future__ import annotations

from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from app.modules.discovery.types import ExternalSearchHit

_SOURCE = "novelfull"
_SEARCH_BASE = "https://novelfull.net/search"


def novelfull_search_url(query: str) -> str:
    """Build the NovelFull title search URL."""
    return f"{_SEARCH_BASE}?{urlencode({'keyword': query})}"


def parse_novelfull_search(
    html: str, *, base_url: str = "https://novelfull.net"
) -> list[ExternalSearchHit]:
    """Extract title hits from a NovelFull search page."""
    soup = BeautifulSoup(html, "html.parser")
    hits: list[ExternalSearchHit] = []
    for link in soup.select("#list-page .row h3[class*='title'] > a"):
        href = link.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        title_attr = link.get("title")
        title = (title_attr if isinstance(title_attr, str) else None) or link.get_text()
        title = title.strip() if isinstance(title, str) else ""
        if not title:
            continue
        book_url = urljoin(base_url, href.strip())
        hits.append(
            ExternalSearchHit(
                source=_SOURCE,
                title=title,
                author=_author_near(link),
                book_url=book_url,
            )
        )
    return hits


def _author_near(link: object) -> str:
    parent = getattr(link, "parent", None)
    row = getattr(parent, "parent", None) if parent is not None else None
    if row is None:
        return ""
    author = row.select_one(".author, .desc .author, span.author")
    if author is None:
        return ""
    text = author.get_text(strip=True)
    return text if isinstance(text, str) else ""
