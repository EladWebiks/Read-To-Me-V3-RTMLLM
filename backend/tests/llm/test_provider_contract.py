"""Offline LLMProvider contract suite using a fake adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from app.modules.llm.exceptions import CapabilityNotSupportedError
from app.modules.llm.types import (
    EmbeddingRequest,
    EmbeddingResponse,
    GenerateTextRequest,
    GenerateTextResponse,
    Message,
    Role,
    StreamChunk,
    StructuredOutputRequest,
    ToolCallingRequest,
    ToolCallingResponse,
    ToolCallingStreamChunk,
    ToolSpec,
    Usage,
)
from pydantic import BaseModel, Field


class _FakeOut(BaseModel):
    title: str = Field(description="book title")


class FakeProvider:
    """In-memory provider satisfying the LLMProvider contract."""

    def __init__(self, *, supports_tools: bool = True) -> None:
        self._supports_tools = supports_tools

    @property
    def name(self) -> str:
        return "fake"

    async def generate_text(self, req: GenerateTextRequest) -> GenerateTextResponse:
        last = req.messages[-1].content if req.messages else ""
        return GenerateTextResponse(
            text=f"echo:{last}",
            usage=Usage(tokens_in=3, tokens_out=2),
            model="fake-model",
            provider=self.name,
            finish_reason="stop",
        )

    async def stream_text(self, req: GenerateTextRequest) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(text="hel", done=False)
        yield StreamChunk(text="lo", done=False)
        yield StreamChunk(text="", done=True)

    async def generate_structured_output(
        self,
        req: StructuredOutputRequest[_FakeOut],
    ) -> _FakeOut:
        return req.response_model(title="Demo")

    async def call_tools(self, req: ToolCallingRequest) -> ToolCallingResponse:
        if not self._supports_tools:
            raise CapabilityNotSupportedError("tools")
        return ToolCallingResponse(
            text=None,
            tool_calls=[],
            usage=Usage(1, 1),
            model="fake-model",
            provider=self.name,
        )

    async def stream_tools(
        self,
        req: ToolCallingRequest,
    ) -> AsyncIterator[ToolCallingStreamChunk]:
        response = await self.call_tools(req)
        yield ToolCallingStreamChunk(text="answer")
        yield ToolCallingStreamChunk(done=True, response=response)

    async def create_embeddings(self, req: EmbeddingRequest) -> EmbeddingResponse:
        raise CapabilityNotSupportedError("embeddings")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_text_normalized() -> None:
    provider = FakeProvider()
    resp = await provider.generate_text(
        GenerateTextRequest(messages=[Message(role=Role.USER, content="hi")])
    )
    assert resp.text.startswith("echo:")
    assert resp.usage.tokens_in == 3
    assert resp.provider == "fake"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stream_text_chunks() -> None:
    provider = FakeProvider()
    chunks = [
        c
        async for c in provider.stream_text(
            GenerateTextRequest(messages=[Message(role=Role.USER, content="x")])
        )
    ]
    assert "".join(c.text for c in chunks if not c.done) == "hello"
    assert chunks[-1].done is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_structured_output_validates() -> None:
    provider = FakeProvider()
    out = await provider.generate_structured_output(
        StructuredOutputRequest(
            messages=[Message(role=Role.USER, content="extract")],
            response_model=_FakeOut,
        )
    )
    assert out.title == "Demo"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_feature_detection() -> None:
    provider = FakeProvider(supports_tools=False)
    with pytest.raises(CapabilityNotSupportedError):
        await provider.call_tools(
            ToolCallingRequest(
                messages=[Message(role=Role.USER, content="go")],
                tools=[
                    ToolSpec(
                        name="search",
                        description="search books",
                        parameters={"type": "object", "properties": {}},
                    )
                ],
            )
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_stream_has_deltas_and_terminal_response() -> None:
    provider = FakeProvider()
    request = ToolCallingRequest(
        messages=[Message(role=Role.USER, content="go")],
        tools=[],
    )

    chunks = [chunk async for chunk in provider.stream_tools(request)]

    assert chunks[0].text == "answer"
    assert chunks[-1].done is True
    assert chunks[-1].response is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_embeddings_unsupported() -> None:
    provider = FakeProvider()
    with pytest.raises(CapabilityNotSupportedError):
        await provider.create_embeddings(EmbeddingRequest(texts=["a"]))
