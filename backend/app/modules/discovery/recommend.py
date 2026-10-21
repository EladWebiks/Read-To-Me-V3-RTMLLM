"""Bounded recommend ranking and query helpers."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol

from app.core.normalize import normalize_title
from app.modules.discovery.models import DiscoveredBook


class _ScoredSource(Protocol):
    chapter_count_estimate: int | None
    source: str


_MAX_QUERIES = 30
_MIN_TOKEN_LEN = 3
_EXACT_MATCH = 3
_PARTIAL_MATCH = 2
_TOKEN_MATCH = 1
_MAX_RECOMMEND_LIMIT = 25
# Alternate English titles → canonical key (after article strip).
_TITLE_ALIASES: dict[str, str] = {
    "master of gu": "reverend insanity",
    "xian ni": "renegade immortal",
    "ze tian ji": "way of choices",
    "stellar transformations": "stellar transformation",
}
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
# Straight, curly, and prime-like apostrophes commonly seen in titles.
_APOSTROPHE_RE = re.compile("['\u2019\u2032`]")
_MIN_CANON_LEN = 8
_EXTENSION_SLACK = 8
_DERIV_EXTRA = 3


def clamp_recommend_limit(limit: int) -> int:
    """Clamp result count to the recommend contract (1-25)."""
    return max(1, min(limit, _MAX_RECOMMEND_LIMIT))


def exclude_title_key(title: str) -> str:
    """Normalize a title for exclude/dedupe (articles, apostrophes, aliases)."""
    key = _APOSTROPHE_RE.sub("", normalize_title(title))
    for prefix in ("the ", "a ", "an "):
        if key.startswith(prefix):
            key = key[len(prefix) :]
            break
    return _TITLE_ALIASES.get(key, key)


def is_derivative_title(candidate: str, canon_titles: Sequence[str]) -> bool:
    """True when candidate is a fanfic/spinoff of a shorter canonical title."""
    cand = exclude_title_key(candidate)
    if not cand:
        return False
    canons = {exclude_title_key(t) for t in canon_titles if t.strip()}
    if cand in canons:
        return False
    return any(_extends_canon(cand, canon) for canon in canons)


def _extends_canon(cand: str, canon: str) -> bool:
    if len(canon) < _MIN_CANON_LEN:
        return False
    if cand.startswith((f"{canon} ", f"{canon}:")):
        return True
    if cand.endswith(f" {canon}") or f": {canon}" in cand or f":{canon}" in cand:
        return True
    return f" {canon} " in f" {cand} " and len(cand) > len(canon) + _DERIV_EXTRA


def dedupe_by_exclude_key(books: Sequence[DiscoveredBook]) -> list[DiscoveredBook]:
    """Keep first book per exclude key (caller should pass best-first order)."""
    seen: set[str] = set()
    out: list[DiscoveredBook] = []
    for book in books:
        key = exclude_title_key(book.normalized_title)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(book)
    return out


def matches_recommend_query(book_title: str, queries: Sequence[str]) -> bool:
    """Recommend results must match a researched/query title, not fuzzy lookalikes."""
    book_key = exclude_title_key(book_title)
    return any(exclude_title_key(q) == book_key for q in queries if q.strip())


def prefer_source_rows[T](sources: Sequence[T], preferred: str | None) -> list[T]:
    """Move rows matching ``preferred`` source name to the front."""
    if not preferred:
        return list(sources)
    matched = [s for s in sources if getattr(s, "source", None) == preferred]
    rest = [s for s in sources if getattr(s, "source", None) != preferred]
    return [*matched, *rest]


def without_excluded_sources[T](sources: Sequence[T], excluded: frozenset[str]) -> list[T]:
    """Drop sources whose name is in ``excluded`` (lowercased names)."""
    if not excluded:
        return list(sources)
    return [s for s in sources if getattr(s, "source", None) not in excluded]


def source_chapter_estimate(
    sources: Sequence[_ScoredSource],
    *,
    preferred: str | None = None,
) -> int | None:
    """Best chapter estimate, preferring a named source when it has a count."""
    if preferred:
        for src in sources:
            if src.source == preferred and src.chapter_count_estimate:
                return src.chapter_count_estimate
    estimates = [s.chapter_count_estimate for s in sources if s.chapter_count_estimate]
    return max(estimates) if estimates else None


def passes_source_and_chapters(
    sources: Sequence[_ScoredSource],
    *,
    source: str | None,
    min_chapters: int | None,
    exclude_sources: frozenset[str] = frozenset(),
) -> bool:
    """True when optional source membership and chapter floor are satisfied."""
    usable = without_excluded_sources(sources, exclude_sources)
    if not usable:
        return False
    if source and not any(s.source == source for s in usable):
        return False
    if min_chapters is None:
        return True
    best = source_chapter_estimate(usable, preferred=source) or 0
    if best <= 0:
        best = max((s.chapter_count_estimate or 0 for s in usable), default=0)
    return best >= min_chapters


def cap_queries(queries: list[str], *, max_queries: int = _MAX_QUERIES) -> list[str]:
    """Dedupe case-insensitively and hard-cap fan-out size."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in queries:
        cleaned = " ".join(raw.split()).strip()
        if not cleaned:
            continue
        key = exclude_title_key(cleaned)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
        if len(out) >= max_queries:
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
    if not needle or _is_noisy_extension(normalized_book, needle):
        return 0
    if exclude_title_key(normalized_book) == exclude_title_key(needle):
        return _EXACT_MATCH
    if needle in normalized_book or normalized_book in needle:
        return _PARTIAL_MATCH
    return _token_overlap_score(normalized_book, needle)


def _is_noisy_extension(normalized_book: str, needle: str) -> bool:
    return len(normalized_book) > len(needle) + _EXTENSION_SLACK and needle in normalized_book


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
