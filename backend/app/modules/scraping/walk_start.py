"""Resolve which chapter URL a scrape job should start walking from."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from app.core.fetcher import FetchError, fetch_html, post_form_html
from app.modules.scraping.adapters import novelfull as novelfull_adapter
from app.modules.scraping.adapters import ranobes as ranobes_adapter
from app.modules.scraping.adapters import scribblehub as scribblehub_adapter
from app.modules.scraping.registry import ALL_ALLOWED_HOSTS

_CHAPTER_DASH = re.compile(r"/chapter-(\d+)(?:-|\.|/|$)", re.IGNORECASE)
_NOVELLUNAR = re.compile(
    r"novellunar\.com/novel/([^/]+)/chapter/(\d+)",
    re.IGNORECASE,
)
_FREEWEB_SLUG = re.compile(r"/novel/([^/]+)", re.IGNORECASE)
_NOVELBIN_BOOK = re.compile(r"(https?://[^/]+/b/[^/]+)", re.IGNORECASE)
_NOVELBIN_SLUG = re.compile(r"/b/([^/]+)", re.IGNORECASE)
_NOVELFIRE_SLUG = re.compile(r"/book/([^/]+)", re.IGNORECASE)


def resolve_walk_start(adapter: object, requested_url: str, first_chapter_url: str) -> str:
    """Walk from the first chapter when the request URL is a book page.

    Chapter URLs (where ``derive_book_url`` succeeds) are used as-is so mid-book
    starts still work. Book pages have no chapter body, so using them as
    ``start_url`` finishes with 0 chapters scraped.
    """
    if not first_chapter_url:
        return requested_url
    derived = adapter.derive_book_url(requested_url)  # type: ignore[attr-defined]
    if derived is None:
        return first_chapter_url
    return requested_url


def resolve_job_start_url(
    adapter: object,
    requested_url: str,
    first_chapter_url: str,
    *,
    start_chapter: int | None,
    book_html: str | None = None,
    book_url: str | None = None,
) -> str:
    """Sync resolution: TOC already in hand, or construct a stable chapter URL."""
    base = resolve_walk_start(adapter, requested_url, first_chapter_url)
    chapter = 1 if start_chapter is None or start_chapter <= 1 else start_chapter
    if chapter <= 1:
        return _start_at_first_chapter(adapter, base, first_chapter_url, book_url, requested_url)
    toc_base = book_url or first_chapter_url or requested_url
    from_html = _sync_from_book_html(adapter, book_html, toc_base, chapter)
    if from_html:
        return from_html
    seed = first_chapter_url or book_url or base
    built = construct_chapter_url(adapter, seed, chapter)
    if built and chapter_number_from_url(built) == chapter:
        return built
    return built or base


def _start_at_first_chapter(
    adapter: object,
    base: str,
    first_chapter_url: str,
    book_url: str | None,
    requested_url: str,
) -> str:
    if chapter_number_from_url(base) is not None:
        return base
    # Book page with missing TOC link — still start at chapter 1 when the site
    # uses stable /chapter-N paths (freewebnovel, novelfire, …).
    seed = first_chapter_url or book_url or base or requested_url
    return construct_chapter_url(adapter, seed, 1) or base


def _sync_from_book_html(
    adapter: object, book_html: str | None, toc_base: str, start_chapter: int
) -> str | None:
    if not book_html:
        return None
    found = find_chapter_url_in_html(book_html, toc_base, start_chapter)
    if found:
        return found
    if getattr(adapter, "name", "") == "scribblehub":
        return scribblehub_adapter.find_chapter_in_toc(book_html, toc_base, start_chapter)
    return None


async def resolve_job_start_url_async(
    adapter: object,
    requested_url: str,
    first_chapter_url: str,
    *,
    start_chapter: int | None,
    book_html: str | None = None,
    book_url: str | None = None,
) -> str:
    """Resolve mid-book starts via construct/TOC/ajax — never relies on 1..N seeking."""
    base = resolve_job_start_url(
        adapter,
        requested_url,
        first_chapter_url,
        start_chapter=start_chapter,
        book_html=book_html,
        book_url=book_url,
    )
    if start_chapter is None or start_chapter <= 1:
        return base
    if chapter_number_from_url(base) == start_chapter:
        return base
    jumped = await _async_site_jump(
        getattr(adapter, "name", ""), book_html, book_url, start_chapter
    )
    return jumped or base


async def _async_site_jump(
    name: str,
    book_html: str | None,
    book_url: str | None,
    start_chapter: int,
) -> str | None:
    if name in {"novelfull", "novelbin"} and book_url and book_html:
        return await _ajax_or_toc_jump(name, book_html, book_url, start_chapter)
    if name == "ranobes" and book_url:
        return await _ranobes_toc_jump(book_url, start_chapter)
    if name == "scribblehub" and book_url and book_html:
        return await _scribblehub_toc_jump(book_html, book_url, start_chapter)
    return None


async def _ajax_or_toc_jump(
    site: str, book_html: str, book_url: str, start_chapter: int
) -> str | None:
    novel_id = novelfull_adapter.extract_novel_id(book_html)
    if novel_id:
        found = await _fetch_chapter_from_ajax(site, novel_id, book_url, start_chapter)
        if found:
            return found
    page = novelfull_adapter.toc_page_for_chapter(start_chapter)
    page_url = novelfull_adapter.book_toc_page_url(book_url, page)
    try:
        html = await fetch_html(page_url, ALL_ALLOWED_HOSTS)
    except FetchError:
        return None
    return find_chapter_url_in_html(html, book_url, start_chapter)


async def _fetch_chapter_from_ajax(
    site: str, novel_id: str, book_url: str, start_chapter: int
) -> str | None:
    origin = _site_origin(book_url, site)
    ajax_url = f"{origin}/ajax-chapter-option?novelId={novel_id}"
    try:
        html = await fetch_html(ajax_url, ALL_ALLOWED_HOSTS)
    except FetchError:
        return None
    return find_chapter_url_in_html(html, book_url, start_chapter)


async def _ranobes_toc_jump(book_url: str, start_chapter: int) -> str | None:
    html = await _ranobes_toc_html(book_url, start_chapter)
    if html is None:
        return None
    link = ranobes_adapter.find_chapter_link_in_toc(html, start_chapter)
    return urljoin(book_url, link) if link else None


async def _fetch_html_or_none(url: str) -> str | None:
    try:
        return await fetch_html(url, ALL_ALLOWED_HOSTS)
    except FetchError:
        return None


async def _ranobes_toc_html(book_url: str, start_chapter: int) -> str | None:
    index = ranobes_adapter.chapters_index_url(book_url)
    if not index:
        return None
    html = await _fetch_html_or_none(index)
    if html is None:
        return None
    data = ranobes_adapter.parse_toc_data(html)
    total = int(data.get("count_all") or 0) if data else 0
    page = ranobes_adapter.toc_page_for_chapter(start_chapter, total) if total else 1
    if page <= 1:
        return html
    page_url = ranobes_adapter.chapters_page_url(book_url, page)
    return await _fetch_html_or_none(page_url) if page_url else None


async def _scribblehub_toc_jump(book_html: str, book_url: str, start_chapter: int) -> str | None:
    mypostid = scribblehub_adapter.extract_mypostid(book_html)
    if not mypostid:
        return scribblehub_adapter.find_chapter_in_toc(book_html, book_url, start_chapter)
    parsed = urlparse(book_url)
    origin = f"{parsed.scheme or 'https'}://{parsed.netloc}"
    try:
        html = await post_form_html(
            scribblehub_adapter.toc_ajax_url(origin),
            ALL_ALLOWED_HOSTS,
            scribblehub_adapter.toc_ajax_form(mypostid),
        )
    except FetchError:
        return scribblehub_adapter.find_chapter_in_toc(book_html, book_url, start_chapter)
    return scribblehub_adapter.find_chapter_in_toc(html, book_url, start_chapter)


def _site_origin(book_url: str, site: str) -> str:
    parsed = urlparse(book_url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    if site == "novelbin":
        return "https://novelbin.com"
    return "https://novelfull.net"


def find_chapter_url_in_html(html: str, base_url: str, chapter_number: int) -> str | None:
    """Match a TOC / ajax-option link whose href encodes the chapter number."""
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.select("a[href], option[value]"):
        href = str(link.get("href") or link.get("value") or "")
        if not href or href.startswith(("#", "javascript:")):
            continue
        if chapter_number_from_url(href) != chapter_number:
            continue
        return urljoin(base_url, href)
    return None


def construct_chapter_url(
    adapter: object,
    seed_url: str,
    chapter_number: int,
) -> str | None:
    """Build a mid-book chapter URL for sites with stable chapter paths."""
    builders = {
        "novellunar": _novellunar_chapter,
        "freewebnovel": _freewebnovel_chapter,
        "novelbin": _novelbin_chapter,
        "novelfire": _novelfire_chapter,
    }
    builder = builders.get(getattr(adapter, "name", ""))
    return builder(seed_url, chapter_number) if builder else None


def chapter_number_from_url(url: str) -> int | None:
    """Best-effort chapter number encoded in a chapter URL path.

    ScribbleHub ``/chapter/{post_id}/`` ids are not sequential chapter numbers
    and must not match here.
    """
    lunar = _NOVELLUNAR.search(url)
    if lunar:
        return int(lunar.group(2))
    match = _CHAPTER_DASH.search(url)
    return int(match.group(1)) if match else None


def _novellunar_chapter(seed_url: str, chapter_number: int) -> str | None:
    match = _NOVELLUNAR.search(seed_url)
    slug_match = re.search(r"/novel/([^/]+)", urlparse(seed_url).path, re.IGNORECASE)
    slug = match.group(1) if match else (slug_match.group(1) if slug_match else None)
    if not slug:
        return None
    parsed = urlparse(seed_url)
    path = f"/novel/{slug}/chapter/{chapter_number}"
    return urlunparse((parsed.scheme or "https", parsed.netloc, path, "", "", ""))


def _freewebnovel_chapter(seed_url: str, chapter_number: int) -> str | None:
    match = _FREEWEB_SLUG.search(urlparse(seed_url).path)
    if not match:
        return None
    parsed = urlparse(seed_url)
    path = f"/novel/{match.group(1)}/chapter-{chapter_number}"
    return urlunparse((parsed.scheme or "https", parsed.netloc, path, "", "", ""))


def _novelbin_chapter(seed_url: str, chapter_number: int) -> str | None:
    book = _NOVELBIN_BOOK.search(seed_url)
    if book:
        return f"{book.group(1).rstrip('/')}/chapter-{chapter_number}"
    match = _NOVELBIN_SLUG.search(urlparse(seed_url).path)
    if not match:
        return None
    parsed = urlparse(seed_url)
    path = f"/b/{match.group(1)}/chapter-{chapter_number}"
    return urlunparse((parsed.scheme or "https", parsed.netloc, path, "", "", ""))


def _novelfire_chapter(seed_url: str, chapter_number: int) -> str | None:
    match = _NOVELFIRE_SLUG.search(urlparse(seed_url).path)
    if not match:
        return None
    parsed = urlparse(seed_url)
    path = f"/book/{match.group(1)}/chapter-{chapter_number}"
    return urlunparse((parsed.scheme or "https", parsed.netloc, path, "", "", ""))
