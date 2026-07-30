"""Persistence for LLM telemetry, conversations, and model catalog."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.llm.models import (
    Conversation,
    ConversationMessage,
    ConversationSummary,
    CostRecord,
    LlmExecution,
    ModelConfiguration,
    ModelProvider,
    ToolCallRecord,
)
from app.modules.llm.registry import ModelSpec


@dataclass(frozen=True, slots=True)
class CatalogRow:
    """One joined provider+model row for the runtime catalog snapshot."""

    provider_name: str
    provider_enabled: bool
    model_name: str
    model_enabled: bool
    capabilities: list[str]
    context_window: int
    supports_tools: bool
    supports_structured: bool
    supports_streaming: bool
    input_cost_per_1m: float
    output_cost_per_1m: float


@dataclass(frozen=True, slots=True)
class ExecutionWrite:
    """Fields for one llm_execution + cost_record insert."""

    task: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost: float
    latency_ms: int
    status: str
    fallback_used: bool
    trace_id: str | None
    error: str | None
    unit_cost_in: float
    unit_cost_out: float
    user_id: uuid.UUID
    conversation_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ToolCallWrite:
    """Fields for one tool_call audit insert."""

    tool_name: str
    input_data: dict[str, Any]
    status: str
    risk_level: str
    message_id: uuid.UUID | None = None
    output_data: dict[str, Any] | None = None
    duration_ms: int | None = None
    confirmed_by_user: bool = False
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ToolCallUpdate:
    """Fields to patch on an existing tool_call."""

    status: str
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    confirmed_by_user: bool | None = None
    error: str | None = None
    duration_ms: int | None = None


@dataclass(frozen=True, slots=True)
class ConversationSummaryWrite:
    """Fields for a compact conversation-prefix summary."""

    conversation_id: uuid.UUID
    user_id: uuid.UUID
    summary: str
    through_message_id: uuid.UUID
    source_message_count: int


class LlmRepository:
    """DB access for llm module tables."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_execution(self, data: ExecutionWrite) -> uuid.UUID:
        """Insert llm_execution + cost_record; return execution id."""
        execution = LlmExecution(
            conversation_id=data.conversation_id,
            user_id=data.user_id,
            task=data.task,
            provider=data.provider,
            model=data.model,
            tokens_in=data.tokens_in,
            tokens_out=data.tokens_out,
            cost=data.cost,
            latency_ms=data.latency_ms,
            status=data.status,
            fallback_used=data.fallback_used,
            trace_id=data.trace_id,
            error=data.error,
        )
        self._session.add(execution)
        await self._session.flush()
        self._session.add(
            CostRecord(
                llm_execution_id=execution.id,
                model=data.model,
                tokens_in=data.tokens_in,
                tokens_out=data.tokens_out,
                unit_cost_in=data.unit_cost_in,
                unit_cost_out=data.unit_cost_out,
                total_cost=data.cost,
            )
        )
        await self._session.commit()
        return execution.id

    async def upsert_provider(self, name: str, *, enabled: bool = True) -> ModelProvider:
        """Insert provider row if missing."""
        existing = await self._session.execute(
            select(ModelProvider).where(ModelProvider.name == name)
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            return row
        row = ModelProvider(name=name, enabled=enabled, config={})
        self._session.add(row)
        await self._session.flush()
        return row

    async def upsert_model(self, provider: ModelProvider, spec: ModelSpec) -> None:
        """Insert model_configuration if missing for provider+name."""
        existing = await self._session.execute(
            select(ModelConfiguration).where(
                ModelConfiguration.provider_id == provider.id,
                ModelConfiguration.model_name == spec.model_name,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return
        self._session.add(
            ModelConfiguration(
                provider_id=provider.id,
                model_name=spec.model_name,
                capabilities=[c.value for c in spec.capabilities],
                context_window=spec.context_window,
                supports_tools=spec.supports_tools,
                supports_structured=spec.supports_structured,
                supports_streaming=spec.supports_streaming,
                enabled=spec.enabled,
                input_cost_per_1m=spec.input_cost_per_1m,
                output_cost_per_1m=spec.output_cost_per_1m,
            )
        )

    async def list_catalog_rows(self) -> list[CatalogRow]:
        """All catalog rows, deterministically ordered (provider, model)."""
        result = await self._session.execute(
            select(ModelConfiguration, ModelProvider)
            .join(ModelProvider, ModelConfiguration.provider_id == ModelProvider.id)
            .order_by(ModelProvider.name, ModelConfiguration.model_name)
        )
        return [
            CatalogRow(
                provider_name=provider.name,
                provider_enabled=provider.enabled,
                model_name=model.model_name,
                model_enabled=model.enabled,
                capabilities=[str(c) for c in model.capabilities],
                context_window=model.context_window,
                supports_tools=model.supports_tools,
                supports_structured=model.supports_structured,
                supports_streaming=model.supports_streaming,
                input_cost_per_1m=model.input_cost_per_1m,
                output_cost_per_1m=model.output_cost_per_1m,
            )
            for model, provider in result.all()
        ]

    async def list_providers(self) -> list[ModelProvider]:
        """All provider rows ordered by name."""
        result = await self._session.execute(select(ModelProvider).order_by(ModelProvider.name))
        return list(result.scalars().all())

    async def list_model_configs(self) -> list[ModelConfiguration]:
        """All model rows ordered by name."""
        result = await self._session.execute(
            select(ModelConfiguration).order_by(ModelConfiguration.model_name)
        )
        return list(result.scalars().all())

    async def get_provider_by_name(self, name: str) -> ModelProvider | None:
        """Provider row by unique name."""
        result = await self._session.execute(
            select(ModelProvider).where(ModelProvider.name == name)
        )
        return result.scalar_one_or_none()

    async def get_model_config(
        self,
        provider_id: uuid.UUID,
        model_name: str,
    ) -> ModelConfiguration | None:
        """Model row by (provider_id, model_name)."""
        result = await self._session.execute(
            select(ModelConfiguration).where(
                ModelConfiguration.provider_id == provider_id,
                ModelConfiguration.model_name == model_name,
            )
        )
        return result.scalar_one_or_none()

    async def create_conversation(
        self,
        user_id: uuid.UUID,
        *,
        title: str | None = None,
    ) -> Conversation:
        """Insert a new conversation owned by user_id."""
        row = Conversation(user_id=user_id, title=title)
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_conversation_for_user(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Conversation | None:
        """Return conversation if owned by user_id."""
        result = await self._session.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def add_message(
        self,
        conversation_id: uuid.UUID,
        *,
        role: str,
        content: str,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
    ) -> ConversationMessage:
        """Append one message to a conversation."""
        row = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            # Explicit clock: Postgres now() is transaction-start and collides in-batch.
            created_at=datetime.now(UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_messages(
        self,
        conversation_id: uuid.UUID,
        *,
        limit: int = 40,
    ) -> list[ConversationMessage]:
        """Newest-last history capped at limit (oldest of the window first)."""
        result = await self._session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(
                ConversationMessage.created_at.desc(),
                ConversationMessage.seq.desc(),
            )
            .limit(limit)
        )
        rows = list(result.scalars().all())
        rows.reverse()
        return rows

    async def list_all_messages(self, conversation_id: uuid.UUID) -> list[ConversationMessage]:
        """Return complete oldest-first history for context reconstruction."""
        result = await self._session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at, ConversationMessage.seq)
        )
        return list(result.scalars().all())

    async def get_conversation_summary(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ConversationSummary | None:
        """Return a summary only when it belongs to the authenticated owner."""
        result = await self._session.execute(
            select(ConversationSummary).where(
                ConversationSummary.conversation_id == conversation_id,
                ConversationSummary.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_conversation_summary(
        self,
        data: ConversationSummaryWrite,
    ) -> ConversationSummary:
        """Insert or replace the compact prefix for one conversation."""
        row = await self.get_conversation_summary(data.conversation_id, data.user_id)
        if row is None:
            row = ConversationSummary(
                conversation_id=data.conversation_id,
                user_id=data.user_id,
                summary=data.summary,
                through_message_id=data.through_message_id,
                source_message_count=data.source_message_count,
            )
            self._session.add(row)
        else:
            row.summary = data.summary
            row.through_message_id = data.through_message_id
            row.source_message_count = data.source_message_count
        await self._session.flush()
        return row

    async def delete_conversation_summary(self, row: ConversationSummary) -> None:
        """Invalidate a stale summary row."""
        await self._session.delete(row)
        await self._session.flush()

    async def set_conversation_title(
        self,
        conversation_id: uuid.UUID,
        title: str,
    ) -> None:
        """Update conversation title when still empty."""
        row = await self._session.get(Conversation, conversation_id)
        if row is None or row.title:
            return
        row.title = title
        await self._session.flush()

    async def record_tool_call(self, data: ToolCallWrite) -> ToolCallRecord:
        """Insert a tool_call audit row."""
        row = ToolCallRecord(
            message_id=data.message_id,
            tool_name=data.tool_name,
            input=data.input_data,
            output=data.output_data,
            status=data.status,
            duration_ms=data.duration_ms,
            risk_level=data.risk_level,
            confirmed_by_user=data.confirmed_by_user,
            error=data.error,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_tool_call(self, call_id: uuid.UUID) -> ToolCallRecord | None:
        """Load one tool_call by id."""
        return await self._session.get(ToolCallRecord, call_id)

    async def update_tool_call(self, row: ToolCallRecord, data: ToolCallUpdate) -> ToolCallRecord:
        """Mutate an existing tool_call (HITL resolve)."""
        row.status = data.status
        if data.input_data is not None:
            row.input = data.input_data
        if data.output_data is not None:
            row.output = data.output_data
        if data.confirmed_by_user is not None:
            row.confirmed_by_user = data.confirmed_by_user
        if data.error is not None:
            row.error = data.error
        if data.duration_ms is not None:
            row.duration_ms = data.duration_ms
        await self._session.flush()
        return row
