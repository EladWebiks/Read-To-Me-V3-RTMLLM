"""Unit tests for discovery chapter-estimate merging."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.modules.discovery.schemas import BookSourceRead, DiscoveredBookRead
from app.modules.discovery.service import (
    _MIN_RELIABLE_CHAPTER_ESTIMATE,
    _scrapable_chapters,
    better_chapter_estimate,
)


@pytest.mark.unit
def test_better_chapter_estimate_never_decreases() -> None:
    assert better_chapter_estimate(1500, 15) == 1500
    assert better_chapter_estimate(15, 1500) == 1500
    assert better_chapter_estimate(None, 15) == 15
    assert better_chapter_estimate(15, None) == 15
    assert better_chapter_estimate(None, None) is None


@pytest.mark.unit
def test_scrapable_chapters_hides_thin_listings() -> None:
    book = _book_read(estimates=[15, 45])
    assert _scrapable_chapters(book) is None
    book = _book_read(estimates=[15, _MIN_RELIABLE_CHAPTER_ESTIMATE])
    assert _scrapable_chapters(book) == _MIN_RELIABLE_CHAPTER_ESTIMATE
    book = _book_read(estimates=[2334])
    assert _scrapable_chapters(book) == 2334


@pytest.mark.unit
def test_scrapable_chapters_prefers_named_source() -> None:
    now = datetime.now(UTC)
    book = DiscoveredBookRead(
        id=uuid4(),
        title="X",
        author="A",
        description="",
        language="en",
        sources=[
            BookSourceRead(
                id=uuid4(),
                source="novelfire",
                book_url="https://novelfire.net/a",
                first_chapter_url="https://novelfire.net/a/1",
                chapter_count_estimate=900,
                created_at=now,
                updated_at=now,
            ),
            BookSourceRead(
                id=uuid4(),
                source="ranobes",
                book_url="https://ranobes.top/novels/1.html",
                first_chapter_url="",
                chapter_count_estimate=1200,
                created_at=now,
                updated_at=now,
            ),
        ],
        created_at=now,
        updated_at=now,
    )
    assert _scrapable_chapters(book, preferred="ranobes") == 1200


def _book_read(*, estimates: list[int]) -> DiscoveredBookRead:
    now = datetime.now(UTC)
    sources = [
        BookSourceRead(
            id=uuid4(),
            source=f"src{i}",
            book_url=f"https://example.com/{i}",
            first_chapter_url=f"https://example.com/{i}/1",
            chapter_count_estimate=n,
            created_at=now,
            updated_at=now,
        )
        for i, n in enumerate(estimates)
    ]
    return DiscoveredBookRead(
        id=uuid4(),
        title="Tales of Demons and Gods",
        author="Mad Snail",
        description="",
        language="en",
        sources=sources,
        created_at=now,
        updated_at=now,
    )
