"""Normalized LLM request/response types (provider-agnostic)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class Role(StrEnum):
    """Chat message role."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class ToolCall:
    """Model-proposed tool invocation."""

    id: str
    name: str
    arguments: dict[str, Any]
    # Opaque provider state (e.g. Gemini thought_signature) for multi-turn tool loops.
    thought_signature: bytes | None = None


@dataclass(frozen=True, slots=True)
class Message:
    """One chat turn."""

    role: Role
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True, slots=True)
class Usage:
    """Token accounting for one call."""

    tokens_in: int
    tokens_out: int
    cost_usd: float | None = None


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Tool schema exposed to the model (JSON-schema friendly)."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True, slots=True)
class GenerateTextRequest:
    """Plain text generation / chat completion."""

    messages: Sequence[Message]
    max_output_tokens: int | None = None
    temperature: float | None = None
    task: str = "chat"


@dataclass(frozen=True, slots=True)
class GenerateTextResponse:
    """Completed text generation."""

    text: str
    usage: Usage
    model: str
    provider: str
    finish_reason: str | None = None


@dataclass(frozen=True, slots=True)
class StreamChunk:
    """One streaming delta."""

    text: str
    done: bool = False
    usage: Usage | None = None


@dataclass(frozen=True, slots=True)
class StructuredOutputRequest[T: BaseModel]:
    """Request a pydantic-validated structured response."""

    messages: Sequence[Message]
    response_model: type[T]
    max_output_tokens: int | None = None
    temperature: float | None = None
    task: str = "structured"
    # When true, providers that support it may use live web search (e.g. Gemini
    # Google Search grounding) before coercing into response_model.
    use_web_search: bool = False


@dataclass(frozen=True, slots=True)
class ToolCallingRequest:
    """Chat turn that may emit tool calls."""

    messages: Sequence[Message]
    tools: Sequence[ToolSpec]
    max_output_tokens: int | None = None
    temperature: float | None = None
    task: str = "tools"


@dataclass(frozen=True, slots=True)
class ToolCallingResponse:
    """Assistant message plus any tool calls."""

    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=lambda: Usage(0, 0))
    model: str = ""
    provider: str = ""


@dataclass(frozen=True, slots=True)
class ToolCallingStreamChunk:
    """One tool-capable stream event; terminal chunk carries the normalized response."""

    text: str = ""
    done: bool = False
    response: ToolCallingResponse | None = None


@dataclass(frozen=True, slots=True)
class EmbeddingRequest:
    """Embed one or more texts."""

    texts: Sequence[str]
    task: str = "embed"


@dataclass(frozen=True, slots=True)
class EmbeddingResponse:
    """Embedding vectors aligned with input texts."""

    vectors: list[list[float]]
    usage: Usage
    model: str
    provider: str
