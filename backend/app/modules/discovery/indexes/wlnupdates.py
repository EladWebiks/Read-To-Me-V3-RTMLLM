"""WLNUpdates theme→title index client (JSON API, not a scrape adapter)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from app.core.fetcher import FetchError, post_json
from app.core.normalize import normalize_title
from app.modules.discovery.indexes.allowlist import INDEX_ALLOWED_HOSTS

logger = logging.getLogger(__name__)

_API_URL = "https://www.wlnupdates.com/api"
_CACHE_TTL_S = 3600.0
_MAX_MATCHES = 3
_MAX_TITLES = 10
_EXACT = 3
_PREFIX = 2
_CONTAINS = 1

_tag_cache: tuple[float, list[str]] | None = None
_genre_cache: tuple[float, list[str]] | None = None


@dataclass(frozen=True, slots=True)
class WlnTitleHit:
    """One title expanded from WLN for a theme query."""

    title: str
    themes: tuple[str, ...]


async def titles_from_themes(themes: list[str]) -> list[WlnTitleHit]:
    """Map free-text themes to titles via WLN (soft-fail if API is down)."""
    cleaned = [t.strip() for t in themes if t.strip()]
    if not cleaned:
        return []
    return await _titles_from_cleaned(cleaned)


async def _titles_from_cleaned(cleaned: list[str]) -> list[WlnTitleHit]:
    try:
        tags = await _enumerate("enumerate-tags")
        genres = await _enumerate("enumerate-genres")
        matched = match_theme_labels(cleaned, tags=tags, genres=genres)
        if not matched:
            return []
        rows = await _search_advanced(matched)
    except (FetchError, OSError, TimeoutError) as exc:
        logger.warning("wlnupdates theme search failed: %s", exc)
        return []
    except Exception as exc:
        # httpx HTTPStatusError and similar — soft-fail, never break recommend
        logger.warning("wlnupdates theme search failed: %s", exc)
        return []
    return _hits_from_rows(rows, cleaned)


def match_theme_labels(
    themes: list[str],
    *,
    tags: list[str],
    genres: list[str],
) -> dict[str, dict[str, str]]:
    """Pick up to _MAX_MATCHES tag/genre names for search-advanced."""
    tag_cat: dict[str, str] = {}
    genre_cat: dict[str, str] = {}
    scored: list[tuple[int, str, str]] = []
    for theme in themes:
        scored.extend(_score_labels(theme, tags, kind="tag"))
        scored.extend(_score_labels(theme, genres, kind="genre"))
    scored.sort(key=lambda row: (-row[0], row[1]))
    _fill_categories(scored, tag_cat, genre_cat)
    return _category_payload(tag_cat, genre_cat)


def extract_titles(rows: list[object]) -> list[str]:
    """Pull unique series titles from a search-advanced data list."""
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        title = _row_title(row)
        if title is None:
            continue
        key = normalize_title(title)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(title)
        if len(out) >= _MAX_TITLES:
            break
    return out


def clear_caches() -> None:
    """Test helper — drop enumerate caches."""
    global _tag_cache, _genre_cache
    _tag_cache = None
    _genre_cache = None


def _fill_categories(
    scored: list[tuple[int, str, str]],
    tag_cat: dict[str, str],
    genre_cat: dict[str, str],
) -> None:
    for _score, kind, label in scored:
        if len(tag_cat) + len(genre_cat) >= _MAX_MATCHES:
            return
        if kind == "tag" and label not in tag_cat:
            tag_cat[label] = "included"
        elif kind == "genre" and label not in genre_cat:
            genre_cat[label] = "included"


def _category_payload(
    tag_cat: dict[str, str],
    genre_cat: dict[str, str],
) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if tag_cat:
        out["tag-category"] = tag_cat
    if genre_cat:
        out["genre-category"] = genre_cat
    return out


def _row_title(row: object) -> str | None:
    if not isinstance(row, dict):
        return None
    title = row.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    return title.strip()


async def _enumerate(mode: str) -> list[str]:
    global _tag_cache, _genre_cache
    now = time.monotonic()
    cached = _cached_names(mode, now)
    if cached is not None:
        return cached
    payload = await post_json(_API_URL, INDEX_ALLOWED_HOSTS, {"mode": mode})
    if payload.get("error"):
        raise FetchError(str(payload.get("message") or f"wln {mode} error"))
    names = _parse_enumerate(payload.get("data"))
    if mode == "enumerate-tags":
        _tag_cache = (now, names)
    else:
        _genre_cache = (now, names)
    return names


def _cached_names(mode: str, now: float) -> list[str] | None:
    if mode == "enumerate-tags" and _tag_cache is not None and now - _tag_cache[0] < _CACHE_TTL_S:
        return _tag_cache[1]
    if (
        mode == "enumerate-genres"
        and _genre_cache is not None
        and now - _genre_cache[0] < _CACHE_TTL_S
    ):
        return _genre_cache[1]
    return None


async def _search_advanced(categories: dict[str, dict[str, str]]) -> list[object]:
    body: dict[str, object] = {
        "mode": "search-advanced",
        "series-type": {"Translated": "included"},
        "sort-mode": "update",
        "chapter-limits": [0, 0],
    }
    body.update(categories)
    payload = await post_json(_API_URL, INDEX_ALLOWED_HOSTS, body)
    if payload.get("error"):
        raise FetchError(str(payload.get("message") or "wln search-advanced error"))
    data = payload.get("data")
    return data if isinstance(data, list) else []


def _hits_from_rows(rows: list[object], themes: list[str]) -> list[WlnTitleHit]:
    theme_tuple = tuple(themes)
    return [WlnTitleHit(title=t, themes=theme_tuple) for t in extract_titles(rows)]


def _parse_enumerate(data: object) -> list[str]:
    if not isinstance(data, list):
        return []
    names: list[str] = []
    for item in data:
        if isinstance(item, (list, tuple)) and item and isinstance(item[0], str):
            names.append(item[0])
    return names


def _score_labels(
    theme: str,
    labels: list[str],
    *,
    kind: str,
) -> list[tuple[int, str, str]]:
    needle = _slug(theme)
    if not needle:
        return []
    out: list[tuple[int, str, str]] = []
    for label in labels:
        score = _label_score(needle, _slug(label))
        if score:
            out.append((score, kind, label))
    return out


def _label_score(needle: str, label: str) -> int:
    if not label:
        return 0
    if needle == label:
        return _EXACT
    if label.startswith(needle) or needle.startswith(label):
        return _PREFIX
    return _CONTAINS if needle in label or label in needle else 0


def _slug(text: str) -> str:
    return normalize_title(text).replace(" ", "-")
