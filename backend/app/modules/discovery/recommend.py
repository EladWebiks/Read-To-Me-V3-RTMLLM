"""Bounded recommend ranking and query helpers."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol

from app.core.normalize import normalize_title
from app.modules.discovery.models import DiscoveredBook


class _ScoredSource(Protocol):
    chapter_count_estimate: int | None


_MAX_QUERIES = 8
_MIN_TOKEN_LEN = 3
_EXACT_MATCH = 3
_PARTIAL_MATCH = 2
_TOKEN_MATCH = 1
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "in",
        "on",
        "to",
        "for",
        "with",
        "from",
        "by",
        "is",
        "are",
        "as",
        "at",
        "this",
        "that",
        "book",
        "novel",
        "story",
    }
)
_WORD_RE = re.compile(r"[a-z0-9']+")


def clamp_recommend_limit(limit: int) -> int:
    """Clamp result count to the recommend contract (1-10)."""
    return max(1, min(limit, 10))


def cap_queries(queries: list[str]) -> list[str]:
    """Dedupe case-insensitively and hard-cap fan-out size."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in queries:
        cleaned = " ".join(raw.split()).strip()
        if not cleaned:
            continue
        key = normalize_title(cleaned)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
        if len(out) >= _MAX_QUERIES:
            break
    return out


def theme_tokens(themes: list[str]) -> set[str]:
    """Normalize theme strings into tokens for overlap scoring."""
    tokens: set[str] = set()
    for theme in themes:
        tokens.update(_significant_tokens(theme))
    return tokens


def summary_keyword_queries(structured: dict[str, object] | None) -> list[str]:
    """Pull short searchable phrases from a cached summary payload."""
    if not structured:
        return []
    out: list[str] = []
    for key in ("themes", "tropes"):
        values = structured.get(key)
        if not isinstance(values, list):
            continue
        for item in values:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
    return out[:4]


def score_candidate(
    book: DiscoveredBook,
    sources: Sequence[_ScoredSource],
    *,
    queries: list[str],
    themes: set[str],
) -> tuple[int, int, int, int]:
    """Higher is better: title match, sources, chapters, theme overlap."""
    title_score = max((_title_match(book.normalized_title, q) for q in queries), default=0)
    source_count = len(sources)
    chapters = max((s.chapter_count_estimate or 0 for s in sources), default=0)
    haystack = f"{book.normalized_title} {normalize_title(book.description)}"
    theme_hits = sum(1 for token in themes if token in haystack)
    return (title_score, source_count, chapters, theme_hits)


def evidence_for(
    book: DiscoveredBook,
    *,
    query_hits: dict[str, list[str]],
    themes: list[str],
    index_notes: dict[str, list[str]] | None = None,
) -> list[str]:
    """Human-readable match reasons for one candidate."""
    reasons = list(query_hits.get(book.normalized_title, []))
    labeled = [f"matched query '{q}'" for q in reasons]
    for note in (index_notes or {}).get(book.normalized_title, []):
        if note not in labeled:
            labeled.append(note)
    haystack = f"{book.normalized_title} {normalize_title(book.description)}"
    for theme in themes:
        tokens = _significant_tokens(theme)
        if tokens and all(token in haystack for token in tokens):
            label = f"theme '{theme.strip()}'"
            if label not in labeled:
                labeled.append(label)
    if not labeled:
        labeled.append("source listing")
    return labeled


def _title_match(normalized_book: str, query: str) -> int:
    needle = normalize_title(query)
    if not needle:
        return 0
    if normalized_book == needle:
        return _EXACT_MATCH
    if needle in normalized_book or normalized_book in needle:
        return _PARTIAL_MATCH
    return _token_overlap_score(normalized_book, needle)


def _token_overlap_score(normalized_book: str, needle: str) -> int:
    book_tokens = set(_significant_tokens(normalized_book))
    query_tokens = set(_significant_tokens(needle))
    if not query_tokens:
        return 0
    overlap = len(book_tokens & query_tokens)
    if overlap == len(query_tokens):
        return _PARTIAL_MATCH
    if overlap:
        return _TOKEN_MATCH
    return 0


def _significant_tokens(text: str) -> list[str]:
    return [
        w
        for w in _WORD_RE.findall(normalize_title(text))
        if w not in _STOPWORDS and len(w) >= _MIN_TOKEN_LEN
    ]
