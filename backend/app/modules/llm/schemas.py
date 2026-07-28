"""HTTP DTOs for the LLM module."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelRead(BaseModel):
    """Public model metadata (no secrets)."""

    provider: str
    model_name: str
    capabilities: list[str]
    context_window: int
    supports_tools: bool
    supports_structured: bool
    supports_streaming: bool
    enabled: bool


class ModelListResponse(BaseModel):
    """GET /api/llm/models payload."""

    llm_enabled: bool
    default_provider: str
    default_model: str
    models: list[ModelRead] = Field(default_factory=list)
