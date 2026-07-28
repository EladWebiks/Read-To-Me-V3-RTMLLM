"""Unit tests for the static model catalog."""

from __future__ import annotations

import pytest
from app.modules.llm.capabilities import ModelCapability
from app.modules.llm.registry import get_model, list_models, models_for_capability


@pytest.mark.unit
def test_catalog_has_default_flash_lite() -> None:
    model = get_model("gemini", "gemini-3.5-flash-lite")
    assert model is not None
    assert ModelCapability.FAST_CHAT in model.capabilities
    assert model.supports_tools is True
    assert model.supports_structured is True
    assert model.context_window > 0


@pytest.mark.unit
def test_models_for_capability_prefers_settings_model() -> None:
    matches = models_for_capability(
        ModelCapability.FAST_CHAT,
        prefer_provider="gemini",
        prefer_model="gemini-3.5-flash-lite",
    )
    assert matches
    assert matches[0].model_name == "gemini-3.5-flash-lite"


@pytest.mark.unit
def test_embedding_has_no_candidate_in_b1() -> None:
    matches = models_for_capability(ModelCapability.EMBEDDING)
    assert matches == []


@pytest.mark.unit
def test_list_models_enabled_only() -> None:
    enabled = list_models(enabled_only=True)
    assert all(m.enabled for m in enabled)
    assert len(enabled) >= 1
