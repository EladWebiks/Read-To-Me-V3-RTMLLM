"""Unit tests for recommend follow-up exclude merging."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.modules.discovery.recommend import exclude_title_key
from app.modules.tools.definitions.recommend_excludes import (
    merge_exclude_titles,
    prior_recommend_exclude_titles,
    titles_from_assistant_text,
    titles_from_recommend_output,
)


@pytest.mark.unit
def test_exclude_title_key_strips_articles() -> None:
    assert exclude_title_key("The Desolate Era") == exclude_title_key("Desolate Era")
    assert exclude_title_key("A Will Eternal") == "will eternal"


@pytest.mark.unit
def test_exclude_title_key_aliases() -> None:
    assert exclude_title_key("Master of Gu") == "reverend insanity"
    assert exclude_title_key("Reverend Insanity") == "reverend insanity"


@pytest.mark.unit
def test_titles_from_recommend_output() -> None:
    titles = titles_from_recommend_output(
        {
            "results": [
                {"title": "Martial Peak"},
                {"title": "  Coiling Dragon  "},
                {"book": {"title": "Legacy Nested"}},
                {"book": {}},
                "skip",
            ]
        }
    )
    assert titles == ["Martial Peak", "Coiling Dragon", "Legacy Nested"]


@pytest.mark.unit
def test_titles_from_assistant_text() -> None:
    text = (
        "Here are suggestions:\n"
        "Martial God Asura by Kindhearted Bee (~6,517 chapters)\n"
        "- Library of Heaven's Path by Heng Sao Tian Ya (2,382 chapters)\n"
        "- True Martial World | Cocooned Cow | 1711 ch on supported sites (novelfull)\n"
        "Would you like to import any of these?"
    )
    titles = titles_from_assistant_text(text)
    assert "Martial God Asura" in titles
    assert "Library of Heaven's Path" in titles
    assert "True Martial World" in titles


@pytest.mark.unit
def test_merge_exclude_titles_dedupes() -> None:
    merged = merge_exclude_titles(
        ["The Desolate Era", "Martial Peak"],
        ["Desolate Era", "Coiling Dragon"],
    )
    assert merged == ["The Desolate Era", "Martial Peak", "Coiling Dragon"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_prior_recommend_exclude_titles_merges_tool_and_chat() -> None:
    user_id = uuid4()
    conversation_id = uuid4()
    conv = MagicMock()
    conv.created_at = datetime(2026, 1, 1, tzinfo=UTC)

    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_result(conv),
            _scalars_result(
                [
                    {
                        "results": [
                            {"book": {"title": "Martial Peak"}},
                        ]
                    }
                ]
            ),
            _scalars_result(
                [
                    "Coiling Dragon by I Eat Tomatoes (~808 chapters)\n",
                ]
            ),
        ]
    )

    titles = await prior_recommend_exclude_titles(
        session,
        user_id=user_id,
        conversation_id=conversation_id,
    )
    assert titles == ["Martial Peak", "Coiling Dragon"]


def _scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _scalars_result(values: list[object]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result
