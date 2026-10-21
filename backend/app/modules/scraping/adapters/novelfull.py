"""Novelfull.net scrape adapter — HTML parsing only."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

from app.modules.scraping.types import BookMetadata, ChapterData

_CHAPTER_PATH_RE = re.compile(r"/([^/]+)/chapter-\d+", re.IGNORECASE)
_CHAPTER_NUM_RE = re.compile(r"/chapter-(\d+)", re.IGNORECASE)


class NovelfullAdapter:
    """Deterministic parser for novelfull.net pages."""

    name = "novelfull"

    def matches(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return "novelfull.net" in host

    def derive_book_url(self, chapter_url: str) -> str | None:
        parsed = urlparse(chapter_url)
        m = _CHAPTER_PATH_RE.search(parsed.path)
        if not m:
            return None
        slug = m.group(1)
        return urlunparse((parsed.scheme, parsed.netloc, f"/{slug}.html", "", "", ""))

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
        number = _chapter_number_from_url(base_url)
        content = _chapter_content(soup)
        next_url = _next_url(soup, base_url)
        book_title, book_author = _chapter_breadcrumb(soup)
        return ChapterData(
            title=title,
            content=content,
            next_url=next_url,
            book_title=book_title,
            book_author=book_author,
            chapter_number=number,
            is_placeholder=not content.strip(),
        )


def _book_title(soup: BeautifulSoup) -> str:
    tag = soup.select_one("h3.title") or soup.select_one("h1")
    return tag.get_text(strip=True) if tag else ""


def _book_author(soup: BeautifulSoup) -> str:
    tag = soup.select_one('a[href*="/author/"]')
    return tag.get_text(strip=True) if tag else ""


def _book_cover(soup: BeautifulSoup, base_url: str) -> str:
    img = soup.select_one(".book img")
    url = _attr(img, "src") or _attr(img, "data-src") if img else ""
    if not url:
        og = soup.select_one("meta[property='og:image']")
        url = _attr(og, "content") if og else ""
    return urljoin(base_url, url) if url else ""


def _first_chapter(soup: BeautifulSoup, base_url: str) -> str:
    link = soup.select_one("#list-chapter a") or soup.select_one(".list-chapter a")
    if link and link.get("href"):
        return urljoin(base_url, str(link["href"]))
    return ""


def _chapter_title(soup: BeautifulSoup) -> str:
    tag = (
        soup.select_one("a.chapter-title")
        or soup.select_one(".chapter-text")
        or soup.select_one("ol.breadcrumb li.active a")
    )
    return tag.get_text(strip=True) if tag else ""


def _chapter_number_from_url(base_url: str) -> int | None:
    m = _CHAPTER_NUM_RE.search(urlparse(base_url).path)
    return int(m.group(1)) if m else None


def _chapter_content(soup: BeautifulSoup) -> str:
    div = soup.select_one("#chapter-content") or soup.select_one("#chr-content")
    if not div:
        return ""
    return _parse_content_div(div)


def _parse_content_div(div: Tag) -> str:
    for tag in div.select("iframe, script, ins, #frame"):
        tag.decompose()
    paragraphs: list[str] = []
    for child in div.children:
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


def _next_url(soup: BeautifulSoup, base_url: str) -> str | None:
    btn = soup.select_one("#next_chap")
    if not btn or not btn.get("href") or btn.has_attr("disabled"):
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


def _chapter_breadcrumb(soup: BeautifulSoup) -> tuple[str, str]:
    book_title = ""
    tag = soup.select_one("a.truyen-title")
    if tag:
        book_title = tag.get_text(strip=True)
    else:
        crumbs = soup.select("ol.breadcrumb li")
        if len(crumbs) >= 2:
            link = crumbs[1].select_one("a")
            if link:
                book_title = link.get_text(strip=True)
    author = ""
    atag = soup.select_one('a[href*="/author/"]')
    if atag:
        author = atag.get_text(strip=True)
    return book_title, author


def _attr(tag: Tag | None, key: str) -> str:
    if tag is None:
        return ""
    val = tag.get(key, "")
    return str(val) if val else ""


def extract_novel_id(html: str) -> str | None:
    """NovelFull book id used by ``/ajax-chapter-option``."""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.select_one("[data-novel-id]")
    if tag is None:
        return None
    value = _attr(tag, "data-novel-id").strip()
    return value or None


def ajax_chapter_option_url(novel_id: str) -> str:
    return f"https://novelfull.net/ajax-chapter-option?novelId={novel_id}"


def toc_page_for_chapter(chapter_number: int, *, page_size: int = 50) -> int:
    """1-based NovelFull TOC page index (``?page=N``), ~50 chapters per page."""
    if chapter_number < 1:
        return 1
    return (chapter_number - 1) // page_size + 1


def book_toc_page_url(book_url: str, page: int) -> str:
    if page <= 1:
        return book_url
    joiner = "&" if "?" in book_url else "?"
    return f"{book_url}{joiner}page={page}"
