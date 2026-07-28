"""Model router fallback and circuit-breaker tests."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest
from app.core.config import Settings
from app.modules.llm.capabilities import ModelCapability
from app.modules.llm.exceptions import LlmProviderError, NoCandidateModelError
from app.modules.llm.model_router import ModelRouter, _BreakerState
from app.modules.llm.registry import ModelSpec


def _settings(**kwargs: object) -> Settings:
    base: dict[str, object] = {
        "llm_enabled": True,
        "llm_provider": "gemini",
        "llm_model": "gemini-3.5-flash-lite",
        "gemini_api_key": "test-key",
    }
    base.update(kwargs)
    return Settings.model_validate(base)


@pytest.mark.unit
def test_candidates_prefer_configured_model() -> None:
    router = ModelRouter(_settings())
    matches = router.candidates(ModelCapability.FAST_CHAT)
    assert matches[0].model_name == "gemini-3.5-flash-lite"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_fallback_on_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    router = ModelRouter(_settings())

    async def boom(_provider: object, model: ModelSpec) -> str:
        if model.model_name == "gemini-3.5-flash-lite":
            raise LlmProviderError("fail primary")
        return "ok"

    monkeypatch.setattr(router, "build", lambda _model: AsyncMock())
    result, model, fallback = await router.run(ModelCapability.FAST_CHAT, boom)
    assert result == "ok"
    assert fallback is True
    assert model.model_name == "gemini-3.6-flash"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_candidate_for_embedding() -> None:
    router = ModelRouter(_settings())

    async def _never(_provider: object, _model: ModelSpec) -> str:
        return "nope"

    with pytest.raises(NoCandidateModelError):
        await router.run(ModelCapability.EMBEDDING, _never)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_circuit_breaker_skips_open_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = ModelRouter(_settings())
    router._breakers["gemini"] = _BreakerState(
        failures=0,
        open_until=time.monotonic() + 120,
    )

    async def _call(_provider: object, _model: ModelSpec) -> str:
        return "should-not-run"

    monkeypatch.setattr(router, "build", lambda _m: AsyncMock())
    with pytest.raises(LlmProviderError):
        await router.run(ModelCapability.FAST_CHAT, _call)
