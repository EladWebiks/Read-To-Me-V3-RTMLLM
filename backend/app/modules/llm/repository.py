"""Persistence for LLM telemetry, conversations, and model catalog."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import ColumnElement, and_, delete, func, select, update
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
from app.modules.llm.schemas import ExecutionAdminFilters, ToolCallAdminFilters
from app.modules.usage.kinds import (
    LlmModelFact,
    LlmTaskFact,
    UsageFact,
    UsageMetric,
)
from app.modules.usage.repository import day_window


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
class UsageTotals:
    """Aggregate of llm_executions for one user over a period."""

    tokens_in: int
    tokens_out: int
    total_cost: float
    execution_count: int


@dataclass(frozen=True, slots=True)
class ModelUsageRow:
    """Cross-user aggregate for one (provider, model)."""

    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    total_cost: float
    execution_count: int


@dataclass(frozen=True, slots=True)
class TaskUsageRow:
    """Cross-user aggregate for one task."""

    task: str
    tokens_in: int
    tokens_out: int
    total_cost: float
    execution_count: int


@dataclass(frozen=True, slots=True)
class UserUsageRow:
    """Aggregate for one user over a period."""

    user_id: uuid.UUID
    tokens_in: int
    tokens_out: int
    total_cost: float
    execution_count: int


@dataclass(frozen=True, slots=True)
class ToolCallWrite:
    """Fields for one tool_call audit insert."""

    tool_name: str
    input_data: dict[str, Any]
    status: str
    risk_level: str
    user_id: uuid.UUID | None = None
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


def _execution_conditions(
    *,
    period_start: datetime,
    period_end: datetime,
    filters: ExecutionAdminFilters,
) -> list[ColumnElement[bool]]:
    """Period + optional user/task/status filters for list_executions_admin."""
    conditions: list[ColumnElement[bool]] = [
        LlmExecution.created_at >= period_start,
        LlmExecution.created_at < period_end,
    ]
    if filters.user_ids is not None:
        conditions.append(LlmExecution.user_id.in_(filters.user_ids))
    if filters.task:
        conditions.append(LlmExecution.task == filters.task)
    if filters.status:
        conditions.append(LlmExecution.status == filters.status)
    return conditions


def _tool_call_conditions(filters: ToolCallAdminFilters) -> list[ColumnElement[bool]]:
    """Translate the optional filter set into WHERE conditions."""
    conditions: list[ColumnElement[bool]] = []
    if filters.tool_name:
        conditions.append(ToolCallRecord.tool_name == filters.tool_name)
    if filters.status:
        conditions.append(ToolCallRecord.status == filters.status)
    if filters.risk_level:
        conditions.append(ToolCallRecord.risk_level == filters.risk_level)
    if filters.period_start:
        conditions.append(ToolCallRecord.created_at >= filters.period_start)
    if filters.period_end:
        conditions.append(ToolCallRecord.created_at < filters.period_end)
    return conditions


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

    async def usage_summary_for_user(
        self,
        user_id: uuid.UUID,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> UsageTotals:
        """Billing-month aggregate over [period_start, period_end).

        Served by ix_llm_executions_user_id_created_at as one index range scan.
        """
        result = await self._session.execute(
            select(
                func.coalesce(func.sum(LlmExecution.tokens_in), 0),
                func.coalesce(func.sum(LlmExecution.tokens_out), 0),
                func.coalesce(func.sum(LlmExecution.cost), 0.0),
                func.count(LlmExecution.id),
            ).where(
                LlmExecution.user_id == user_id,
                LlmExecution.created_at >= period_start,
                LlmExecution.created_at < period_end,
            )
        )
        tokens_in, tokens_out, total_cost, count = result.one()
        return UsageTotals(
            tokens_in=int(tokens_in),
            tokens_out=int(tokens_out),
            total_cost=float(total_cost),
            execution_count=int(count),
        )

    @staticmethod
    def _in_period(period_start: datetime, period_end: datetime) -> ColumnElement[bool]:
        return and_(
            LlmExecution.created_at >= period_start,
            LlmExecution.created_at < period_end,
        )

    @staticmethod
    def _usage_sums() -> tuple[Any, ...]:
        return (
            func.coalesce(func.sum(LlmExecution.tokens_in), 0),
            func.coalesce(func.sum(LlmExecution.tokens_out), 0),
            func.coalesce(func.sum(LlmExecution.cost), 0.0),
            func.count(LlmExecution.id),
        )

    async def usage_totals_admin(
        self, *, period_start: datetime, period_end: datetime
    ) -> UsageTotals:
        """Cross-user totals over [period_start, period_end)."""
        result = await self._session.execute(
            select(*self._usage_sums()).where(self._in_period(period_start, period_end))
        )
        tokens_in, tokens_out, total_cost, count = result.one()
        return UsageTotals(
            tokens_in=int(tokens_in),
            tokens_out=int(tokens_out),
            total_cost=float(total_cost),
            execution_count=int(count),
        )

    async def usage_by_model_admin(
        self, *, period_start: datetime, period_end: datetime
    ) -> list[ModelUsageRow]:
        """Cross-user aggregates grouped by (provider, model), cost-desc."""
        stmt = (
            select(LlmExecution.provider, LlmExecution.model, *self._usage_sums())
            .where(self._in_period(period_start, period_end))
            .group_by(LlmExecution.provider, LlmExecution.model)
            .order_by(func.coalesce(func.sum(LlmExecution.cost), 0.0).desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            ModelUsageRow(
                provider=row[0],
                model=row[1],
                tokens_in=int(row[2]),
                tokens_out=int(row[3]),
                total_cost=float(row[4]),
                execution_count=int(row[5]),
            )
            for row in rows
        ]

    async def usage_by_task_admin(
        self, *, period_start: datetime, period_end: datetime
    ) -> list[TaskUsageRow]:
        """Cross-user aggregates grouped by task, cost-desc."""
        stmt = (
            select(LlmExecution.task, *self._usage_sums())
            .where(self._in_period(period_start, period_end))
            .group_by(LlmExecution.task)
            .order_by(func.coalesce(func.sum(LlmExecution.cost), 0.0).desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            TaskUsageRow(
                task=row[0],
                tokens_in=int(row[1]),
                tokens_out=int(row[2]),
                total_cost=float(row[3]),
                execution_count=int(row[4]),
            )
            for row in rows
        ]

    async def usage_by_user_admin(
        self, *, period_start: datetime, period_end: datetime, limit: int, offset: int
    ) -> tuple[list[UserUsageRow], int]:
        """Per-user aggregates, cost-desc, with total distinct-user count."""
        condition = self._in_period(period_start, period_end)
        total_stmt = select(func.count(func.distinct(LlmExecution.user_id))).where(condition)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(LlmExecution.user_id, *self._usage_sums())
            .where(condition)
            .group_by(LlmExecution.user_id)
            .order_by(func.coalesce(func.sum(LlmExecution.cost), 0.0).desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).all()
        items = [
            UserUsageRow(
                user_id=row[0],
                tokens_in=int(row[1]),
                tokens_out=int(row[2]),
                total_cost=float(row[3]),
                execution_count=int(row[4]),
            )
            for row in rows
        ]
        return items, total

    async def usage_for_users(
        self,
        user_ids: list[uuid.UUID],
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> dict[uuid.UUID, UsageTotals]:
        """Per-user aggregates for a fixed id set (backoffice quota column)."""
        if not user_ids:
            return {}
        stmt = (
            select(LlmExecution.user_id, *self._usage_sums())
            .where(
                LlmExecution.user_id.in_(user_ids),
                self._in_period(period_start, period_end),
            )
            .group_by(LlmExecution.user_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return {
            row[0]: UsageTotals(int(row[1]), int(row[2]), float(row[3]), int(row[4]))
            for row in rows
        }

    async def list_executions_admin(
        self,
        filters: ExecutionAdminFilters,
        *,
        period_start: datetime,
        period_end: datetime,
        limit: int,
        offset: int,
    ) -> tuple[list[LlmExecution], int]:
        """Cross-user execution rows, newest first."""
        if filters.user_ids is not None and not filters.user_ids:
            return [], 0
        conditions = _execution_conditions(
            period_start=period_start, period_end=period_end, filters=filters
        )
        total_stmt = select(func.count()).select_from(LlmExecution).where(*conditions)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(LlmExecution)
            .where(*conditions)
            .order_by(LlmExecution.created_at.desc(), LlmExecution.id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows), total

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
        """Set conversation title to the latest user message preview."""
        row = await self._session.get(Conversation, conversation_id)
        if row is None:
            return
        row.title = title
        row.updated_at = datetime.now(UTC)
        await self._session.flush()

    async def list_conversations_for_user(
        self, user_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[Conversation], int]:
        """Owned conversations, newest activity first."""
        total_stmt = (
            select(func.count()).select_from(Conversation).where(Conversation.user_id == user_id)
        )
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows), total

    async def delete_conversation_for_user(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        """Hard-delete an owned conversation and its messages/tool calls.

        Keeps llm_executions/cost audit rows; only clears the conversation FK.
        """
        row = await self.get_conversation_for_user(conversation_id, user_id)
        if row is None:
            return False
        await self._purge_conversation_children(conversation_id)
        await self._session.delete(row)
        await self._session.flush()
        return True

    async def _purge_conversation_children(self, conversation_id: uuid.UUID) -> None:
        msg_ids = select(ConversationMessage.id).where(
            ConversationMessage.conversation_id == conversation_id
        )
        await self._session.execute(
            delete(ToolCallRecord).where(ToolCallRecord.message_id.in_(msg_ids))
        )
        await self._session.execute(
            delete(ConversationSummary).where(
                ConversationSummary.conversation_id == conversation_id
            )
        )
        await self._session.execute(
            update(LlmExecution)
            .where(LlmExecution.conversation_id == conversation_id)
            .values(conversation_id=None)
        )
        await self._session.execute(
            delete(ConversationMessage).where(
                ConversationMessage.conversation_id == conversation_id
            )
        )

    async def record_tool_call(self, data: ToolCallWrite) -> ToolCallRecord:
        """Insert a tool_call audit row."""
        row = ToolCallRecord(
            message_id=data.message_id,
            user_id=data.user_id,
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

    async def list_tool_calls_admin(
        self, filters: ToolCallAdminFilters, *, limit: int, offset: int
    ) -> tuple[list[tuple[ToolCallRecord, uuid.UUID | None]], int]:
        """Cross-user audit rows, newest first, with owner attribution.

        Prefer the stored user_id; fall back to message → conversation for
        legacy rows written before tool_calls.user_id existed.
        """
        conditions = _tool_call_conditions(filters)
        total_stmt = select(func.count()).select_from(ToolCallRecord).where(*conditions)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        owner = func.coalesce(ToolCallRecord.user_id, Conversation.user_id)
        stmt = (
            select(ToolCallRecord, owner)
            .join(
                ConversationMessage,
                ToolCallRecord.message_id == ConversationMessage.id,
                isouter=True,
            )
            .join(
                Conversation,
                ConversationMessage.conversation_id == Conversation.id,
                isouter=True,
            )
            .where(*conditions)
            .order_by(ToolCallRecord.created_at.desc(), ToolCallRecord.id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows], total

    async def daily_usage_facts(self, day: date) -> list[UsageFact]:
        """Per-user LLM facts for one UTC day (builder-facing, spec §6)."""
        start, end = day_window(day)
        failures = func.count(LlmExecution.id).filter(LlmExecution.status != "ok")
        stmt = (
            select(
                LlmExecution.user_id,
                func.coalesce(func.sum(LlmExecution.tokens_in), 0),
                func.coalesce(func.sum(LlmExecution.tokens_out), 0),
                func.coalesce(func.sum(LlmExecution.cost), 0.0),
                func.count(LlmExecution.id),
                failures,
            )
            .where(LlmExecution.created_at >= start, LlmExecution.created_at < end)
            .group_by(LlmExecution.user_id)
        )
        facts: list[UsageFact] = []
        for row in (await self._session.execute(stmt)).all():
            user_id = row[0]
            facts.append(UsageFact(user_id, UsageMetric.LLM_TOKENS_IN, float(row[1])))
            facts.append(UsageFact(user_id, UsageMetric.LLM_TOKENS_OUT, float(row[2])))
            facts.append(UsageFact(user_id, UsageMetric.LLM_COST_USD, float(row[3])))
            facts.append(UsageFact(user_id, UsageMetric.LLM_EXECUTIONS, float(row[4])))
            facts.append(UsageFact(user_id, UsageMetric.LLM_FAILURES, float(row[5])))
        return facts

    async def daily_model_facts(self, day: date) -> list[LlmModelFact]:
        """Cross-user (provider, model) aggregates for one UTC day."""
        start, end = day_window(day)
        stmt = (
            select(
                LlmExecution.provider,
                LlmExecution.model,
                func.coalesce(func.sum(LlmExecution.tokens_in), 0),
                func.coalesce(func.sum(LlmExecution.tokens_out), 0),
                func.coalesce(func.sum(LlmExecution.cost), 0.0),
                func.count(LlmExecution.id),
            )
            .where(LlmExecution.created_at >= start, LlmExecution.created_at < end)
            .group_by(LlmExecution.provider, LlmExecution.model)
        )
        return [
            LlmModelFact(r[0], r[1], int(r[2]), int(r[3]), float(r[4]), int(r[5]))
            for r in (await self._session.execute(stmt)).all()
        ]

    async def daily_task_facts(self, day: date) -> list[LlmTaskFact]:
        """Cross-user per-task aggregates for one UTC day."""
        start, end = day_window(day)
        stmt = (
            select(
                LlmExecution.task,
                func.coalesce(func.sum(LlmExecution.tokens_in), 0),
                func.coalesce(func.sum(LlmExecution.tokens_out), 0),
                func.coalesce(func.sum(LlmExecution.cost), 0.0),
                func.count(LlmExecution.id),
            )
            .where(LlmExecution.created_at >= start, LlmExecution.created_at < end)
            .group_by(LlmExecution.task)
        )
        return [
            LlmTaskFact(r[0], int(r[1]), int(r[2]), float(r[3]), int(r[4]))
            for r in (await self._session.execute(stmt)).all()
        ]
