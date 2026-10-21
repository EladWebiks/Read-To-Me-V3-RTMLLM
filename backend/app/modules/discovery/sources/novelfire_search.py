"""Parse NovelFire search result HTML (no network)."""

from __future__ import annotations

import re
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup, Tag

from app.modules.discovery.types import ExternalSearchHit
from app.modules.scraping.adapters.novelfire import canonicalize_novelfire_url

_SOURCE = "novelfire"
_BASE = "https://novelfire.net"
_CHAPTERS = re.compile(r"([\d,]+)\s*Chapters?", re.IGNORECASE)


def novelfire_search_url(query: str) -> str:
    """Build the NovelFire title search URL."""
    return f"{_BASE}/search?{urlencode({'keyword': query, 'type': 'title'})}"


def parse_novelfire_search(html: str, *, base_url: str = _BASE) -> list[ExternalSearchHit]:
    """Extract title hits from a NovelFire search results page."""
    soup = BeautifulSoup(html, "html.parser")
    hits: list[ExternalSearchHit] = []
    seen: set[str] = set()
    for item in soup.select("li.novel-item"):
        link = item.select_one('a[href*="/book/"]')
        if link is None:
            continue
        href = link.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        book_url = canonicalize_novelfire_url(urljoin(base_url, href.strip()))
        if book_url in seen:
            continue
        seen.add(book_url)
        title = _title(link, item)
        if not title:
            continue
        hits.append(
            ExternalSearchHit(
                source=_SOURCE,
                title=title,
                author="",
                book_url=book_url,
                chapter_count_estimate=_chapter_estimate(item),
            )
        )
    return hits


def _title(link: Tag, item: Tag) -> str:
    heading = item.select_one("h4.novel-title, .novel-title")
    if heading is not None:
        text = heading.get_text(strip=True)
        if text:
            return text
    title_attr = link.get("title")
    if isinstance(title_attr, str) and title_attr.strip():
        return title_attr.strip()
    return ""


def _chapter_estimate(item: Tag) -> int | None:
    found = [
        int(match.group(1).replace(",", ""))
        for match in _CHAPTERS.finditer(item.get_text(" ", strip=True))
    ]
    return max(found) if found else None
