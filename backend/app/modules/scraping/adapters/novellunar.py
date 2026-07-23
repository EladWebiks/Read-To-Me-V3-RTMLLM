"""Novellunar.com scrape adapter — HTML parsing only."""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

from app.modules.scraping.types import BookMetadata, ChapterData

_CHAPTER_URL_RE = re.compile(
    r"novellunar\.com/novel/([^/]+)/chapter/(\d+)",
    re.IGNORECASE,
)
_AUTHOR_RE = re.compile(r"written by the author\s+(.+?),", re.IGNORECASE)


class NovellunarAdapter:
    """Deterministic parser for novellunar.com pages."""

    name = "novellunar"

    def matches(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return "novellunar.com" in host

    def derive_book_url(self, chapter_url: str) -> str | None:
        m = _CHAPTER_URL_RE.search(chapter_url)
        if not m:
            return None
        parsed = urlparse(chapter_url)
        slug = m.group(1)
        return urlunparse((parsed.scheme, parsed.netloc, f"/novel/{slug}", "", "", ""))

    def parse_book_page(self, html: str, base_url: str) -> BookMetadata:
        soup = BeautifulSoup(html, "html.parser")
        title = _book_title(soup)
        author = _book_author(soup)
        cover_url = _book_cover(soup, base_url)
        first = _first_chapter(soup, base_url)
        return BookMetadata(
            title=title, author=author, cover_url=cover_url, first_chapter_url=first
        )

    def parse_chapter_page(self, html: str, base_url: str) -> ChapterData:
        soup = BeautifulSoup(html, "html.parser")
        title = _chapter_title(soup)
        number = _chapter_number_from_url(base_url, title)
        content = _chapter_content(soup)
        next_url = _build_next_url(base_url, number)
        book_title = _chapter_book_title(soup)
        return ChapterData(
            title=title,
            content=content,
            next_url=next_url,
            book_title=book_title,
            book_author="",
            chapter_number=number,
            is_placeholder=not content.strip(),
        )


def _book_title(soup: BeautifulSoup) -> str:
    tag = soup.select_one("h1.text-2xl") or soup.select_one("h1")
    return tag.get_text(strip=True) if tag else ""


def _book_author(soup: BeautifulSoup) -> str:
    meta = soup.select_one('meta[name="description"]')
    if meta:
        m = _AUTHOR_RE.search(str(meta.get("content", "")))
        if m:
            return m.group(1).strip()
    return ""


def _book_cover(soup: BeautifulSoup, base_url: str) -> str:
    img = soup.select_one('img[src*="img.novellunar.com"]')
    url = _attr(img, "src") if img else ""
    if not url:
        og = soup.select_one("meta[property='og:image']")
        url = _attr(og, "content") if og else ""
    if url and not url.startswith("http"):
        from urllib.parse import urljoin

        url = urljoin(base_url, url)
    return url


def _first_chapter(soup: BeautifulSoup, base_url: str) -> str:
    link = soup.select_one('a[href*="/chapter/1"]')
    if link and link.get("href"):
        href = str(link["href"])
        if not href.startswith("http"):
            from urllib.parse import urljoin

            href = urljoin(base_url, href)
        return href
    return ""


def _parse_url_parts(url: str) -> tuple[str, int] | None:
    m = _CHAPTER_URL_RE.search(url)
    if not m:
        return None
    return m.group(1), int(m.group(2))


def _chapter_title(soup: BeautifulSoup) -> str:
    tag = soup.select_one("h1.text-lg")
    return tag.get_text(strip=True) if tag else ""


def _chapter_number_from_url(base_url: str, title: str) -> int | None:
    parts = _parse_url_parts(base_url)
    if parts:
        return parts[1]
    if title:
        m = re.search(r"Chapter\s+(\d+)", title, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None


def _chapter_content(soup: BeautifulSoup) -> str:
    root = soup.select_one('article div[style*="pre-wrap"]')
    if not root:
        return ""
    paragraphs: list[str] = []
    current: list[str] = []
    for span in root.find_all("span", recursive=False):
        stripped = span.get_text().strip()
        if not stripped:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        current.append(stripped)
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def _build_next_url(current_url: str, chapter_number: int | None) -> str | None:
    if chapter_number is None:
        return None
    parts = _parse_url_parts(current_url)
    if not parts:
        return None
    slug, _ = parts
    parsed = urlparse(current_url)
    return urlunparse(
        (parsed.scheme, parsed.netloc, f"/novel/{slug}/chapter/{chapter_number + 1}", "", "", "")
    )


def _chapter_book_title(soup: BeautifulSoup) -> str:
    links = soup.select("a.hover\\:text-blue-600")
    for link in links:
        href = link.get("href", "")
        if str(href).startswith("/novel/") and "/chapter/" not in str(href):
            return link.get_text(strip=True)
    og = soup.select_one("meta[property='og:title']")
    if og:
        return re.sub(
            r"\s+Chapter\s+\d+.*$",
            "",
            str(og.get("content", "")),
            flags=re.IGNORECASE,
        ).strip()
    return ""


def _attr(tag: object | None, key: str) -> str:
    if tag is None:
        return ""
    val = getattr(tag, "get", lambda *_a: "")(key, "")
    return str(val) if val else ""
