"""Ranobes.top / ranobes.net scrape adapter — HTML parsing only."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag

from app.modules.scraping.types import BookMetadata, ChapterData

_HOSTS = ("ranobes.top", "ranobes.net")
_CHAPTER_TITLE_NUM = re.compile(r"(?i)chapter\s*(\d+)")
_TOC_PER_PAGE = 25


class RanobesAdapter:
    """Deterministic parser for ranobes.top / ranobes.net pages."""

    name = "ranobes"

    def matches(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return any(domain in host for domain in _HOSTS)

    def derive_book_url(self, chapter_url: str) -> str | None:
        parsed = urlparse(chapter_url)
        # Chapter pages look like /slug-ID/chapterid.html — not /novels/ or /chapters/.
        if "/novels/" in parsed.path or "/chapters/" in parsed.path:
            return None
        if not re.search(r"-(\d+)/(\d+)\.html$", parsed.path):
            return None
        novel_id = extract_novel_id(chapter_url)
        if not novel_id:
            return None
        slug = _slug_from_chapter_path(parsed.path, novel_id)
        path = f"/novels/{novel_id}-{slug}.html" if slug else f"/novels/{novel_id}.html"
        return urlunparse((parsed.scheme or "https", parsed.netloc, path, "", "", ""))

    def parse_book_page(self, html: str, base_url: str) -> BookMetadata:
        soup = BeautifulSoup(html, "html.parser")
        novel_id = extract_novel_id(base_url) or ""
        first = ""
        if novel_id:
            first = urljoin(base_url, f"/chapters/{novel_id}/first")
        return BookMetadata(
            title=_book_title(soup),
            author=_book_author(soup),
            cover_url=_book_cover(soup, base_url),
            first_chapter_url=first or _first_chapter_fallback(soup, base_url),
        )

    def parse_chapter_page(self, html: str, base_url: str) -> ChapterData:
        soup = BeautifulSoup(html, "html.parser")
        title = _chapter_title(soup)
        content = _chapter_content(soup)
        return ChapterData(
            title=title,
            content=content,
            next_url=_next_url(soup, base_url),
            book_title=_chapter_book_title(soup),
            book_author=_book_author(soup),
            chapter_number=_number_from_title(title),
            is_placeholder=not content.strip(),
        )


def extract_novel_id(url: str) -> str | None:
    """Extract the numeric novel id from a ranobes book/chapter/TOC URL."""
    path = urlparse(url).path
    patterns = (
        r"/chapters/(\d+)",
        r"/novels/(\d+)-",
        r"/(\d+)-[^/]+\.html$",
        r"-(\d+)/(\d+)\.html$",
    )
    for pattern in patterns:
        match = re.search(pattern, path, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def chapters_index_url(book_url: str) -> str | None:
    """TOC index URL for a novel."""
    novel_id = extract_novel_id(book_url)
    if not novel_id:
        return None
    parsed = urlparse(book_url)
    return urlunparse(
        (parsed.scheme or "https", parsed.netloc, f"/chapters/{novel_id}/", "", "", "")
    )


def chapters_page_url(book_url: str, page: int) -> str | None:
    """Paginated TOC URL (page 1 is the index)."""
    index = chapters_index_url(book_url)
    if not index:
        return None
    if page <= 1:
        return index
    return index.rstrip("/") + f"/page/{page}/"


def toc_page_for_chapter(chapter_number: int, total: int, *, per_page: int = _TOC_PER_PAGE) -> int:
    """Newest-first TOC page that should contain *chapter_number*."""
    if total <= 0 or chapter_number <= 0:
        return 1
    capped = min(chapter_number, total)
    return max(1, (total - capped) // per_page + 1)


def parse_toc_data(html: str) -> dict[str, Any] | None:
    """Parse ``window.__DATA__`` chapter-list payload."""
    raw = _extract_json_object(html, "window.__DATA__")
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def find_chapter_link_in_toc(html: str, chapter_number: int) -> str | None:
    """Find a chapter URL in a TOC page by title number or __DATA__ entries."""
    found = _find_in_toc_data(html, chapter_number)
    return found if found is not None else _find_in_toc_links(html, chapter_number)


def _extract_json_object(html: str, marker: str) -> str | None:
    start = html.find(marker)
    if start < 0:
        return None
    brace = html.find("{", start)
    if brace < 0:
        return None
    depth = 0
    for idx, char in enumerate(html[brace:], brace):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return html[brace : idx + 1]
    return None


def _find_in_toc_data(html: str, chapter_number: int) -> str | None:
    data = parse_toc_data(html)
    if not data:
        return None
    for item in data.get("chapters") or []:
        if not isinstance(item, dict):
            continue
        if _number_from_title(str(item.get("title") or "")) != chapter_number:
            continue
        link = str(item.get("link") or "")
        return link or None
    return None


def _find_in_toc_links(html: str, chapter_number: int) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.select(".cat_line a, a[href]"):
        if _number_from_title(link.get_text(" ", strip=True)) != chapter_number:
            continue
        href = str(link.get("href") or "")
        if href and not href.startswith(("#", "javascript:")):
            return href
    return None


def _slug_from_chapter_path(path: str, novel_id: str) -> str:
    match = re.search(rf"/([^/]+)-{re.escape(novel_id)}/\d+\.html$", path, re.IGNORECASE)
    return match.group(1) if match else ""


def _book_title(soup: BeautifulSoup) -> str:
    tag = soup.select_one("h1.title, h1")
    if not tag:
        return ""
    text = tag.get_text(" ", strip=True)
    return text.split("•", 1)[0].strip()


def _book_author(soup: BeautifulSoup) -> str:
    tag = soup.select_one('.tag_list a[href*="/authors/"], a[href*="/authors/"]')
    return tag.get_text(strip=True) if tag else ""


def _book_cover(soup: BeautifulSoup, base_url: str) -> str:
    img = soup.select_one(".r-fullstory-poster .poster img, .poster img")
    src = _attr(img, "data-src") or _attr(img, "src")
    return urljoin(base_url, src) if src else ""


def _first_chapter_fallback(soup: BeautifulSoup, base_url: str) -> str:
    link = soup.select_one("a.read-begin, a[href*='/chapters/'][href$='/first']")
    if link and link.get("href"):
        return urljoin(base_url, str(link["href"]))
    return ""


def _chapter_title(soup: BeautifulSoup) -> str:
    tag = soup.select_one("h1.title, h1")
    if not tag:
        return ""
    text = tag.get_text(" ", strip=True)
    return text.split("|", 1)[0].strip()


def _chapter_book_title(soup: BeautifulSoup) -> str:
    for link in soup.select(".breadcrumbs a, .speedbar a"):
        href = str(link.get("href") or "")
        if "/novels/" in href or re.search(r"/\d+-", href):
            return link.get_text(strip=True)
    return ""


def _chapter_content(soup: BeautifulSoup) -> str:
    article = soup.select_one("#arrticle, #article, div.text")
    if not article:
        return ""
    for tag in article.select("script, iframe, ins, .free-support, div[id^='adfox_']"):
        tag.decompose()
    paragraphs = [p.get_text(strip=True) for p in article.find_all("p") if p.get_text(strip=True)]
    if paragraphs:
        return "\n\n".join(paragraphs)
    return article.get_text("\n\n", strip=True)


def _next_url(soup: BeautifulSoup, base_url: str) -> str | None:
    for link in soup.select("a[rel='next'], a.next, a"):
        text = link.get_text(" ", strip=True).lower()
        rel = " ".join(link.get("rel") or []) if link.get("rel") else ""
        if "next" not in text and "next" not in rel.lower():
            continue
        href = _attr(link, "href")
        if not href or href.startswith("javascript"):
            continue
        resolved = urljoin(base_url, href)
        if resolved.rstrip("/") != base_url.rstrip("/"):
            return resolved
    return None


def _number_from_title(title: str) -> int | None:
    match = _CHAPTER_TITLE_NUM.search(title)
    return int(match.group(1)) if match else None


def _attr(tag: Tag | None, key: str) -> str:
    if tag is None:
        return ""
    val = tag.get(key, "")
    return str(val) if val else ""
