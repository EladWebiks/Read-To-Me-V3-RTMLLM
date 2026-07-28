"""Shared HTML helpers for NovelFull-like search pages."""

from __future__ import annotations

from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from app.modules.discovery.types import ExternalSearchHit


def keyword_search_url(base: str, query: str) -> str:
    """Build ``/search?keyword=…`` for NovelFull-family sites."""
    return f"{base.rstrip('/')}/search?{urlencode({'keyword': query})}"


def parse_list_page_title_links(
    html: str,
    *,
    source: str,
    base_url: str,
) -> list[ExternalSearchHit]:
    """Parse ``#list-page .row h3[class*='title'] > a`` result rows."""
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
        hits.append(
            ExternalSearchHit(
                source=source,
                title=title,
                author=_author_near(link),
                book_url=urljoin(base_url, href.strip()),
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
