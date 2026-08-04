"""Unit tests for discovery recommend helpers and batch bounds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.modules.discovery.models import DiscoveredBook
from app.modules.discovery.recommend import (
    cap_queries,
    clamp_recommend_limit,
    evidence_for,
    score_candidate,
    summary_keyword_queries,
)


@dataclass
class _Src:
    chapter_count_estimate: int | None
    source: str = "novelfull"


def _book(title: str, description: str = "") -> DiscoveredBook:
    now = datetime.now(UTC)
    return DiscoveredBook(
        id=uuid4(),
        title=title,
        normalized_title=title.lower(),
        author="Author",
        description=description,
        language="en",
        created_at=now,
        updated_at=now,
    )


@pytest.mark.unit
def test_cap_queries_dedupes_and_limits() -> None:
    capped = cap_queries(
        [
            "Against the Gods",
            "against the gods",
            "  Martial Peak  ",
            "",
            *[f"Title {i}" for i in range(20)],
        ]
    )
    assert capped[0] == "Against the Gods"
    assert capped[1] == "Martial Peak"
    assert len(capped) == 8


@pytest.mark.unit
def test_clamp_recommend_limit() -> None:
    assert clamp_recommend_limit(0) == 1
    assert clamp_recommend_limit(3) == 3
    assert clamp_recommend_limit(99) == 10


@pytest.mark.unit
def test_score_prefers_title_match_and_rich_sources() -> None:
    exact = _book("Martial Peak")
    weak = _book("Random Cultivation Tale", "martial arts")
    exact_score = score_candidate(
        exact,
        [_Src(100), _Src(50, "novelbin")],
        queries=["Martial Peak"],
        themes=set(),
    )
    weak_score = score_candidate(
        weak,
        [_Src(10)],
        queries=["Martial Peak"],
        themes={"cultivation"},
    )
    assert exact_score > weak_score


@pytest.mark.unit
def test_evidence_includes_query_and_theme() -> None:
    book = _book("Solo Leveling", "hunter gate dungeon")
    evidence = evidence_for(
        book,
        query_hits={book.normalized_title: ["Solo Leveling"]},
        themes=["dungeon"],
        index_notes={book.normalized_title: ["title research"]},
    )
    assert "matched query 'Solo Leveling'" in evidence
    assert "theme 'dungeon'" in evidence
    assert "title research" in evidence


@pytest.mark.unit
def test_summary_keyword_queries_reads_themes_and_tropes() -> None:
    assert summary_keyword_queries(
        {"themes": ["cultivation", "revenge"], "tropes": ["system"]}
    ) == ["cultivation", "revenge", "system"]


@pytest.mark.unit
def test_similar_candidate_titles_drops_lone_seed_with_themes() -> None:
    from app.modules.discovery.service import _similar_candidate_titles

    assert (
        _similar_candidate_titles(
            ["Against the Gods"],
            themes=["cultivation"],
            seed_norm=None,
        )
        == []
    )
    assert _similar_candidate_titles(
        ["Martial World", "Peerless Martial God"],
        themes=["cultivation"],
        seed_norm="against the gods",
    ) == ["Martial World", "Peerless Martial God"]
