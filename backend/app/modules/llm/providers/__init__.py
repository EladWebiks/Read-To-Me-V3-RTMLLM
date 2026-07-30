"""Resolve LLM providers by name."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.modules.llm.exceptions import LlmConfigError
from app.modules.llm.providers.gemini_provider import GeminiProvider, GeminiProviderConfig
from app.modules.llm.registry import ModelSpec, get_model


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


def build_provider_for(
    settings: Settings,
    *,
    provider: str,
    model_name: str,
) -> GeminiProvider:
    """Lookup catalog + build."""
    spec = get_model(provider, model_name)
    if spec is None:
        raise LlmConfigError(f"Unknown model: {provider}/{model_name}")
    return build_provider(ProviderBuildContext(settings=settings, model=spec))


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
