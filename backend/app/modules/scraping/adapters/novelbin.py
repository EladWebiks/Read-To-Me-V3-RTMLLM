"""Novelbin.com scrape adapter — HTML parsing only."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

from app.modules.scraping.types import BookMetadata, ChapterData

_CHAPTER_NUM_RE = re.compile(r"/chapter-(\d+)", re.IGNORECASE)


class NovelbinAdapter:
    """Deterministic parser for novelbin.com pages."""

    name = "novelbin"

    def matches(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return "novelbin.com" in host

    def derive_book_url(self, chapter_url: str) -> str | None:
        m = re.search(r"(https?://[^/]+/b/[^/]+)", chapter_url, re.IGNORECASE)
        return m.group(1).rstrip("/") if m else None

    def parse_book_page(self, html: str, base_url: str) -> BookMetadata:
        soup = BeautifulSoup(html, "html.parser")
        title = _extract_book_title(soup)
        author = _extract_book_author(soup)
        cover_url = _extract_cover_url(soup, base_url)
        first_chapter = _extract_first_chapter(soup, base_url)
        return BookMetadata(
            title=title,
            author=author,
            cover_url=cover_url,
            first_chapter_url=first_chapter,
        )

    def parse_chapter_page(self, html: str, base_url: str) -> ChapterData:
        soup = BeautifulSoup(html, "html.parser")
        title = _parse_chapter_title(soup)
        content = _parse_chapter_content(soup)
        next_url = _parse_next_url(soup, base_url)
        book_title, book_author = _parse_breadcrumb_meta(soup)
        number = _chapter_number_from_url(base_url)
        return ChapterData(
            title=title,
            content=content,
            next_url=next_url,
            book_title=book_title,
            book_author=book_author,
            chapter_number=number,
            is_placeholder=not content.strip(),
        )


def _chapter_number_from_url(base_url: str) -> int | None:
    match = _CHAPTER_NUM_RE.search(urlparse(base_url).path)
    return int(match.group(1)) if match else None


def _extract_book_title(soup: BeautifulSoup) -> str:
    tag = soup.select_one("h3.title") or soup.select_one("h1")
    return tag.get_text(strip=True) if tag else ""


def _extract_book_author(soup: BeautifulSoup) -> str:
    for sel in (".info a", 'a[href*="/author/"]'):
        tag = soup.select_one(sel)
        if tag:
            return tag.get_text(strip=True)
    return ""


def _extract_cover_url(soup: BeautifulSoup, base_url: str) -> str:
    img = soup.select_one(".book img")
    url = _attr(img, "src") or _attr(img, "data-src") if img else ""
    if not url:
        og = soup.select_one("meta[property='og:image']")
        url = _attr(og, "content") if og else ""
    return urljoin(base_url, url) if url else ""


def _extract_first_chapter(soup: BeautifulSoup, base_url: str) -> str:
    link = soup.select_one("#list-chapter a") or soup.select_one(".list-chapter a")
    if link and link.get("href"):
        return urljoin(base_url, str(link["href"]))
    return ""


def _parse_chapter_title(soup: BeautifulSoup) -> str:
    tag = soup.select_one("a.chr-title") or soup.select_one(".chr-text span")
    return tag.get_text(strip=True) if tag else ""


def _parse_chapter_content(soup: BeautifulSoup) -> str:
    div = soup.select_one("#chr-content")
    if not div:
        return ""
    return _extract_paragraphs(div)


def _extract_paragraphs(container: Tag) -> str:
    paragraphs: list[str] = []
    for child in container.children:
        if isinstance(child, Tag):
            for br in child.find_all("br"):
                br.replace_with(NavigableString("\n"))
            _collect_lines(child.get_text(), paragraphs)
        elif isinstance(child, NavigableString):
            _collect_lines(str(child), paragraphs)
    return "\n\n".join(paragraphs)


def _collect_lines(text: str, out: list[str]) -> None:
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped:
            out.append(stripped)


def _parse_next_url(soup: BeautifulSoup, base_url: str) -> str | None:
    btn = soup.select_one("#next_chap")
    if not btn or not btn.get("href"):
        btn = soup.select_one('a[data-chapter-nav="next"]')
    if not btn or not btn.get("href"):
        return None
    href = str(btn["href"])
    if not href or href.endswith("#"):
        return None
    resolved = urljoin(base_url, href)
    if resolved.rstrip("/") == base_url.rstrip("/"):
        return None
    return resolved


def _parse_breadcrumb_meta(soup: BeautifulSoup) -> tuple[str, str]:
    book_title = ""
    tag = soup.select_one(".novel-title")
    if tag:
        book_title = tag.get_text(strip=True)
    else:
        crumbs = soup.select("ol.breadcrumb li")
        if len(crumbs) >= 2:
            link = crumbs[1].select_one("a")
            if link:
                book_title = link.get_text(strip=True)
    author = ""
    for sel in (".novel-author a", 'a[href*="/author/"]', ".author"):
        atag = soup.select_one(sel)
        if atag:
            author = atag.get_text(strip=True)
            break
    return book_title, author


def _attr(tag: Tag | None, key: str) -> str:
    if tag is None:
        return ""
    val = tag.get(key, "")
    return str(val) if val else ""
