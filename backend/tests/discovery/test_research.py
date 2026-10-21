"""Unit tests for discovery title research helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.modules.discovery.exceptions import DiscoveryRecommendError
from app.modules.discovery.indexes.research import (
    ResearchTitleHit,
    TitleResearchSpec,
    _hits_from_payload,
    _request,
    _ResearchTitle,
    _ResearchTitles,
    titles_from_research,
)
from app.modules.llm.exceptions import LlmRateLimitError


def test_hits_keep_research_reason_in_note() -> None:
    hits = _hits_from_payload(
        _ResearchTitles(
            titles=[
                _ResearchTitle(
                    title="I Shall Seal the Heavens",
                    reason="Same cultivation revenge arc style as the seed",
                ),
                _ResearchTitle(title="Against the Gods", reason="seed itself"),
            ]
        ),
        seed_title="Against the Gods",
        limit=5,
    )
    assert hits == [
        ResearchTitleHit(
            title="I Shall Seal the Heavens",
            note="title research: Same cultivation revenge arc style as the seed",
        )
    ]


def test_hits_support_custom_note_prefix() -> None:
    hits = _hits_from_payload(
        _ResearchTitles(titles=[_ResearchTitle(title="Martial Peak", reason="cultivation")]),
        seed_title=None,
        limit=3,
        note_prefix="title research",
    )
    assert hits[0].note == "title research: cultivation"


def test_research_request_disables_web_search() -> None:
    req = _request(["cultivation"], "Against the Gods", limit=5, exclude_titles=[])
    assert req.use_web_search is False
    assert req.response_model is _ResearchTitles


@pytest.mark.unit
@pytest.mark.asyncio
async def test_titles_from_research_surfaces_llm_errors() -> None:
    llm = MagicMock()
    llm.generate_structured = AsyncMock(
        side_effect=LlmRateLimitError("Too many AI requests right now.")
    )
    with pytest.raises(DiscoveryRecommendError, match="Title research failed"):
        await titles_from_research(
            llm,
            user_id=uuid4(),
            spec=TitleResearchSpec(themes=("cultivation",), seed_title=None),
        )
