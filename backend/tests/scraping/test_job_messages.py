"""Unit tests for public scrape error copy."""

from __future__ import annotations

from app.modules.scraping.job_messages import public_scrape_error


def test_missing_greenlet_is_humanized() -> None:
    raw = (
        "1 validation error for ChapterRead updated_at Error extracting attribute: "
        "MissingGreenlet: greenlet_spawn has not been called"
    )
    out = public_scrape_error(raw)
    assert out is not None
    assert "MissingGreenlet" not in out
    assert "internal error" in out.lower()


def test_short_error_kept() -> None:
    assert public_scrape_error("Fetch timed out") == "Fetch timed out"


def test_none_passthrough() -> None:
    assert public_scrape_error(None) is None
