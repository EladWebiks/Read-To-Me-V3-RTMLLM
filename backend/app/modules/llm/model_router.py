"""Capability → ordered candidates with fallback and circuit breaker."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from app.core.config import Settings
from app.modules.llm import catalog
from app.modules.llm.capabilities import ModelCapability
from app.modules.llm.exceptions import LlmError, LlmProviderError, NoCandidateModelError
from app.modules.llm.providers import ProviderBuildContext, build_provider
from app.modules.llm.providers.gemini_provider import GeminiProvider
from app.modules.llm.registry import ModelSpec

T = TypeVar("T")

_FAILURE_THRESHOLD = 3
_COOLDOWN_SECONDS = 60.0


@dataclass
class _BreakerState:
    failures: int = 0
    open_until: float = 0.0


class ModelRouter:
    """Selects providers by capability and falls back on failure."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._breakers: dict[str, _BreakerState] = {}

    def candidates(self, capability: ModelCapability) -> list[ModelSpec]:
        """Enabled snapshot models for capability, preferred settings model first."""
        return catalog.models_for_capability(
            capability,
            prefer_provider=self._settings.llm.provider,
            prefer_model=self._settings.llm.model,
        )

    def build(self, model: ModelSpec) -> GeminiProvider:
        """Instantiate adapter for a catalog model."""
        return build_provider(ProviderBuildContext(settings=self._settings, model=model))

    async def run(
        self,
        capability: ModelCapability,
        call: Callable[[GeminiProvider, ModelSpec], Awaitable[T]],
    ) -> tuple[T, ModelSpec, bool]:
        """Try candidates in order; return (result, model, fallback_used)."""
        matches = self.candidates(capability)
        if not matches:
            raise NoCandidateModelError(capability.value)

        last_error: LlmError | None = None
        for index, model in enumerate(matches):
            if self._is_open(model.provider):
                continue
            try:
                provider = self.build(model)
                result = await call(provider, model)
                self._record_success(model.provider)
                return result, model, index > 0
            except LlmError as exc:
                last_error = exc
                self._record_failure(model.provider)

        if last_error is not None:
            raise last_error
        raise LlmProviderError("All LLM providers unavailable")

    def _is_open(self, provider: str) -> bool:
        state = self._breakers.setdefault(provider, _BreakerState())
        return time.monotonic() < state.open_until

    def _record_success(self, provider: str) -> None:
        state = self._breakers.setdefault(provider, _BreakerState())
        state.failures = 0
        state.open_until = 0.0

    def _record_failure(self, provider: str) -> None:
        state = self._breakers.setdefault(provider, _BreakerState())
        state.failures += 1
        if state.failures >= _FAILURE_THRESHOLD:
            state.open_until = time.monotonic() + _COOLDOWN_SECONDS
            state.failures = 0
