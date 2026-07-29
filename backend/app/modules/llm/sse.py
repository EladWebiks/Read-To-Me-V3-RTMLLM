"""SSE event types shared by chat and orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

ChatEventKind = Literal[
    "meta",
    "delta",
    "done",
    "error",
    "step",
    "tool_result",
    "confirmation_request",
    "choice_request",
]


@dataclass(frozen=True, slots=True)
class ChatSseEvent:
    """One SSE payload for the chat stream."""

    event: ChatEventKind
    data: dict[str, Any]

    def encode(self) -> str:
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"
