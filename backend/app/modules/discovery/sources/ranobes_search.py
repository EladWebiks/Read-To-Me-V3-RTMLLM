"""Parse Ranobes search result HTML (no network)."""

from __future__ import annotations

import re
from urllib.parse import quote_plus, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from app.modules.discovery.types import ExternalSearchHit

_SOURCE = "ranobes"
_BASE = "https://ranobes.top"
_NOVEL_PATH = re.compile(r"/novels/(\d+)(?:-([^/?#]+))?\.html", re.IGNORECASE)


def ranobes_search_url(query: str) -> str:
    """Build the Ranobes title search URL."""
    return f"{_BASE}/search/{quote_plus(query)}/"


def canonicalize_ranobes_book_url(url: str, *, base_url: str = _BASE) -> str:
    """Normalize a novel page URL (https, no query/fragment, /novels/{id}-….html)."""
    absolute = urljoin(base_url, url.strip())
    parsed = urlparse(absolute)
    match = _NOVEL_PATH.search(parsed.path)
    if match is None:
        return urlunparse((parsed.scheme or "https", parsed.netloc, parsed.path, "", "", ""))
    novel_id, slug = match.group(1), match.group(2) or ""
    path = f"/novels/{novel_id}-{slug}.html" if slug else f"/novels/{novel_id}.html"
    host = parsed.netloc or urlparse(base_url).netloc or "ranobes.top"
    return urlunparse((parsed.scheme or "https", host, path, "", "", ""))


def parse_ranobes_search(html: str, *, base_url: str = _BASE) -> list[ExternalSearchHit]:
    """Extract title hits from a Ranobes search results page."""
    soup = BeautifulSoup(html, "html.parser")
    hits: list[ExternalSearchHit] = []
    seen: set[str] = set()
    for link in soup.select(".short-cont .title a, article.shortstory h2.title a"):
        href = link.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        if "/novels/" not in href:
            continue
        book_url = canonicalize_ranobes_book_url(href, base_url=base_url)
        if book_url in seen:
            continue
        seen.add(book_url)
        title = link.get_text(strip=True)
        if not title:
            continue
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
    block = getattr(parent, "parent", None) if parent is not None else None
    if block is None:
        return ""
    author = block.select_one('a[href*="/authors/"]')
    if author is None:
        return ""
    text = author.get_text(strip=True)
    return text if isinstance(text, str) else ""
