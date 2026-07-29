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
from app.modules.discovery.sources.novelfull_search import (
    novelfull_search_url,
    parse_novelfull_search,
)
from app.modules.discovery.sources.novellunar_search import (
    novellunar_request_headers,
    novellunar_search_url,
    parse_novellunar_search,
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


SOURCE_SEARCHERS: list[tuple[str, Searcher]] = [
    ("novelfull", search_novelfull),
    ("novelbin", search_novelbin),
    ("freewebnovel", search_freewebnovel),
    ("novellunar", search_novellunar),
]


async def search_all_sources(query: str) -> list[ExternalSearchHit]:
    """Run every source searcher; skip failures so one site cannot block others."""
    hits: list[ExternalSearchHit] = []
    for name, searcher in SOURCE_SEARCHERS:
        try:
            hits.extend(await searcher(query))
        except FetchError as exc:
            logger.warning("discovery search failed for %s: %s", name, exc)
        except Exception:
            logger.exception("discovery search crashed for %s", name)
    return hits
