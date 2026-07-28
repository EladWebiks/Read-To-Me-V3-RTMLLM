"""LLMProvider protocol — the only contract callers depend on."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, TypeVar

from pydantic import BaseModel

from app.modules.llm.types import (
    EmbeddingRequest,
    EmbeddingResponse,
    GenerateTextRequest,
    GenerateTextResponse,
    StreamChunk,
    StructuredOutputRequest,
    ToolCallingRequest,
    ToolCallingResponse,
)

T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
    """Vendor-agnostic LLM adapter."""

    @property
    def name(self) -> str:
        """Provider id (e.g. gemini)."""

    async def generate_text(self, req: GenerateTextRequest) -> GenerateTextResponse:
        """Complete a chat turn as plain text."""

    async def stream_text(
        self,
        req: GenerateTextRequest,
    ) -> AsyncIterator[StreamChunk]:
        """Stream text deltas (async iterator)."""
        ...

    async def generate_structured_output(
        self,
        req: StructuredOutputRequest[T],
    ) -> T:
        """Return a pydantic-validated structured object."""
        ...

    async def call_tools(self, req: ToolCallingRequest) -> ToolCallingResponse:
        """Complete a turn that may include tool calls."""

    async def create_embeddings(self, req: EmbeddingRequest) -> EmbeddingResponse:
        """Embed texts; may raise CapabilityNotSupportedError."""
