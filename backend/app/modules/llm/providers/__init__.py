"""Resolve LLM providers by name."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.modules.llm.exceptions import LlmConfigError
from app.modules.llm.providers.gemini_provider import GeminiProvider, GeminiProviderConfig
from app.modules.llm.registry import ModelSpec

# Provider names with a registered adapter factory. A DB catalog row for any
# other provider is unserveable and is skipped by the runtime catalog.
KNOWN_ADAPTERS: frozenset[str] = frozenset({"gemini"})


def has_adapter(provider: str) -> bool:
    """True when an adapter factory exists for this provider name."""
    return provider in KNOWN_ADAPTERS


@dataclass(frozen=True, slots=True)
class ProviderBuildContext:
    """Inputs needed to construct an adapter instance."""

    settings: Settings
    model: ModelSpec


def build_provider(ctx: ProviderBuildContext) -> GeminiProvider:
    """Build the configured provider for a catalog model."""
    if ctx.model.provider == "gemini":
        return _build_gemini(ctx)
    raise LlmConfigError(f"Unknown provider: {ctx.model.provider}")


def _build_gemini(ctx: ProviderBuildContext) -> GeminiProvider:
    key = ctx.settings.llm.gemini_api_key
    if not key:
        raise LlmConfigError("GEMINI_API_KEY is required when LLM is enabled")
    return GeminiProvider(
        GeminiProviderConfig(
            api_key=key,
            model_name=ctx.model.model_name,
            timeout_seconds=ctx.settings.llm.timeout_seconds,
            max_output_tokens=ctx.settings.llm.max_output_tokens,
            max_retries=ctx.settings.llm.max_retries,
            supports_tools=ctx.model.supports_tools,
            supports_structured=ctx.model.supports_structured,
            supports_streaming=ctx.model.supports_streaming,
        )
    )
