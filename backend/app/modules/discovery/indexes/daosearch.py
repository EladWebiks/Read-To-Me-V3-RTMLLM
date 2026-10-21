"""DaoSearch REST index — soft backup theme→title (not a scrape adapter)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlencode

from app.core.fetcher import get_json
from app.core.normalize import normalize_title
from app.modules.discovery.indexes.allowlist import INDEX_ALLOWED_HOSTS

logger = logging.getLogger(__name__)

_BASE = "https://daosearch.io/api/v1"
_MAX_TITLES = 10
_MAX_GENRES = 2
_EXACT = 3
_PREFIX = 2
_CONTAINS = 1


@dataclass(frozen=True, slots=True)
class DaoTitleHit:
    """One title from DaoSearch genre browse."""

    title: str
    themes: tuple[str, ...]


async def titles_from_themes(themes: list[str], *, limit: int = _MAX_TITLES) -> list[DaoTitleHit]:
    """Map free-text themes to popular DaoSearch titles (soft-fail)."""
    cleaned = [t.strip() for t in themes if t.strip()]
    if not cleaned:
        return []
    try:
        return await _browse_cleaned(cleaned, limit=limit)
    except Exception as exc:
        logger.warning("daosearch theme browse failed: %s", exc)
        return []


async def _browse_cleaned(cleaned: list[str], *, limit: int) -> list[DaoTitleHit]:
    genres = await _list_genres()
    matched = _match_genres(cleaned, genres)
    if not matched:
        return []
    return await _titles_for_genres(matched, limit=limit)


async def _list_genres() -> list[tuple[int, str]]:
    payload = await get_json(f"{_BASE}/genres", INDEX_ALLOWED_HOSTS)
    rows = payload.get("data")
    if not isinstance(rows, list):
        return []
    out: list[tuple[int, str]] = []
    for row in rows:
        parsed = _parse_genre_row(row)
        if parsed is not None:
            out.append(parsed)
    return out


def _parse_genre_row(row: object) -> tuple[int, str] | None:
    if not isinstance(row, dict):
        return None
    gid = row.get("id")
    name = row.get("nameTranslated") or row.get("name")
    if isinstance(gid, int) and isinstance(name, str) and name.strip():
        return gid, name.strip()
    return None


def _match_genres(
    themes: list[str],
    genres: list[tuple[int, str]],
) -> list[tuple[int, str]]:
    scored = _score_genre_matches(themes, genres)
    scored.sort(key=lambda row: (-row[0], row[2]))
    return _dedupe_genres(scored)


def _score_genre_matches(
    themes: list[str],
    genres: list[tuple[int, str]],
) -> list[tuple[int, int, str]]:
    scored: list[tuple[int, int, str]] = []
    for theme in themes:
        needle = _slug(theme)
        if not needle:
            continue
        scored.extend(
            (score, gid, name)
            for gid, name in genres
            if (score := _label_score(needle, _slug(name)))
        )
    return scored


def _dedupe_genres(scored: list[tuple[int, int, str]]) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    seen: set[int] = set()
    for _score, gid, name in scored:
        if gid in seen:
            continue
        seen.add(gid)
        out.append((gid, name))
        if len(out) >= _MAX_GENRES:
            break
    return out


async def _titles_for_genres(
    matched: list[tuple[int, str]],
    *,
    limit: int,
) -> list[DaoTitleHit]:
    out: list[DaoTitleHit] = []
    seen: set[str] = set()
    for gid, genre_name in matched:
        query = urlencode({"genre": gid, "sort": "popularity", "limit": min(limit, 50)})
        payload = await get_json(f"{_BASE}/books?{query}", INDEX_ALLOWED_HOSTS)
        _consume_book_rows(payload.get("data"), genre_name, out, seen, limit=limit)
        if len(out) >= limit:
            break
    return out


def _consume_book_rows(
    rows: object,
    genre_name: str,
    out: list[DaoTitleHit],
    seen: set[str],
    *,
    limit: int,
) -> None:
    if not isinstance(rows, list):
        return
    for row in rows:
        title = _row_title(row)
        if title is None:
            continue
        key = normalize_title(title)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(DaoTitleHit(title=title, themes=(genre_name,)))
        if len(out) >= limit:
            return


def _row_title(row: object) -> str | None:
    if not isinstance(row, dict):
        return None
    for key in ("titleTranslated", "title"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


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
