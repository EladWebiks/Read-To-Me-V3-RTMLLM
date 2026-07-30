"""HTTP DTOs for the LLM module."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.llm.capabilities import ModelCapability


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


class UiContext(BaseModel):
    """Current SPA screen (data only — ADR-14)."""

    path: str = Field(min_length=1, max_length=512, pattern=r"^/")
    book_id: UUID | None = None
    chapter_id: UUID | None = None


class ChatRequest(BaseModel):
    """POST /api/chat body."""

    message: str = Field(min_length=1, max_length=16_000)
    conversation_id: UUID | None = None
    ui_context: UiContext | None = None


class ConfirmRequest(BaseModel):
    """POST /api/chat/{conversation_id}/confirm body."""

    call_id: UUID
    approved: bool
    values: dict[str, Any] | None = Field(
        default=None,
        description="User-edited form fields (merged into frozen proposal)",
    )


class ChatMessageRead(BaseModel):
    """One persisted conversation message."""

    id: UUID
    role: str
    content: str
    created_at: datetime


class ConversationRead(BaseModel):
    """Conversation with ordered messages."""

    id: UUID
    title: str | None
    messages: list[ChatMessageRead] = Field(default_factory=list)


class ProviderPatch(BaseModel):
    """PATCH /api/admin/llm/catalog/providers/{provider} body."""

    enabled: bool


class ModelPatch(BaseModel):
    """PATCH model body — only supplied fields change."""

    enabled: bool | None = None
    input_cost_per_1m: float | None = Field(default=None, ge=0)
    output_cost_per_1m: float | None = Field(default=None, ge=0)


class ModelCreate(BaseModel):
    """POST /api/admin/llm/catalog/models body."""

    provider: str = Field(min_length=1, max_length=64)
    model_name: str = Field(min_length=1, max_length=128)
    capabilities: list[ModelCapability]
    context_window: int = Field(ge=1)
    supports_tools: bool = True
    supports_structured: bool = True
    supports_streaming: bool = True
    enabled: bool = True
    input_cost_per_1m: float = Field(default=0.0, ge=0)
    output_cost_per_1m: float = Field(default=0.0, ge=0)


class ModelAdminRead(BaseModel):
    """Admin view of one catalog model (includes pricing)."""

    model_name: str
    enabled: bool
    effective_enabled: bool
    capabilities: list[str]
    context_window: int
    supports_tools: bool
    supports_structured: bool
    supports_streaming: bool
    input_cost_per_1m: float
    output_cost_per_1m: float
    updated_at: datetime


class ProviderAdminRead(BaseModel):
    """Admin view of one provider with its models."""

    name: str
    enabled: bool
    has_adapter: bool
    models: list[ModelAdminRead] = Field(default_factory=list)


class CatalogAdminResponse(BaseModel):
    """GET /api/admin/llm/catalog payload."""

    providers: list[ProviderAdminRead] = Field(default_factory=list)


class UserUsageSummary(BaseModel):
    """Aggregated per-user LLM usage for a period (tier quotas / billing)."""

    user_id: UUID
    period_start: datetime
    period_end: datetime
    tokens_in: int
    tokens_out: int
    total_cost: float
    execution_count: int


class UsageBreakdownRead(BaseModel):
    """Shared aggregate fields for admin usage buckets."""

    tokens_in: int
    tokens_out: int
    total_cost: float
    execution_count: int


class ModelUsageRead(UsageBreakdownRead):
    """Cross-user aggregate for one (provider, model)."""

    provider: str
    model: str


class TaskUsageRead(UsageBreakdownRead):
    """Cross-user aggregate for one task."""

    task: str


class UserUsageRead(UsageBreakdownRead):
    """Aggregate for one user over the period."""

    user_id: UUID


class AdminUsageOverview(UsageBreakdownRead):
    """GET /api/admin/usage/summary payload."""

    period_start: datetime
    period_end: datetime
    by_model: list[ModelUsageRead] = Field(default_factory=list)
    by_task: list[TaskUsageRead] = Field(default_factory=list)


class LlmExecutionRead(BaseModel):
    """One llm_execution row for the backoffice recent-executions table."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    conversation_id: UUID | None
    task: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost: float
    latency_ms: int
    status: str
    fallback_used: bool
    error: str | None
    created_at: datetime
