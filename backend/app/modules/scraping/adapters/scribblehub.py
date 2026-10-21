"""ScribbleHub.com scrape adapter — HTML parsing only."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag

from app.modules.scraping.types import BookMetadata, ChapterData

_READ = re.compile(r"/read/(\d+)-([^/]+)/chapter/(\d+)/?", re.IGNORECASE)
_CHAPTER_TITLE_NUM = re.compile(r"(?i)^\s*chapter\s*(\d+)")


class ScribblehubAdapter:
    """Deterministic parser for scribblehub.com series/chapter pages."""

    name = "scribblehub"

    def matches(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return "scribblehub.com" in host

    def derive_book_url(self, chapter_url: str) -> str | None:
        parsed = urlparse(chapter_url)
        match = _READ.search(parsed.path)
        if not match:
            return None
        series_id, slug = match.group(1), match.group(2)
        path = f"/series/{series_id}/{slug}/"
        return urlunparse((parsed.scheme or "https", parsed.netloc, path, "", "", ""))

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


def extract_mypostid(html: str) -> str | None:
    """Series post id used by the TOC ajax endpoint."""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.select_one("input#mypostid[value]")
    if tag and tag.get("value"):
        return str(tag["value"])
    return None


def toc_ajax_url(origin: str) -> str:
    """WordPress admin-ajax endpoint for chapter listings."""
    return urljoin(origin.rstrip("/") + "/", "wp-admin/admin-ajax.php")


def toc_ajax_form(mypostid: str) -> dict[str, str]:
    """Form body that returns the full TOC (pagenum=-1)."""
    return {
        "action": "wi_getreleases_pagination",
        "pagenum": "-1",
        "mypostid": mypostid,
    }


def chapter_links_from_toc_html(html: str, base_url: str) -> list[str]:
    """Ordered oldest→newest chapter URLs from a TOC ajax/HTML fragment."""
    soup = BeautifulSoup(html, "html.parser")
    links = soup.select("a.toc_a, .toc_ol a, a[href*='/chapter/']")
    hrefs: list[str] = []
    seen: set[str] = set()
    for link in links:
        href = str(link.get("href") or "")
        if not href or "/chapter/" not in href:
            continue
        absolute = urljoin(base_url, href)
        if absolute in seen:
            continue
        seen.add(absolute)
        hrefs.append(absolute)
    # ScribbleHub TOC is newest-first; walk oldest→newest.
    return list(reversed(hrefs))


def find_chapter_in_toc(html: str, base_url: str, chapter_number: int) -> str | None:
    """Pick the Nth chapter (1-based) from a TOC listing."""
    ordered = chapter_links_from_toc_html(html, base_url)
    if 1 <= chapter_number <= len(ordered):
        return ordered[chapter_number - 1]
    return None


def _book_title(soup: BeautifulSoup) -> str:
    tag = soup.select_one(".fic_title, h1.fic_title, h1")
    return tag.get_text(strip=True) if tag else ""


def _book_author(soup: BeautifulSoup) -> str:
    tag = soup.select_one(".auth_name_fic, span.auth_name_fic, a.auth_name_fic")
    return tag.get_text(strip=True) if tag else ""


def _book_cover(soup: BeautifulSoup, base_url: str) -> str:
    img = soup.select_one(".fic_image img, .property_feature img")
    src = _attr(img, "src")
    return urljoin(base_url, src) if src else ""


def _first_chapter(soup: BeautifulSoup, base_url: str) -> str:
    links = soup.select("a.toc_a, .toc_ol a[href*='/chapter/']")
    for link in links:
        text = link.get_text(" ", strip=True)
        if _CHAPTER_TITLE_NUM.match(text) and _number_from_title(text) == 1:
            return urljoin(base_url, str(link["href"]))
    # Newest-first TOC: first chapter is the last link on the page.
    if links and links[-1].get("href"):
        return urljoin(base_url, str(links[-1]["href"]))
    return ""


def _chapter_title(soup: BeautifulSoup) -> str:
    tag = soup.select_one(".chapter-title, h1.chapter-title, div.chapter-title, h1")
    return tag.get_text(strip=True) if tag else ""


def _chapter_book_title(soup: BeautifulSoup) -> str:
    crumb = soup.select_one(".s_breadcrumb a[href*='/series/'], #chp_contents a[href*='/series/']")
    if crumb:
        return crumb.get_text(strip=True)
    return _book_title(soup)


def _chapter_content(soup: BeautifulSoup) -> str:
    article = soup.select_one("#chp_raw, div.chp_raw, #chp_contents")
    if not article:
        return ""
    for tag in article.select(
        "script, iframe, .wi_authornotes, .spdiv, .chp_stats_feature, "
        ".modern-footnotes-footnote, .modern-footnotes-footnote__note"
    ):
        tag.decompose()
    paragraphs = [p.get_text(strip=True) for p in article.find_all("p") if p.get_text(strip=True)]
    if paragraphs:
        return "\n\n".join(paragraphs)
    return article.get_text("\n\n", strip=True)


def _next_url(soup: BeautifulSoup, base_url: str) -> str | None:
    for link in soup.select("a.btn-next, a[rel='next'], a"):
        text = link.get_text(" ", strip=True).lower()
        classes = " ".join(link.get("class") or []).lower()
        if "next" not in text and "btn-next" not in classes and "next_page" not in classes:
            continue
        href = _attr(link, "href")
        if not href or href.startswith("javascript"):
            continue
        resolved = urljoin(base_url, href)
        if "/chapter/" in resolved and resolved.rstrip("/") != base_url.rstrip("/"):
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
