"""Seed-only defaults: the code catalog defines what seeding inserts."""

from __future__ import annotations

import pytest
from app.modules.llm.capabilities import ModelCapability
from app.modules.llm.registry import MODEL_CATALOG


@pytest.mark.unit
def test_seed_defaults_include_flash_lite() -> None:
    lite = next(m for m in MODEL_CATALOG if m.model_name == "gemini-3.5-flash-lite")
    assert ModelCapability.FAST_CHAT in lite.capabilities
    assert lite.supports_tools is True
    assert lite.supports_structured is True
    assert lite.input_cost_per_1m > 0
    assert lite.output_cost_per_1m > 0


@pytest.mark.unit
def test_seed_defaults_are_enabled_with_context_windows() -> None:
    assert all(m.enabled for m in MODEL_CATALOG)
    assert all(m.context_window > 0 for m in MODEL_CATALOG)
