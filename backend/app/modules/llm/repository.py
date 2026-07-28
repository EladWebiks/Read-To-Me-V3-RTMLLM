"""Persistence for LLM telemetry, conversations, and model catalog."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.llm.models import (
    Conversation,
    ConversationMessage,
    CostRecord,
    LlmExecution,
    ModelConfiguration,
    ModelProvider,
)
from app.modules.llm.registry import ModelSpec


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
    conversation_id: uuid.UUID | None = None


class LlmRepository:
    """DB access for llm module tables."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_execution(self, data: ExecutionWrite) -> uuid.UUID:
        """Insert llm_execution + cost_record; return execution id."""
        execution = LlmExecution(
            conversation_id=data.conversation_id,
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
            )
        )

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
                ConversationMessage.id.desc(),
            )
            .limit(limit)
        )
        rows = list(result.scalars().all())
        rows.reverse()
        return rows

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
