"""NovelFire.net scrape adapter — HTML parsing only."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag

from app.modules.scraping.types import BookMetadata, ChapterData

_BASE = "https://novelfire.net"
_BOOK_PATH = re.compile(r"/book/([^/]+)", re.IGNORECASE)
_NOVEL_PATH = re.compile(r"/novel/([^/]+)", re.IGNORECASE)
_CHAPTER_NUM = re.compile(r"/chapter-(\d+)(?:/|$)", re.IGNORECASE)
_MIRROR_HOSTS = ("novelfire.net", "novelphoenix.com")


def canonicalize_novelfire_url(url: str, *, base_url: str = _BASE) -> str:
    """Normalize NovelFire URLs to novelfire.net /book/{slug}/chapter-N."""
    absolute = urljoin(base_url, url.strip())
    parsed = urlparse(absolute)
    slug = _slug_from_path(parsed.path)
    if slug is None:
        return absolute
    chapter = _CHAPTER_NUM.search(parsed.path)
    path = f"/book/{slug}/chapter-{chapter.group(1)}" if chapter else f"/book/{slug}"
    return urlunparse(("https", "novelfire.net", path, "", "", ""))


def _slug_from_path(path: str) -> str | None:
    book = _BOOK_PATH.search(path)
    if book:
        return book.group(1)
    novel = _NOVEL_PATH.search(path)
    return novel.group(1) if novel else None


class NovelfireAdapter:
    """Deterministic parser for novelfire.net pages."""

    name = "novelfire"

    def matches(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return any(mirror in host for mirror in _MIRROR_HOSTS)

    def derive_book_url(self, chapter_url: str) -> str | None:
        canonical = canonicalize_novelfire_url(chapter_url)
        if not _CHAPTER_NUM.search(urlparse(canonical).path):
            return None
        slug = _slug_from_path(urlparse(canonical).path)
        if slug is None:
            return None
        return f"{_BASE}/book/{slug}"

    def parse_book_page(self, html: str, base_url: str) -> BookMetadata:
        soup = BeautifulSoup(html, "html.parser")
        return BookMetadata(
            title=_book_title(soup),
            author=_book_author(soup),
            cover_url=_book_cover(soup, base_url),
            first_chapter_url=_first_chapter(soup, base_url),
        )

    def parse_chapter_page(self, html: str, base_url: str) -> ChapterData:
        soup = BeautifulSoup(html, "html.parser")
        content = _chapter_content(soup)
        return ChapterData(
            title=_chapter_title(soup),
            content=content,
            next_url=_next_url(soup, base_url),
            book_title=_chapter_book_title(soup),
            book_author=_book_author(soup),
            chapter_number=_chapter_number_from_url(base_url),
            is_placeholder=not content.strip(),
        )


def _book_title(soup: BeautifulSoup) -> str:
    tag = soup.select_one("h1.novel-title, h1[itemprop='name'], h1")
    return tag.get_text(strip=True) if tag else ""


def _book_author(soup: BeautifulSoup) -> str:
    tag = soup.select_one('span[itemprop="author"]')
    return tag.get_text(strip=True) if tag else ""


def _book_cover(soup: BeautifulSoup, base_url: str) -> str:
    img = soup.select_one(".cover img, .novel-cover img, img[itemprop='image']")
    src = _attr(img, "data-src") or _attr(img, "src")
    return urljoin(base_url, src) if src else ""


def _first_chapter(soup: BeautifulSoup, base_url: str) -> str:
    for sel in ("a.button[href*='/chapter-']", "ul.chapter-list li a", "a[href*='/chapter-1']"):
        link = soup.select_one(sel)
        if link and link.get("href"):
            return canonicalize_novelfire_url(urljoin(base_url, str(link["href"])))
    return ""


def _chapter_title(soup: BeautifulSoup) -> str:
    tag = soup.select_one("span.chapter-title, h1, title")
    return tag.get_text(strip=True) if tag else ""


def _chapter_book_title(soup: BeautifulSoup) -> str:
    crumb = soup.select_one(".breadcrumb a[href*='/book/'], a.booktitle")
    if crumb:
        return crumb.get_text(strip=True)
    title = _chapter_title(soup)
    if " - " in title:
        return title.split(" - ", 1)[0].strip()
    return ""


def _chapter_number_from_url(base_url: str) -> int | None:
    match = _CHAPTER_NUM.search(urlparse(base_url).path)
    return int(match.group(1)) if match else None


def _chapter_content(soup: BeautifulSoup) -> str:
    article = soup.select_one("div#content")
    if not article:
        return ""
    for tag in article.select("script, iframe, ins, .ads, .ad"):
        tag.decompose()
    for el in list(article.find_all(True))[:5]:
        text = el.get_text(" ", strip=True)
        if re.match(r"(?i)^\s*chapter\s+\d+", text):
            el.decompose()
    paragraphs = [p.get_text(strip=True) for p in article.find_all("p") if p.get_text(strip=True)]
    if paragraphs:
        return "\n\n".join(paragraphs)
    return article.get_text("\n\n", strip=True)


def _next_url(soup: BeautifulSoup, base_url: str) -> str | None:
    for sel in ("a.chnav.next", "a.nextchap", "a[rel='next']"):
        link = soup.select_one(sel)
        href = _attr(link, "href") if link else ""
        if href and not href.startswith("javascript"):
            resolved = canonicalize_novelfire_url(urljoin(base_url, href))
            if resolved.rstrip("/") != canonicalize_novelfire_url(base_url).rstrip("/"):
                return resolved
    return None


def _attr(tag: Tag | None, key: str) -> str:
    if tag is None:
        return ""
    val = tag.get(key, "")
    return str(val) if val else ""
