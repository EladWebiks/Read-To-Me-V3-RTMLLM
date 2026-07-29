"""Unit tests for discovery source ranking."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from app.modules.discovery.ranking import rank_sources


@dataclass
class _Src:
    source: str
    chapter_count_estimate: int | None


@pytest.mark.unit
def test_rank_sources_prefers_higher_chapter_estimate() -> None:
    ranked = rank_sources(
        [
            _Src("novelfull", None),
            _Src("novellunar", 1200),
            _Src("novelbin", 400),
        ]
    )
    assert [s.source for s in ranked] == ["novellunar", "novelbin", "novelfull"]


@pytest.mark.unit
def test_rank_sources_unknowns_sort_after_known() -> None:
    ranked = rank_sources(
        [
            _Src("freewebnovel", None),
            _Src("novelfull", 10),
        ]
    )
    assert ranked[0].source == "novelfull"
    assert ranked[1].chapter_count_estimate is None
