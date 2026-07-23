"""Shared value objects for scraping adapters."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BookMetadata:
    """Metadata extracted from a book's info page."""

    title: str = ""
    author: str = ""
    cover_url: str = ""
    first_chapter_url: str = ""


@dataclass(frozen=True)
class ChapterData:
    """Parsed content from a single chapter page."""

    title: str = ""
    content: str = ""
    next_url: str | None = None
    book_title: str = ""
    book_author: str = ""
    chapter_number: int | None = None
    is_placeholder: bool = field(default=False)
