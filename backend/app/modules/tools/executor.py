"""Validate → authz → mode → (confirm) → execute → audit for one tool call."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError

from app.modules.llm.repository import LlmRepository, ToolCallWrite
from app.modules.llm.types import ToolCall
from app.modules.tools.base import BaseTool, Mode, RiskLevel, ToolContext
from app.modules.tools.exceptions import (
    ToolAuthzError,
    ToolConfirmationRequiredError,
    ToolModeBlockedError,
    ToolValidationError,
)

_CONTRACT_ERRORS = (
    ToolAuthzError,
    ToolValidationError,
    ToolModeBlockedError,
    ToolConfirmationRequiredError,
)


@dataclass(frozen=True, slots=True)
class ExecuteOptions:
    """Optional execute_tool_call knobs (HITL resume)."""

    message_id: UUID | None = None
    confirmed: bool = False
    arguments: dict[str, Any] | None = None
    audit: bool = True


@dataclass(frozen=True, slots=True)
class _AuditFields:
    status: str
    output: dict[str, Any] | None
    duration_ms: int
    error: str | None
    confirmed_by_user: bool = False


async def execute_tool_call(
    tool: BaseTool,
    call: ToolCall,
    ctx: ToolContext,
    repo: LlmRepository,
    options: ExecuteOptions | None = None,
) -> dict[str, Any]:
    """Run the execution contract; return a JSON-serializable result dict."""
    opts = options or ExecuteOptions()
    started = time.perf_counter()
    args = call.arguments if opts.arguments is None else opts.arguments
    try:
        return await _execute_ok(tool, args, ctx, repo, opts, started)
    except _CONTRACT_ERRORS as exc:
        fields = _AuditFields("denied", None, _ms(started), str(exc), opts.confirmed)
        return await _fail_result(tool, args, repo, opts, fields)
    except Exception as exc:
        fields = _AuditFields("error", None, _ms(started), str(exc), opts.confirmed)
        return await _fail_result(tool, args, repo, opts, fields)


async def prepare_gated_call(
    tool: BaseTool,
    call: ToolCall,
    ctx: ToolContext,
) -> BaseModel:
    """Validate + authorize + mode-gate without executing (HITL propose)."""
    inp = _parse_input(tool, call.arguments)
    await tool.authorize(inp, ctx)
    _gate_mode(tool, ctx)
    if tool.risk_level != RiskLevel.CONFIRMATION_REQUIRED:
        raise ToolValidationError(f"{tool.name} is not confirmation_required")
    return inp


async def _execute_ok(
    tool: BaseTool,
    args: dict[str, Any],
    ctx: ToolContext,
    repo: LlmRepository,
    opts: ExecuteOptions,
    started: float,
) -> dict[str, Any]:
    inp = _parse_input(tool, args)
    await tool.authorize(inp, ctx)
    _gate_mode(tool, ctx)
    if not opts.confirmed:
        _gate_confirmation(tool)
    out = await tool.execute(inp, ctx)
    payload = out.model_dump(mode="json")
    if opts.audit:
        await _audit(
            repo,
            tool,
            args,
            opts.message_id,
            _AuditFields("success", payload, _ms(started), None, opts.confirmed),
        )
    return {"ok": True, "tool": tool.name, "data": payload}


async def _fail_result(
    tool: BaseTool,
    args: dict[str, Any],
    repo: LlmRepository,
    opts: ExecuteOptions,
    fields: _AuditFields,
) -> dict[str, Any]:
    if opts.audit:
        await _audit(repo, tool, args, opts.message_id, fields)
    return {"ok": False, "tool": tool.name, "error": fields.error or "error"}


def _parse_input(tool: BaseTool, arguments: dict[str, Any]) -> BaseModel:
    try:
        return tool.input_model.model_validate(arguments)
    except ValidationError as exc:
        raise ToolValidationError(str(exc)) from exc


def _gate_mode(tool: BaseTool, ctx: ToolContext) -> None:
    if ctx.mode == Mode.INTERNAL_ONLY and tool.touches_external:
        raise ToolModeBlockedError(f"{tool.name} touches external network")
    if ctx.mode == Mode.INTERNAL_ONLY and not tool.allowed_in_internal_only:
        raise ToolModeBlockedError(f"{tool.name} not allowed in internal_only")


def _gate_confirmation(tool: BaseTool) -> None:
    if tool.risk_level == RiskLevel.CONFIRMATION_REQUIRED:
        raise ToolConfirmationRequiredError(tool.name)


async def _audit(
    repo: LlmRepository,
    tool: BaseTool,
    arguments: dict[str, Any],
    message_id: UUID | None,
    fields: _AuditFields,
) -> None:
    await repo.record_tool_call(
        ToolCallWrite(
            message_id=message_id,
            tool_name=tool.name,
            input_data=dict(arguments),
            output_data=fields.output,
            status=fields.status,
            duration_ms=fields.duration_ms,
            risk_level=tool.risk_level.value,
            confirmed_by_user=fields.confirmed_by_user,
            error=fields.error,
        )
    )


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
