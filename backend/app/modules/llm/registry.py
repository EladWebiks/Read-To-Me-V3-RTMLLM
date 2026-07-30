"""Seed-only model catalog defaults.

The DB (model_providers / model_configurations) is the runtime source of
truth — see modules/llm/catalog.py. This tuple only defines what startup
seeding inserts when rows are missing; it never overwrites admin edits.
"""

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
