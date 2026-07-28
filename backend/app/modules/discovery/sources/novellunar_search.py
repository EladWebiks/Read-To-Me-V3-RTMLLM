"""Parse NovelLunar search API JSON (no network)."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

from app.modules.discovery.types import ExternalSearchHit

_SOURCE = "novellunar"
_BASE = "https://novellunar.com"
_API = f"{_BASE}/api/novels/search"


def novellunar_search_url(query: str) -> str:
    """Build the NovelLunar JSON search URL."""
    return f"{_API}?{urlencode({'q': query})}"


def novellunar_request_headers() -> dict[str, str]:
    """Headers the API accepts for anonymous browser-like calls."""
    return {
        "Accept": "application/json",
        "Referer": f"{_BASE}/",
        "Origin": _BASE,
    }


def parse_novellunar_search(payload: str, *, base_url: str = _BASE) -> list[ExternalSearchHit]:
    """Extract title hits from NovelLunar ``/api/novels/search`` JSON."""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    rows = _rows(data)
    hits: list[ExternalSearchHit] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        slug = str(row.get("slug") or "").strip()
        if not title or not slug:
            continue
        chapters = row.get("totalChapters")
        estimate = int(chapters) if isinstance(chapters, int) else None
        hits.append(
            ExternalSearchHit(
                source=_SOURCE,
                title=title,
                author="",
                book_url=f"{base_url.rstrip('/')}/novel/{slug}",
                chapter_count_estimate=estimate,
            )
        )
    return hits


def _rows(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "results", "novels"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []
