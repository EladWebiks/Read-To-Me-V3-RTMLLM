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
            *[f"Title {i}" for i in range(40)],
        ]
    )
    assert capped[0] == "Against the Gods"
    assert capped[1] == "Martial Peak"
    assert len(capped) == 30


@pytest.mark.unit
def test_clamp_recommend_limit() -> None:
    assert clamp_recommend_limit(0) == 1
    assert clamp_recommend_limit(3) == 3
    assert clamp_recommend_limit(20) == 20
    assert clamp_recommend_limit(99) == 25


@pytest.mark.unit
def test_exclude_title_key_strips_articles() -> None:
    from app.modules.discovery.recommend import exclude_title_key

    assert exclude_title_key("The Desolate Era") == "desolate era"
    assert exclude_title_key("Desolate Era") == "desolate era"


@pytest.mark.unit
def test_exclude_title_key_maps_known_aliases() -> None:
    from app.modules.discovery.recommend import exclude_title_key

    assert exclude_title_key("Master of Gu") == exclude_title_key("Reverend Insanity")
    assert exclude_title_key("Xian Ni") == exclude_title_key("Renegade Immortal")


@pytest.mark.unit
def test_exclude_title_key_ignores_apostrophe_variants() -> None:
    from app.modules.discovery.recommend import exclude_title_key

    curly = "A Record of a Mortal\u2019s Journey to Immortality"
    straight = "A Record of a Mortal's Journey to Immortality"
    assert exclude_title_key(straight) == exclude_title_key(curly)


@pytest.mark.unit
def test_is_derivative_title_filters_fanfic_extensions() -> None:
    from app.modules.discovery.recommend import is_derivative_title

    canons = ["Martial Peak", "Desolate Era", "Against the Gods"]
    assert is_derivative_title("Martial Peak - Rise Of The Human Emperor", canons)
    assert is_derivative_title("Desolate Era: Hatching a Phoenix at the Beginning", canons)
    assert is_derivative_title("Cronus' system: Against the gods", canons)
    assert is_derivative_title("Dual Cultivation In Martial Peak", canons)
    assert not is_derivative_title("Martial Peak", canons)
    assert not is_derivative_title("True Martial World", canons)


@pytest.mark.unit
def test_dedupe_by_exclude_key_keeps_first() -> None:
    from app.modules.discovery.recommend import dedupe_by_exclude_key

    first = _book("Desolate Era")
    second = _book("The Desolate Era")
    second.normalized_title = "the desolate era"
    assert dedupe_by_exclude_key([first, second]) == [first]


@pytest.mark.unit
def test_passes_source_and_min_chapters() -> None:
    from app.modules.discovery.recommend import passes_source_and_chapters

    srcs = [_Src(800, "ranobes"), _Src(200, "novelfire")]
    assert passes_source_and_chapters(srcs, source="ranobes", min_chapters=500)
    assert not passes_source_and_chapters(srcs, source="scribblehub", min_chapters=500)
    assert not passes_source_and_chapters(
        [_Src(100, "ranobes")], source="ranobes", min_chapters=500
    )


@pytest.mark.unit
def test_passes_source_honors_exclude_sources() -> None:
    from app.modules.discovery.recommend import passes_source_and_chapters

    srcs = [_Src(800, "novellunar"), _Src(200, "novelfire")]
    assert not passes_source_and_chapters(
        srcs,
        source=None,
        min_chapters=None,
        exclude_sources=frozenset({"novelfire", "novellunar"}),
    )
    assert passes_source_and_chapters(
        srcs,
        source=None,
        min_chapters=None,
        exclude_sources=frozenset({"novelfire"}),
    )


@pytest.mark.unit
def test_prefer_source_rows_orders_matching_first() -> None:
    from app.modules.discovery.recommend import prefer_source_rows

    rows = [_Src(1, "novelfire"), _Src(2, "ranobes"), _Src(3, "novellunar")]
    ordered = prefer_source_rows(rows, "ranobes")
    assert ordered[0].source == "ranobes"


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
