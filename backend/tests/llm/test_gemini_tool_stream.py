"""Gemini tool-stream normalization tests without network access."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest
from app.modules.llm.exceptions import LlmProviderError, LlmTimeoutError
from app.modules.llm.providers.gemini_provider import GeminiProvider, GeminiProviderConfig
from app.modules.llm.types import (
    Message,
    Role,
    ToolCallingRequest,
    ToolSpec,
)


def _part(name: str, arguments: object) -> SimpleNamespace:
    return SimpleNamespace(
        function_call=SimpleNamespace(name=name, args=arguments, id=None),
        thought_signature=None,
    )


def _chunk(
    *,
    text: str = "",
    parts: list[object] | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
) -> SimpleNamespace:
    candidate = SimpleNamespace(content=SimpleNamespace(parts=parts or []))
    usage = SimpleNamespace(
        prompt_token_count=tokens_in,
        candidates_token_count=tokens_out,
    )
    return SimpleNamespace(text=text, candidates=[candidate], usage_metadata=usage)


def _request() -> ToolCallingRequest:
    return ToolCallingRequest(
        messages=[Message(role=Role.USER, content="find a book")],
        tools=[ToolSpec(name="search", description="Search", parameters={"type": "object"})],
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_gemini_streams_text_and_assembles_fragmented_tool_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = GeminiProvider(GeminiProviderConfig(api_key="test", model_name="gemini-test"))

    async def _raw_stream() -> AsyncIterator[Any]:
        yield _chunk(text="Checking ", parts=[_part("search", '{"query":')])
        yield _chunk(
            text="now.", parts=[_part("search", '"Defiance"}')], tokens_in=9, tokens_out=4
        )

    async def _open(_req: ToolCallingRequest) -> AsyncIterator[Any]:
        return _raw_stream()

    monkeypatch.setattr(provider, "_open_tool_stream", _open)
    chunks = [chunk async for chunk in provider.stream_tools(_request())]

    assert "".join(chunk.text for chunk in chunks) == "Checking now."
    response = chunks[-1].response
    assert response is not None
    assert response.tool_calls[0].arguments == {"query": "Defiance"}
    assert response.usage.tokens_in == 9


@pytest.mark.unit
@pytest.mark.asyncio
async def test_gemini_rejects_incomplete_streamed_tool_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = GeminiProvider(GeminiProviderConfig(api_key="test", model_name="gemini-test"))

    async def _raw_stream() -> AsyncIterator[Any]:
        yield _chunk(parts=[_part("search", '{"query":')])

    async def _open(_req: ToolCallingRequest) -> AsyncIterator[Any]:
        return _raw_stream()

    monkeypatch.setattr(provider, "_open_tool_stream", _open)

    with pytest.raises(LlmProviderError, match="Incomplete"):
        _chunks = [chunk async for chunk in provider.stream_tools(_request())]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_gemini_normalizes_tool_only_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = GeminiProvider(GeminiProviderConfig(api_key="test", model_name="gemini-test"))

    async def _raw_stream() -> AsyncIterator[Any]:
        yield _chunk(parts=[_part("search", {"query": "Defiance"})], tokens_in=5)

    async def _open(_req: ToolCallingRequest) -> AsyncIterator[Any]:
        return _raw_stream()

    monkeypatch.setattr(provider, "_open_tool_stream", _open)
    chunks = [chunk async for chunk in provider.stream_tools(_request())]

    assert chunks[0].done is True
    assert chunks[0].response is not None
    assert chunks[0].response.tool_calls[0].name == "search"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_gemini_maps_errors_raised_during_stream_iteration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = GeminiProvider(GeminiProviderConfig(api_key="test", model_name="gemini-test"))

    async def _raw_stream() -> AsyncIterator[Any]:
        if False:
            yield _chunk()
        raise TimeoutError("stream timed out")

    async def _open(_req: ToolCallingRequest) -> AsyncIterator[Any]:
        return _raw_stream()

    monkeypatch.setattr(provider, "_open_tool_stream", _open)

    with pytest.raises(LlmTimeoutError):
        _chunks = [chunk async for chunk in provider.stream_tools(_request())]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_closing_gemini_tool_stream_closes_provider_iterator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = GeminiProvider(GeminiProviderConfig(api_key="test", model_name="gemini-test"))
    closed = asyncio.Event()

    async def _raw_stream() -> AsyncIterator[Any]:
        try:
            yield _chunk(text="first")
            await asyncio.Event().wait()
        finally:
            closed.set()

    async def _open(_req: ToolCallingRequest) -> AsyncIterator[Any]:
        return _raw_stream()

    monkeypatch.setattr(provider, "_open_tool_stream", _open)
    stream = provider.stream_tools(_request())
    assert (await anext(stream)).text == "first"

    await stream.aclose()

    assert closed.is_set()
