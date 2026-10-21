"""Orchestration prompt copy."""

import pytest
from app.modules.orchestration.prompts import build_system_prompt

pytestmark = pytest.mark.unit


def test_system_prompt_mentions_novelfire_mirror() -> None:
    prompt = build_system_prompt()
    assert "novelphoenix.com" in prompt
    assert "scrape_book_range" in prompt
