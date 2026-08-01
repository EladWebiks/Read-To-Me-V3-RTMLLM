"""OrchestrationService — bounded tool loop behind chat SSE."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import aclosing
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.llm.conversation_context import (
    ConversationContextService,
    summary_context_block,
)
from app.modules.llm.models import ConversationMessage, ToolCallRecord
from app.modules.llm.repository import LlmRepository, ToolCallUpdate
from app.modules.llm.service import LlmService
from app.modules.llm.sse import ChatSseEvent
from app.modules.llm.types import (
    Message,
    Role,
    ToolCall,
    ToolCallingRequest,
    ToolCallingResponse,
    Usage,
)
from app.modules.orchestration.budget import RunBudget
from app.modules.orchestration.exceptions import BudgetExceededError, OrchestrationError
from app.modules.orchestration.hitl_pause import (
    FreezeRequest,
    apply_budget_snapshot,
    budget_from_snapshot,
    confirmation_event_data,
    freeze_pending,
    is_expired,
    restore_snapshot,
    snapshot_conversation_id,
    snapshot_run_id,
)
from app.modules.orchestration.policy import PolicyService
from app.modules.orchestration.prompts import SYSTEM_PROMPT
from app.modules.orchestration.ui_context import (
    choice_request_for_tool,
    client_action_for_tool,
    format_ui_context_block,
)
from app.modules.quotas.exceptions import QuotaExceededError
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.service import QuotaService
from app.modules.tools.base import BaseTool, Mode, RiskLevel, ToolContext
from app.modules.tools.catalog import build_default_registry
from app.modules.tools.exceptions import (
    ToolAuthzError,
    ToolModeBlockedError,
    ToolNotFoundError,
    ToolValidationError,
)
from app.modules.tools.executor import ExecuteOptions, execute_tool_call, prepare_gated_call
from app.modules.tools.hitl import merge_confirmed_args
from app.modules.tools.registry import ToolRegistry
from app.modules.usage.read_service import UsageReadService
from app.modules.users.schemas import UserRead

_MAX_TOOL_RESULT_CHARS = 6_000

# Persisted role for quota refusals. NOT a member of llm.types.Role on
# purpose: _to_llm_messages drops roles Role() cannot parse, which is what
# keeps refusal copy out of future prompts (spec §3.3). If Role ever grows
# this value, add an explicit skip there.
QUOTA_REFUSAL_ROLE = "quota_refusal"


@dataclass(frozen=True, slots=True)
class _ConfirmedExec:
    """Bundle for post-HITL execute."""

    ctx: ToolContext
    messages: list[Message]
    tool: BaseTool
    call: ToolCall
    row: ToolCallRecord
    values: dict[str, Any] | None
    budget: RunBudget


@dataclass(frozen=True, slots=True)
class _PausePack:
    """Bundle for HITL pause."""

    ctx: ToolContext
    messages: list[Message]
    tool: BaseTool
    call: ToolCall
    budget: RunBudget
    usage: Usage
    hitl_rounds: int


@dataclass(frozen=True, slots=True)
class _ToolRound:
    """Bundle for one tool round in the loop."""

    ctx: ToolContext
    messages: list[Message]
    call: ToolCall
    budget: RunBudget
    usage: Usage
    hitl_rounds: int


@dataclass(frozen=True, slots=True)
class _LoopState:
    """Mutable-ish loop counters carried across rounds."""

    ctx: ToolContext
    messages: list[Message]
    budget: RunBudget
    usage: Usage
    hitl_rounds: int
    final_text: str


@dataclass
class _StreamedRound:
    prefix: bool = False
    response: ToolCallingResponse | None = None
    started: bool = False

    async def events(
        self,
        llm: LlmService,
        request: ToolCallingRequest,
        ctx: ToolContext,
    ) -> AsyncIterator[ChatSseEvent]:
        stream = llm.stream_tools(
            request,
            user_id=ctx.user_id,
            conversation_id=ctx.conversation_id,
        )
        async with aclosing(stream) as chunks:
            async for chunk in chunks:
                if chunk.text:
                    if self.prefix and not self.started:
                        yield ChatSseEvent("delta", {"text": "\n\n"})
                    self.started = True
                    yield ChatSseEvent("delta", {"text": chunk.text})
                if chunk.done:
                    self.response = chunk.response

    def require_response(self) -> ToolCallingResponse:
        if self.response is None:
            raise OrchestrationError("LLM stream ended without a response")
        return self.response


class OrchestrationService:
    """Runs the tool loop for one assistant turn."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        llm: LlmService,
        repo: LlmRepository,
        registry: ToolRegistry | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._llm = llm
        self._repo = repo
        self._registry = registry or build_default_registry()

    async def run(
        self,
        user: UserRead,
        conversation_id: UUID,
        ui_context: dict[str, Any] | None = None,
    ) -> AsyncIterator[ChatSseEvent]:
        """Yield SSE events for one tool-using assistant turn."""
        policy = await PolicyService(self._session, self._settings).resolve(user)
        try:
            await self._check_llm_quota(user)
        except QuotaExceededError as exc:
            # Same-session write: refusal marker + rejection row (Part D), one
            # commit, then the SSE error. The user's message is already
            # persisted; the marker is what explains it after a reload.
            await self._repo.add_message(
                conversation_id, role=QUOTA_REFUSAL_ROLE, content=str(exc)
            )
            await UsageReadService(self._session).record_rejection(user.id, exc.kind, "chat")
            await self._session.commit()
            yield _quota_error_event(exc)
            return
        ctx = self._make_ctx(user.id, conversation_id, uuid4())
        budget = RunBudget.from_policy(policy)
        context = await ConversationContextService(
            self._repo,
            self._llm,
            self._settings,
        ).build(user.id, conversation_id)
        messages = _to_llm_messages(
            context.messages,
            summary=context.summary,
            ui_context=ui_context,
        )
        async for event in self._safe_loop(ctx, messages, budget, Usage(0, 0), 0):
            yield event

    async def resume_confirm(
        self,
        user: UserRead,
        conversation_id: UUID,
        call_id: UUID,
        *,
        approved: bool,
        values: dict[str, Any] | None,
    ) -> AsyncIterator[ChatSseEvent]:
        """Resume after POST /confirm — new SSE stream for the same turn."""
        try:
            async for event in self._resume_confirm(
                user,
                conversation_id,
                call_id,
                approved=approved,
                values=values,
            ):
                yield event
        except BudgetExceededError as exc:
            yield ChatSseEvent("error", {"detail": str(exc), "code": "budget_exceeded"})
        except (
            OrchestrationError,
            ToolValidationError,
            ToolAuthzError,
            ToolModeBlockedError,
        ) as exc:
            yield ChatSseEvent("error", {"detail": str(exc)})

    async def _resume_confirm(
        self,
        user: UserRead,
        conversation_id: UUID,
        call_id: UUID,
        *,
        approved: bool,
        values: dict[str, Any] | None,
    ) -> AsyncIterator[ChatSseEvent]:
        row = await self._require_pending(user.id, conversation_id, call_id)
        messages, usage, budget_raw, hitl_rounds, provider_call_id = restore_snapshot(row)
        ctx = self._make_ctx(user.id, conversation_id, snapshot_run_id(row) or uuid4())
        budget = await self._restore_budget(user, budget_raw)
        tool = self._registry.resolve(row.tool_name)
        call = ToolCall(
            id=provider_call_id or str(row.id),
            name=tool.name,
            arguments=dict(row.input),
        )
        if not approved or is_expired(row):
            async for event in self._deny_pending(row, tool, call, messages):
                yield event
        else:
            pack = _ConfirmedExec(ctx, messages, tool, call, row, values, budget)
            yield ChatSseEvent("step", {"label": f"Running {tool.name}…"})
            result = await self._execute_confirmed(pack)
            for event in _tool_outcome_events(tool.name, bool(result.get("ok")), result):
                yield event
            terminal_text = _confirmed_terminal_text(tool.name, result)
            if terminal_text:
                yield ChatSseEvent("delta", {"text": terminal_text})
                yield await self._finish(ctx, terminal_text, usage, budget)
                return
        async for event in self._loop(ctx, messages, budget, usage, hitl_rounds):
            yield event

    async def _restore_budget(
        self,
        user: UserRead,
        budget_raw: dict[str, Any],
    ) -> RunBudget:
        """Prefer caps frozen at turn start; legacy snapshots re-resolve once."""
        frozen = budget_from_snapshot(budget_raw)
        if frozen is not None:
            return frozen
        budget = RunBudget.from_policy(
            await PolicyService(self._session, self._settings).resolve(user)
        )
        apply_budget_snapshot(budget, budget_raw)
        return budget

    async def _deny_pending(
        self,
        row: ToolCallRecord,
        tool: BaseTool,
        call: ToolCall,
        messages: list[Message],
    ) -> AsyncIterator[ChatSseEvent]:
        status = "expired" if is_expired(row) else "rejected"
        err = "confirmation expired" if status == "expired" else "user declined"
        result = {"ok": False, "tool": tool.name, "error": err}
        await self._repo.update_tool_call(
            row,
            ToolCallUpdate(status=status, confirmed_by_user=False, error=err),
        )
        await self._session.commit()
        _append_tool_message(messages, call, result)
        yield ChatSseEvent("tool_result", {"name": tool.name, "ok": False, "summary": err})

    async def _execute_confirmed(self, pack: _ConfirmedExec) -> dict[str, object]:
        final_args = merge_confirmed_args(pack.tool, dict(pack.row.input), pack.values)
        if pack.tool.touches_external:
            pack.budget.add_external()
        result = await execute_tool_call(
            pack.tool,
            pack.call,
            pack.ctx,
            self._repo,
            ExecuteOptions(confirmed=True, arguments=final_args, audit=False),
        )
        ok = bool(result.get("ok"))
        await self._repo.update_tool_call(
            pack.row,
            ToolCallUpdate(
                status="confirmed" if ok else "error",
                input_data=final_args,
                output_data=result.get("data") if ok else None,
                confirmed_by_user=True,
                error=None if ok else str(result.get("error")),
            ),
        )
        await self._session.commit()
        _append_tool_message(pack.messages, pack.call, result)
        return result

    async def _require_pending(
        self,
        user_id: UUID,
        conversation_id: UUID,
        call_id: UUID,
    ) -> ToolCallRecord:
        conv = await self._repo.get_conversation_for_user(conversation_id, user_id)
        if conv is None:
            raise OrchestrationError("conversation not found")
        row = await self._repo.get_tool_call(call_id)
        if row is None or row.status != "pending_confirmation":
            raise OrchestrationError("pending confirmation not found")
        if snapshot_conversation_id(row) != conversation_id:
            raise OrchestrationError("call_id does not belong to this conversation")
        return row

    async def _safe_loop(
        self,
        ctx: ToolContext,
        messages: list[Message],
        budget: RunBudget,
        usage: Usage,
        hitl_rounds: int,
    ) -> AsyncIterator[ChatSseEvent]:
        try:
            async for event in self._loop(ctx, messages, budget, usage, hitl_rounds):
                yield event
        except BudgetExceededError as exc:
            yield ChatSseEvent("error", {"detail": str(exc), "code": "budget_exceeded"})
        except OrchestrationError as exc:
            yield ChatSseEvent("error", {"detail": str(exc)})

    async def _loop(
        self,
        ctx: ToolContext,
        messages: list[Message],
        budget: RunBudget,
        usage: Usage,
        hitl_rounds: int,
    ) -> AsyncIterator[ChatSseEvent]:
        state = _LoopState(ctx, messages, budget, usage, hitl_rounds, "")
        while True:
            state.budget.begin_iter()
            yield ChatSseEvent("step", {"label": _thinking_step_label(state.messages)})
            streamed = _StreamedRound(prefix=bool(state.final_text))
            async for event in streamed.events(
                self._llm,
                self._tool_request(state.messages, state.ctx),
                state.ctx,
            ):
                yield event
            resp = streamed.require_response()
            next_usage = _accumulate(
                state.budget,
                state.usage,
                resp,
                enforce_limits=bool(resp.tool_calls),
            )
            combined_text = _merge_assistant_text(state.final_text, resp.text)
            if not resp.tool_calls:
                state = _next_state(state, next_usage, state.hitl_rounds, combined_text)
                break
            state.messages.append(_assistant_tool_message(resp))
            paused, next_hitl = False, state.hitl_rounds
            async for event in self._run_tools(resp, _tool_round(state, resp, next_usage)):
                yield event
                if event.event == "confirmation_request":
                    paused, next_hitl = True, next_hitl + 1
            if paused:
                return
            state = _next_state(state, next_usage, next_hitl, combined_text)
        yield await self._finish(state.ctx, state.final_text, state.usage, state.budget)

    def _tool_request(
        self,
        messages: list[Message],
        ctx: ToolContext,
    ) -> ToolCallingRequest:
        return ToolCallingRequest(
            messages=messages,
            tools=self._registry.list_specs(ctx.mode),
            max_output_tokens=self._settings.llm.max_output_tokens,
            task="chat_tools",
        )

    async def _run_tools(
        self,
        resp: ToolCallingResponse,
        round_base: _ToolRound,
    ) -> AsyncIterator[ChatSseEvent]:
        for call in resp.tool_calls:
            round_base.budget.check_walltime()
            round_ = _ToolRound(
                round_base.ctx,
                round_base.messages,
                call,
                round_base.budget,
                round_base.usage,
                round_base.hitl_rounds,
            )
            paused = False
            async for event in self._one_tool(round_):
                yield event
                if event.event == "confirmation_request":
                    paused = True
                if paused and event.event == "done":
                    return
            if paused:
                return

    async def _one_tool(self, round_: _ToolRound) -> AsyncIterator[ChatSseEvent]:
        try:
            tool = self._registry.resolve(round_.call.name)
        except ToolNotFoundError as exc:
            async for event in _fail_tool(round_.messages, round_.call, str(exc)):
                yield event
            return
        if tool.risk_level == RiskLevel.CONFIRMATION_REQUIRED:
            pack = _PausePack(
                round_.ctx,
                round_.messages,
                tool,
                round_.call,
                round_.budget,
                round_.usage,
                round_.hitl_rounds,
            )
            async for event in self._pause_for_confirm(pack):
                yield event
            return
        if tool.touches_external:
            round_.budget.add_external()
        yield ChatSseEvent("step", {"label": _tool_step_label(tool.name)})
        result = await execute_tool_call(tool, round_.call, round_.ctx, self._repo)
        _append_tool_message(round_.messages, round_.call, result)
        for event in _tool_outcome_events(tool.name, bool(result.get("ok")), result):
            yield event

    async def _pause_for_confirm(self, pack: _PausePack) -> AsyncIterator[ChatSseEvent]:
        if pack.hitl_rounds >= pack.budget.max_hitl_rounds:
            async for event in _fail_tool(
                pack.messages, pack.call, "max confirmation rounds exceeded"
            ):
                yield event
            return
        try:
            inp = await prepare_gated_call(pack.tool, pack.call, pack.ctx)
        except (ToolAuthzError, ToolValidationError, ToolModeBlockedError) as exc:
            async for event in _fail_tool(pack.messages, pack.call, str(exc)):
                yield event
            return
        proposed = inp.model_dump(mode="json")
        summary = _confirmation_summary(pack.tool.name, proposed)
        row = await freeze_pending(
            FreezeRequest(
                repo=self._repo,
                tool=pack.tool,
                call=pack.call,
                ctx=pack.ctx,
                messages=pack.messages,
                budget=pack.budget,
                usage=pack.usage,
                hitl_rounds=pack.hitl_rounds + 1,
                ttl_seconds=self._settings.llm_runtime.hitl_ttl_seconds,
                proposed=proposed,
                provided_fields=set(pack.call.arguments),
                summary=summary,
            )
        )
        await self._session.commit()
        yield ChatSseEvent("confirmation_request", confirmation_event_data(row, pack.tool))
        yield ChatSseEvent(
            "done",
            {
                "conversation_id": str(pack.ctx.conversation_id),
                "run_id": str(pack.ctx.run_id),
                "call_id": str(row.id),
                "status": "awaiting_confirmation",
                "tokens_in": pack.usage.tokens_in,
                "tokens_out": pack.usage.tokens_out,
                "cost_usd": pack.budget.cost_usd,
                **pack.budget.summary(),
            },
        )

    async def _finish(
        self,
        ctx: ToolContext,
        text: str,
        usage: Usage,
        budget: RunBudget,
    ) -> ChatSseEvent:
        assistant = await self._repo.add_message(
            ctx.conversation_id,
            role=Role.ASSISTANT.value,
            content=text,
            tokens_in=usage.tokens_in,
            tokens_out=usage.tokens_out,
        )
        await self._session.commit()
        return ChatSseEvent(
            "done",
            {
                "message_id": str(assistant.id),
                "conversation_id": str(ctx.conversation_id),
                "run_id": str(ctx.run_id),
                "tokens_in": usage.tokens_in,
                "tokens_out": usage.tokens_out,
                "cost_usd": budget.cost_usd,
                "status": "complete",
                **budget.summary(),
            },
        )

    async def _check_llm_quota(self, user: UserRead) -> None:
        """Reject the turn BEFORE any provider call when a monthly LLM quota is hit.

        Sits before conversation-context build on purpose: context building can
        itself trigger a summarization provider call. Resume-confirm does not
        re-check — it is the same turn (spec §3.5).

        Hybrid read (usage spec §7): closed days come from usage_daily, today
        live from llm_executions — so the raw scan is one day, not one month.
        """
        quotas = QuotaService(self._session)
        limits = await quotas.limits_for(user)
        if not limits.any_limited(QuotaKind.LLM_TOKENS, QuotaKind.LLM_COST_USD):
            return
        now = datetime.now(UTC)
        _, end = QuotaService.current_month_window(now)
        _, today_start = UsageReadService.hybrid_split(now)
        usage = UsageReadService(self._session)
        summary = await self._llm.usage_summary(user.id, period_start=today_start, period_end=end)
        tokens = (
            await usage.rolled_month_amount(user.id, QuotaKind.LLM_TOKENS, now)
            + summary.tokens_in
            + summary.tokens_out
        )
        QuotaService.enforce(QuotaKind.LLM_TOKENS, tokens, limits, resets_at=end, user_id=user.id)
        cost = (
            await usage.rolled_month_amount(user.id, QuotaKind.LLM_COST_USD, now)
            + summary.total_cost
        )
        QuotaService.enforce(QuotaKind.LLM_COST_USD, cost, limits, resets_at=end, user_id=user.id)

    def _make_ctx(self, user_id: UUID, conversation_id: UUID, run_id: UUID) -> ToolContext:
        return ToolContext(
            user_id=user_id,
            conversation_id=conversation_id,
            run_id=run_id,
            mode=_parse_mode(self._settings.llm_runtime.assistant_mode),
            session=self._session,
        )


def _assistant_tool_message(resp: ToolCallingResponse) -> Message:
    return Message(
        role=Role.ASSISTANT,
        content=resp.text or "",
        tool_calls=tuple(resp.tool_calls),
    )


def _confirmation_summary(tool_name: str, proposed: dict[str, Any]) -> str:
    if "url" in proposed:
        return f"Scrape from {proposed['url']}"
    if tool_name == "create_audio_download":
        return (
            f"Create audio for chapters {proposed.get('chapter_from')}-"
            f"{proposed.get('chapter_to')}"
        )
    return f"Confirm {tool_name}"


def _tool_round(
    state: _LoopState,
    resp: ToolCallingResponse,
    usage: Usage,
) -> _ToolRound:
    return _ToolRound(
        state.ctx,
        state.messages,
        resp.tool_calls[0],
        state.budget,
        usage,
        state.hitl_rounds,
    )


def _next_state(
    state: _LoopState,
    usage: Usage,
    hitl_rounds: int,
    final_text: str,
) -> _LoopState:
    return _LoopState(
        state.ctx,
        state.messages,
        state.budget,
        usage,
        hitl_rounds,
        final_text,
    )


def _merge_assistant_text(existing: str, current: str | None) -> str:
    if not current:
        return existing
    if not existing:
        return current
    return f"{existing}\n\n{current}"


def _tool_step_label(name: str) -> str:
    if name == "summarize_book":
        return "Reading chapters and generating a summary…"
    if name == "get_book_summary":
        return "Checking the saved summary…"
    labels = {
        "search_user_books": "Searching your library…",
        "search_library_content": "Searching book content…",
        "list_available_chapters": "Finding the relevant chapters…",
        "get_chapter_content": "Reading the chapter…",
        "search_discovered_books": "Searching supported book sites…",
    }
    return labels.get(name, f"Running {name.replace('_', ' ')}…")


def _thinking_step_label(messages: list[Message]) -> str:
    if messages and messages[-1].role == Role.TOOL:
        return "Reviewing the results and writing your answer…"
    return "Understanding your request…"


def _parse_mode(raw: str) -> Mode:
    try:
        return Mode(raw)
    except ValueError:
        return Mode.INTERNAL_ONLY


def _to_llm_messages(
    history: list[ConversationMessage],
    *,
    summary: str | None = None,
    ui_context: dict[str, Any] | None = None,
) -> list[Message]:
    messages = [Message(role=Role.SYSTEM, content=SYSTEM_PROMPT)]
    if summary:
        messages.append(Message(role=Role.SYSTEM, content=summary_context_block(summary)))
    block = format_ui_context_block(ui_context)
    if block:
        messages.append(Message(role=Role.SYSTEM, content=block))
    for row in history:
        try:
            role = Role(row.role)
        except ValueError:
            continue
        if role == Role.SYSTEM:
            continue
        messages.append(Message(role=role, content=row.content))
    return messages


def _tool_outcome_events(name: str, ok: bool, result: dict[str, object]) -> list[ChatSseEvent]:
    events = [_tool_result_event(name, ok, result)]
    data = result.get("data") if ok else None
    choice = choice_request_for_tool(name, ok, data if isinstance(data, dict) else None)
    if choice:
        events.append(ChatSseEvent("choice_request", choice))
    return events


def _tool_result_event(name: str, ok: bool, result: dict[str, object]) -> ChatSseEvent:
    data = result.get("data") if ok else None
    payload: dict[str, object] = {
        "name": name,
        "ok": ok,
        "summary": _summarize_result(result),
    }
    action = client_action_for_tool(name, ok, data if isinstance(data, dict) else None)
    if action:
        payload["client_action"] = action
    return ChatSseEvent("tool_result", payload)


def _accumulate(
    budget: RunBudget,
    usage_total: Usage,
    resp: ToolCallingResponse,
    *,
    enforce_limits: bool,
) -> Usage:
    cost = resp.usage.cost_usd if resp.usage.cost_usd is not None else 0.0
    budget.add_usage(resp.usage, cost_usd=cost, enforce_limits=enforce_limits)
    return Usage(
        usage_total.tokens_in + resp.usage.tokens_in,
        usage_total.tokens_out + resp.usage.tokens_out,
    )


def _quota_error_event(exc: QuotaExceededError) -> ChatSseEvent:
    """Structured SSE error the frontend maps to user copy (spec §6)."""
    return ChatSseEvent(
        "error",
        {
            "code": "quota_exceeded",
            "kind": exc.kind.value,
            "detail": str(exc),
            "resets_at": exc.resets_at.isoformat() if exc.resets_at else None,
        },
    )


async def _fail_tool(
    messages: list[Message],
    call: ToolCall,
    error: str,
) -> AsyncIterator[ChatSseEvent]:
    result = {"ok": False, "tool": call.name, "error": error}
    _append_tool_message(messages, call, result)
    yield ChatSseEvent("tool_result", {"name": call.name, "ok": False, "summary": error})


def _append_tool_message(
    messages: list[Message],
    call: ToolCall,
    result: dict[str, object],
) -> None:
    payload = json.dumps(result, ensure_ascii=False)
    if len(payload) > _MAX_TOOL_RESULT_CHARS:
        payload = payload[: _MAX_TOOL_RESULT_CHARS - 14] + "…[truncated]"
    messages.append(
        Message(
            role=Role.TOOL,
            content=payload,
            name=str(result.get("tool") or call.name),
            tool_call_id=call.id,
        )
    )


def _summarize_result(result: dict[str, object]) -> str:
    if not result.get("ok"):
        return str(result.get("error") or "tool failed")
    data = result.get("data")
    if not isinstance(data, dict):
        return "ok"
    return _summarize_ok_data(data)


def _confirmed_terminal_text(tool_name: str, result: dict[str, object]) -> str | None:
    """Use deterministic post-confirm copy for async jobs the UI will track."""
    if tool_name != "create_audio_download" or not result.get("ok"):
        return None
    summary = _summarize_result(result)
    return f"{summary} Progress will appear here, and the MP3 will download when ready."


def _summarize_ok_data(data: dict[str, object]) -> str:
    message = data.get("message")
    if isinstance(message, str) and message.strip():
        return message
    hits = data.get("hits")
    if isinstance(hits, list):
        return f"{len(hits)} content hit(s)"
    if "job_id" in data:
        text: object = f"job {data['job_id']}"
    elif data.get("total") is not None:
        text = f"{data['total']} book(s)"
    else:
        text = data.get("title") or "ok"
    return str(text)
