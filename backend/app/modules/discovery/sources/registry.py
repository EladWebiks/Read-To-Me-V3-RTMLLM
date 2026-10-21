"""Registry of external discovery title searchers."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from app.core.fetcher import FetchError, fetch_html, post_form_html
from app.modules.discovery.sources.freewebnovel_search import (
    freewebnovel_search_form,
    freewebnovel_search_url,
    parse_freewebnovel_search,
)
from app.modules.discovery.sources.novelbin_search import (
    novelbin_search_url,
    parse_novelbin_search,
)
from app.modules.discovery.sources.novelfire_search import (
    novelfire_search_url,
    parse_novelfire_search,
)
from app.modules.discovery.sources.novelfull_search import (
    novelfull_search_url,
    parse_novelfull_search,
)
from app.modules.discovery.sources.novellunar_search import (
    novellunar_request_headers,
    novellunar_search_url,
    parse_novellunar_search,
)
from app.modules.discovery.sources.ranobes_search import (
    parse_ranobes_search,
    ranobes_search_url,
)
from app.modules.discovery.sources.scribblehub_search import (
    parse_scribblehub_search,
    scribblehub_search_url,
)
from app.modules.discovery.types import ExternalSearchHit
from app.modules.scraping.registry import ALL_ALLOWED_HOSTS

logger = logging.getLogger(__name__)

Searcher = Callable[[str], Awaitable[list[ExternalSearchHit]]]


async def search_novelfull(query: str) -> list[ExternalSearchHit]:
    html = await fetch_html(novelfull_search_url(query), ALL_ALLOWED_HOSTS)
    return parse_novelfull_search(html)


async def search_novelbin(query: str) -> list[ExternalSearchHit]:
    html = await fetch_html(novelbin_search_url(query), ALL_ALLOWED_HOSTS)
    return parse_novelbin_search(html)


async def search_freewebnovel(query: str) -> list[ExternalSearchHit]:
    html = await post_form_html(
        freewebnovel_search_url(),
        ALL_ALLOWED_HOSTS,
        freewebnovel_search_form(query),
    )
    return parse_freewebnovel_search(html)


async def search_novellunar(query: str) -> list[ExternalSearchHit]:
    payload = await fetch_html(
        novellunar_search_url(query),
        ALL_ALLOWED_HOSTS,
        headers=novellunar_request_headers(),
    )
    return parse_novellunar_search(payload)


async def search_novelfire(query: str) -> list[ExternalSearchHit]:
    html = await fetch_html(novelfire_search_url(query), ALL_ALLOWED_HOSTS)
    return parse_novelfire_search(html)


async def search_ranobes(query: str) -> list[ExternalSearchHit]:
    html = await fetch_html(ranobes_search_url(query), ALL_ALLOWED_HOSTS)
    return parse_ranobes_search(html)


async def search_scribblehub(query: str) -> list[ExternalSearchHit]:
    html = await fetch_html(scribblehub_search_url(query), ALL_ALLOWED_HOSTS)
    return parse_scribblehub_search(html)


SOURCE_SEARCHERS: list[tuple[str, Searcher]] = [
    ("novelfull", search_novelfull),
    ("novelbin", search_novelbin),
    ("freewebnovel", search_freewebnovel),
    ("novellunar", search_novellunar),
    ("novelfire", search_novelfire),
    ("ranobes", search_ranobes),
    ("scribblehub", search_scribblehub),
]


async def search_all_sources(
    query: str,
    *,
    sources: frozenset[str] | None = None,
) -> list[ExternalSearchHit]:
    """Run source searchers; optional ``sources`` restricts which sites run."""
    hits: list[ExternalSearchHit] = []
    for name, searcher in SOURCE_SEARCHERS:
        if sources is not None and name not in sources:
            continue
        try:
            hits.extend(await searcher(query))
        except FetchError as exc:
            logger.warning("discovery search failed for %s: %s", name, exc)
        except Exception:
            logger.exception("discovery search crashed for %s", name)
    return hits
