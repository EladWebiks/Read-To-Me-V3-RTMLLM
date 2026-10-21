"""Parse ScribbleHub search result HTML (no network)."""

from __future__ import annotations

from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from app.modules.discovery.types import ExternalSearchHit

_SOURCE = "scribblehub"
_BASE = "https://www.scribblehub.com"


def scribblehub_search_url(query: str) -> str:
    """Build the ScribbleHub fiction search URL."""
    return f"{_BASE}/?{urlencode({'s': query, 'post_type': 'fictionposts'})}"


def parse_scribblehub_search(html: str, *, base_url: str = _BASE) -> list[ExternalSearchHit]:
    """Extract series hits from a ScribbleHub search results page."""
    soup = BeautifulSoup(html, "html.parser")
    hits: list[ExternalSearchHit] = []
    seen: set[str] = set()
    for link in soup.select(
        ".search_title a[href*='/series/'], "
        ".search_body a[href*='/series/'], "
        "a.fic_title[href*='/series/'], "
        "h1.fic_title a[href*='/series/']"
    ):
        href = link.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        book_url = urljoin(base_url, href.strip())
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
    root = block if block is not None else parent
    if root is None:
        return ""
    author = root.select_one(".auth_name_fic, a[href*='/profile/']")
    if author is None:
        return ""
    text = author.get_text(strip=True)
    return text if isinstance(text, str) else ""
