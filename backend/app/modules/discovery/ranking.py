"""Rank discovery sources (prefer richer chapter estimates)."""

from __future__ import annotations

from typing import Protocol


class _RankableSource(Protocol):
    chapter_count_estimate: int | None
    source: str


def source_rank_key(src: _RankableSource) -> tuple[int, int, str]:
    """Sort key: higher chapter estimate first; unknowns last; then source name."""
    estimate = src.chapter_count_estimate
    has_estimate = 0 if estimate is None else 1
    count = 0 if estimate is None else estimate
    return (has_estimate, count, src.source)


def rank_sources[T: _RankableSource](sources: list[T]) -> list[T]:
    """Return sources sorted best-first (most chapters, then name)."""
    return sorted(sources, key=source_rank_key, reverse=True)
