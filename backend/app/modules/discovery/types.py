"""Discovery search hit before persistence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExternalSearchHit:
    """One title result from a source search page."""

    source: str
    title: str
    author: str
    book_url: str
    first_chapter_url: str = ""
    chapter_count_estimate: int | None = None
