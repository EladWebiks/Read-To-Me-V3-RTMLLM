"""Unit tests for WLNUpdates theme→title helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from app.modules.discovery.indexes.wlnupdates import (
    clear_caches,
    extract_titles,
    match_theme_labels,
    titles_from_themes,
)

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "discovery"


@pytest.fixture(autouse=True)
def _clear_wln_cache() -> None:
    clear_caches()


@pytest.mark.unit
def test_match_theme_labels_prefers_exact_tags() -> None:
    tags = _load_list("wln_enumerate_tags.json")
    genres = _load_list("wln_enumerate_genres.json")
    matched = match_theme_labels(["cultivation", "revenge"], tags=tags, genres=genres)
    assert matched["tag-category"]["cultivation"] == "included"
    assert matched["tag-category"]["revenge"] == "included"
    assert len(matched.get("tag-category", {})) + len(matched.get("genre-category", {})) <= 3


@pytest.mark.unit
def test_extract_titles_caps_and_dedupes() -> None:
    payload = _load_obj("wln_search_advanced.json")
    data = payload["data"]
    assert isinstance(data, list)
    titles = extract_titles(data)
    assert titles == [
        "Against the Gods",
        "Martial Peak",
        "Library of Heaven's Path",
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_titles_from_themes_uses_one_search() -> None:
    tags = _load_list("wln_enumerate_tags.json")
    genres = _load_list("wln_enumerate_genres.json")
    search = _load_obj("wln_search_advanced.json")
    calls: list[dict[str, object]] = []

    async def fake_post(
        _url: str,
        _allow: set[str],
        payload: dict[str, object],
        **_kwargs: object,
    ) -> dict[str, object]:
        calls.append(payload)
        mode = payload.get("mode")
        if mode == "enumerate-tags":
            return {"error": False, "data": [[n, 1] for n in tags]}
        if mode == "enumerate-genres":
            return {"error": False, "data": [[n, 1] for n in genres]}
        return search

    with patch(
        "app.modules.discovery.indexes.wlnupdates.post_json",
        side_effect=fake_post,
    ):
        hits = await titles_from_themes(["cultivation"])
    modes = [c.get("mode") for c in calls]
    assert modes.count("search-advanced") == 1
    assert {h.title for h in hits} == {
        "Against the Gods",
        "Martial Peak",
        "Library of Heaven's Path",
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_titles_from_themes_soft_fails() -> None:
    with patch(
        "app.modules.discovery.indexes.wlnupdates.post_json",
        new=AsyncMock(side_effect=RuntimeError("down")),
    ):
        assert await titles_from_themes(["cultivation"]) == []


def _load_list(name: str) -> list[str]:
    raw: object = json.loads((_FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    return [row[0] for row in raw if isinstance(row, list) and row]


def _load_obj(name: str) -> dict[str, object]:
    raw: object = json.loads((_FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw
