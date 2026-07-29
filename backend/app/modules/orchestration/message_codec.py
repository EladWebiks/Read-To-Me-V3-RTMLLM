"""Serialize orchestration Message lists for HITL pause/resume."""

from __future__ import annotations

import base64
from typing import Any

from app.modules.llm.types import Message, Role, ToolCall


def dump_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """JSON-safe snapshot of in-memory tool-loop messages."""
    return [_dump_one(m) for m in messages]


def load_messages(raw: list[dict[str, Any]]) -> list[Message]:
    """Restore messages from a HITL snapshot."""
    return [_load_one(item) for item in raw]


def _dump_one(message: Message) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "role": message.role.value,
        "content": message.content,
        "name": message.name,
        "tool_call_id": message.tool_call_id,
        "tool_calls": [_dump_call(c) for c in message.tool_calls],
    }
    return payload


def _dump_call(call: ToolCall) -> dict[str, Any]:
    sig = None
    if call.thought_signature is not None:
        sig = base64.b64encode(call.thought_signature).decode("ascii")
    return {
        "id": call.id,
        "name": call.name,
        "arguments": call.arguments,
        "thought_signature": sig,
    }


def _load_one(item: dict[str, Any]) -> Message:
    calls = tuple(_load_call(c) for c in item.get("tool_calls") or [])
    return Message(
        role=Role(str(item["role"])),
        content=str(item.get("content") or ""),
        name=item.get("name"),
        tool_call_id=item.get("tool_call_id"),
        tool_calls=calls,
    )


def _load_call(item: dict[str, Any]) -> ToolCall:
    sig_raw = item.get("thought_signature")
    sig = base64.b64decode(sig_raw) if isinstance(sig_raw, str) else None
    return ToolCall(
        id=str(item["id"]),
        name=str(item["name"]),
        arguments=dict(item.get("arguments") or {}),
        thought_signature=sig,
    )
