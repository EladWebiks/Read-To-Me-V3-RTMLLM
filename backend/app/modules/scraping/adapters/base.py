"""Adapter protocol — every site adapter must satisfy this."""

from __future__ import annotations

from typing import Protocol

from app.modules.scraping.types import BookMetadata, ChapterData


class ScrapeAdapter(Protocol):
    """Contract for deterministic per-site HTML parsers.

    Adapters MUST NOT make HTTP calls — they only parse pre-fetched HTML.
    """

    name: str

    def matches(self, url: str) -> bool:
        """Return True if *url* belongs to this source."""
        ...

    def derive_book_url(self, chapter_url: str) -> str | None:
        """Derive the book info page URL from a chapter URL, or None."""
        ...

    def parse_book_page(self, html: str, base_url: str) -> BookMetadata:
        """Parse a book info page into metadata."""
        ...

    def parse_chapter_page(self, html: str, base_url: str) -> ChapterData:
        """Parse a chapter page into content + navigation."""
        ...
