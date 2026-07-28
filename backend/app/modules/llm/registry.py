"""Static model catalog — seeded into DB; domain never hardcodes names."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.llm.capabilities import ModelCapability


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """One selectable model in the catalog."""

    provider: str
    model_name: str
    capabilities: frozenset[ModelCapability]
    context_window: int
    supports_tools: bool
    supports_structured: bool
    supports_streaming: bool
    enabled: bool = True
    # USD per 1M tokens (approximate; free-tier cost recorded as 0 at call time).
    input_cost_per_1m: float = 0.0
    output_cost_per_1m: float = 0.0


_FLASH_LITE_CAPS = frozenset(
    {
        ModelCapability.FAST_CHAT,
        ModelCapability.TOOL_CALLING,
        ModelCapability.STRUCTURED_EXTRACTION,
    }
)

_FLASH_CAPS = frozenset(
    {
        ModelCapability.FAST_CHAT,
        ModelCapability.TOOL_CALLING,
        ModelCapability.STRUCTURED_EXTRACTION,
        ModelCapability.LONG_CONTEXT_SUMMARIZATION,
    }
)

MODEL_CATALOG: tuple[ModelSpec, ...] = (
    ModelSpec(
        provider="gemini",
        model_name="gemini-3.5-flash-lite",
        capabilities=_FLASH_LITE_CAPS,
        context_window=1_048_576,
        supports_tools=True,
        supports_structured=True,
        supports_streaming=True,
        input_cost_per_1m=0.10,
        output_cost_per_1m=0.40,
    ),
    ModelSpec(
        provider="gemini",
        model_name="gemini-3.6-flash",
        capabilities=_FLASH_CAPS,
        context_window=1_048_576,
        supports_tools=True,
        supports_structured=True,
        supports_streaming=True,
        input_cost_per_1m=0.30,
        output_cost_per_1m=2.50,
    ),
)


def list_models(*, enabled_only: bool = True) -> list[ModelSpec]:
    """Return catalog entries."""
    if enabled_only:
        return [m for m in MODEL_CATALOG if m.enabled]
    return list(MODEL_CATALOG)


def get_model(provider: str, model_name: str) -> ModelSpec | None:
    """Lookup a catalog entry."""
    for model in MODEL_CATALOG:
        if model.provider == provider and model.model_name == model_name:
            return model
    return None


def models_for_capability(
    capability: ModelCapability,
    *,
    prefer_provider: str | None = None,
    prefer_model: str | None = None,
) -> list[ModelSpec]:
    """Ordered candidates supporting capability (preferred model first)."""
    matches = [m for m in MODEL_CATALOG if m.enabled and capability in m.capabilities]
    if prefer_model and prefer_provider:
        preferred = [
            m for m in matches if m.provider == prefer_provider and m.model_name == prefer_model
        ]
        rest = [m for m in matches if m not in preferred]
        return preferred + rest
    if prefer_provider:
        preferred = [m for m in matches if m.provider == prefer_provider]
        rest = [m for m in matches if m not in preferred]
        return preferred + rest
    return matches
