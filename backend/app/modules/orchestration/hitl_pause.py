"""HITL pause persistence for the orchestration loop."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.modules.llm.models import ToolCallRecord
from app.modules.llm.repository import LlmRepository, ToolCallWrite
from app.modules.llm.types import Message, ToolCall, Usage
from app.modules.orchestration.budget import RunBudget
from app.modules.orchestration.message_codec import dump_messages, load_messages
from app.modules.tools.base import BaseTool, ToolContext
from app.modules.tools.hitl import build_form_payload


@dataclass(frozen=True, slots=True)
class FreezeRequest:
    """Inputs for persisting a pending confirmation."""

    repo: LlmRepository
    tool: BaseTool
    call: ToolCall
    ctx: ToolContext
    messages: list[Message]
    budget: RunBudget
    usage: Usage
    hitl_rounds: int
    ttl_seconds: int
    proposed: dict[str, Any]
    summary: str


async def freeze_pending(req: FreezeRequest) -> ToolCallRecord:
    """Persist pending_confirmation + message snapshot; return the audit row."""
    expires = datetime.now(UTC) + timedelta(seconds=req.ttl_seconds)
    snapshot = {
        "kind": "hitl_pending",
        "conversation_id": str(req.ctx.conversation_id),
        "run_id": str(req.ctx.run_id),
        "provider_call_id": req.call.id,
        "messages": dump_messages(req.messages),
        "usage": {
            "tokens_in": req.usage.tokens_in,
            "tokens_out": req.usage.tokens_out,
        },
        "budget": {
            "cost_usd": req.budget.cost_usd,
            "iters": req.budget.iters,
            "external_calls": req.budget.external_calls,
            "tokens_in": req.budget.tokens_in,
            "tokens_out": req.budget.tokens_out,
        },
        "hitl_rounds": req.hitl_rounds,
        "expires_at": expires.isoformat(),
        "summary": req.summary,
        "form": build_form_payload(req.tool, req.proposed),
        "risk": req.tool.risk_level.value,
    }
    return await req.repo.record_tool_call(
        ToolCallWrite(
            tool_name=req.tool.name,
            input_data=req.proposed,
            output_data=snapshot,
            status="pending_confirmation",
            risk_level=req.tool.risk_level.value,
            confirmed_by_user=False,
        )
    )


def confirmation_event_data(row: ToolCallRecord, tool: BaseTool) -> dict[str, Any]:
    """SSE confirmation_request payload."""
    snap = row.output or {}
    return {
        "call_id": str(row.id),
        "tool": tool.name,
        "risk": tool.risk_level.value,
        "summary": snap.get("summary") or f"Confirm {tool.name}",
        "args": row.input,
        "form": snap.get("form"),
    }


def restore_snapshot(
    row: ToolCallRecord,
) -> tuple[list[Message], Usage, dict[str, float | int], int, str]:
    """Load messages, usage, budget counters, hitl_rounds, provider_call_id."""
    snap = row.output or {}
    if snap.get("kind") != "hitl_pending":
        raise ValueError("tool_call is not a HITL pending snapshot")
    messages = load_messages(list(snap.get("messages") or []))
    usage_raw = snap.get("usage") or {}
    usage = Usage(int(usage_raw.get("tokens_in") or 0), int(usage_raw.get("tokens_out") or 0))
    budget_raw = dict(snap.get("budget") or {})
    if "cost_usd" not in budget_raw and snap.get("cost_usd") is not None:
        budget_raw["cost_usd"] = float(snap["cost_usd"])
    hitl_rounds = int(snap.get("hitl_rounds") or 0)
    provider_call_id = str(snap.get("provider_call_id") or "")
    return messages, usage, budget_raw, hitl_rounds, provider_call_id


def apply_budget_snapshot(budget: RunBudget, raw: dict[str, float | int]) -> None:
    """Restore counters so resume continues under the same caps."""
    budget.cost_usd = float(raw.get("cost_usd") or 0.0)
    budget.iters = int(raw.get("iters") or 0)
    budget.external_calls = int(raw.get("external_calls") or 0)
    budget.tokens_in = int(raw.get("tokens_in") or 0)
    budget.tokens_out = int(raw.get("tokens_out") or 0)


def is_expired(row: ToolCallRecord) -> bool:
    snap = row.output or {}
    raw = snap.get("expires_at")
    if not isinstance(raw, str):
        return False
    expires = datetime.fromisoformat(raw)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return datetime.now(UTC) >= expires


def snapshot_conversation_id(row: ToolCallRecord) -> UUID | None:
    snap = row.output or {}
    raw = snap.get("conversation_id")
    if not raw:
        return None
    return UUID(str(raw))


def snapshot_run_id(row: ToolCallRecord) -> UUID | None:
    snap = row.output or {}
    raw = snap.get("run_id")
    if not raw:
        return None
    return UUID(str(raw))
