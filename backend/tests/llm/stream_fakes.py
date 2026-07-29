"""Helpers for orchestration tests that do not exercise provider streaming."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from app.modules.llm.types import (
    ToolCallingRequest,
    ToolCallingResponse,
    ToolCallingStreamChunk,
)

ToolCallFake = Callable[..., Awaitable[ToolCallingResponse]]


def stream_from_call(fake: ToolCallFake) -> Callable[..., AsyncIterator[ToolCallingStreamChunk]]:
    """Adapt a completed-response fake to the streaming service contract."""

    async def _stream(
        req: ToolCallingRequest,
        **kwargs: Any,
    ) -> AsyncIterator[ToolCallingStreamChunk]:
        response = await fake(req, **kwargs)
        if response.text:
            yield ToolCallingStreamChunk(text=response.text)
        yield ToolCallingStreamChunk(done=True, response=response)

    return _stream
