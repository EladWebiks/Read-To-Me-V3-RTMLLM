"""FreeWebNovel.com scrape adapter — HTML parsing only."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag

from app.modules.scraping.types import BookMetadata, ChapterData

_CHAPTER_PATH_RE = re.compile(r"/novel/([^/]+)/chapter-\d+", re.IGNORECASE)
_CHAPTER_NUM_RE = re.compile(r"/chapter-(\d+)", re.IGNORECASE)


class FreewebnovelAdapter:
    """Deterministic parser for freewebnovel.com pages."""

    name = "freewebnovel"

    def matches(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return "freewebnovel.com" in host

    def derive_book_url(self, chapter_url: str) -> str | None:
        parsed = urlparse(chapter_url)
        m = _CHAPTER_PATH_RE.search(parsed.path)
        if not m:
            return None
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
        placeholder = _is_not_found(soup)
        if placeholder:
            return ChapterData(title="", content="", is_placeholder=True)
        title = _chapter_title(soup)
        number = _chapter_number_from_url(base_url)
        content = _article_content(soup)
        next_url = _next_url(soup, base_url)
        book_title, book_author = _chapter_meta(soup)
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
    og = soup.select_one('meta[property="og:title"]')
    if og:
        raw = _attr(og, "content")
        return raw.split(" - ")[0].strip()
    img = soup.select_one(".m-imgtxt img")
    return _attr(img, "alt").strip() if img else ""


def _book_author(soup: BeautifulSoup) -> str:
    og = soup.select_one('meta[property="og:novel:author"]')
    if og:
        return _attr(og, "content").strip()
    tag = soup.select_one('a[href*="/author/"]')
    return tag.get_text(strip=True) if tag else ""


def _book_cover(soup: BeautifulSoup, base_url: str) -> str:
    img = soup.select_one(".m-imgtxt img")
    url = _attr(img, "src") if img else ""
    if not url:
        og = soup.select_one("meta[property='og:image']")
        url = _attr(og, "content") if og else ""
    return urljoin(base_url, url) if url else ""


def _first_chapter(soup: BeautifulSoup, base_url: str) -> str:
    link = soup.select_one(".m-newest a")
    if not link:
        link = soup.select_one(".chapter-list a")
    if link and link.get("href"):
        return urljoin(base_url, str(link["href"]))
    return ""


def _is_not_found(soup: BeautifulSoup) -> bool:
    title_tag = soup.find("title")
    return bool(title_tag and "page not found" in title_tag.get_text(strip=True).lower())


def _chapter_title(soup: BeautifulSoup) -> str:
    span = soup.select_one("span.chapter")
    if span:
        return span.get_text(strip=True)
    links = soup.select(".m-read a[title], .crumb a[title]")
    for link in reversed(links):
        href = link.get("href", "")
        if "/chapter-" in str(href):
            return link.get_text(strip=True)
    return ""


def _chapter_number_from_url(base_url: str) -> int | None:
    m = _CHAPTER_NUM_RE.search(urlparse(base_url).path)
    return int(m.group(1)) if m else None


def _article_content(soup: BeautifulSoup) -> str:
    article = soup.select_one("#article")
    if not article:
        return ""
    for tag in article.select("subtxt, iframe, script, ins, .read-ads"):
        tag.decompose()
    paragraphs: list[str] = []
    for el in article.find_all(["p", "h4"]):
        text = el.get_text(strip=True)
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _next_url(soup: BeautifulSoup, base_url: str) -> str | None:
    btn = soup.select_one("#next_url")
    if not btn or not btn.get("href"):
        return None
    href = str(btn["href"])
    if not href or href.startswith("javascript"):
        return None
    resolved = urljoin(base_url, href)
    if resolved.rstrip("/") == base_url.rstrip("/"):
        return None
    return resolved


def _chapter_meta(soup: BeautifulSoup) -> tuple[str, str]:
    book_title = ""
    tit = soup.select_one("h1.tit a")
    if tit:
        book_title = tit.get_text(strip=True)
    author = ""
    og = soup.select_one('meta[property="og:novel:author"]')
    if og:
        author = _attr(og, "content").strip()
    if not author:
        tag = soup.select_one('a[href*="/author/"]')
        if tag:
            author = tag.get_text(strip=True)
    return book_title, author


def _attr(tag: Tag | None, key: str) -> str:
    if tag is None:
        return ""
    val = tag.get(key, "")
    return str(val) if val else ""
