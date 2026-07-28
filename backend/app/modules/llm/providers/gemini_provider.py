"""Gemini adapter — google-genai SDK stays inside this package only."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar, cast

from pydantic import BaseModel

from app.modules.llm.exceptions import (
    CapabilityNotSupportedError,
    LlmProviderError,
    LlmRateLimitError,
    LlmTimeoutError,
)
from app.modules.llm.types import (
    EmbeddingRequest,
    EmbeddingResponse,
    GenerateTextRequest,
    GenerateTextResponse,
    Message,
    Role,
    StreamChunk,
    StructuredOutputRequest,
    ToolCall,
    ToolCallingRequest,
    ToolCallingResponse,
    ToolSpec,
    Usage,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class GeminiProviderConfig:
    """Construction options for GeminiProvider."""

    api_key: str
    model_name: str
    timeout_seconds: int = 30
    max_output_tokens: int = 2048
    max_retries: int = 2
    supports_tools: bool = True
    supports_structured: bool = True
    supports_streaming: bool = True


class GeminiProvider:
    """LLMProvider for Google Gemini via google-genai (+ instructor)."""

    def __init__(self, config: GeminiProviderConfig) -> None:
        self._config = config
        self._client: Any | None = None

    @property
    def name(self) -> str:
        return "gemini"

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._config.api_key)
        return self._client

    async def generate_text(self, req: GenerateTextRequest) -> GenerateTextResponse:
        raw = await self._generate(
            contents=_to_contents(req.messages),
            max_tokens=req.max_output_tokens or self._config.max_output_tokens,
            temperature=req.temperature,
        )
        return GenerateTextResponse(
            text=_response_text(raw),
            usage=_usage_from(raw),
            model=self._config.model_name,
            provider=self.name,
            finish_reason=_finish_reason(raw),
        )

    async def stream_text(self, req: GenerateTextRequest) -> AsyncIterator[StreamChunk]:
        if not self._config.supports_streaming:
            raise CapabilityNotSupportedError("streaming")
        stream = await self._open_stream(req)
        async for chunk in stream:
            text = _response_text(chunk)
            if text:
                yield StreamChunk(text=text, done=False)
        yield StreamChunk(text="", done=True)

    async def generate_structured_output(
        self,
        req: StructuredOutputRequest[T],
    ) -> T:
        if not self._config.supports_structured:
            raise CapabilityNotSupportedError("structured_output")
        return await self._structured(req)

    async def call_tools(self, req: ToolCallingRequest) -> ToolCallingResponse:
        if not self._config.supports_tools:
            raise CapabilityNotSupportedError("tools")
        raw = await self._generate(
            contents=_to_contents(req.messages),
            max_tokens=req.max_output_tokens or self._config.max_output_tokens,
            temperature=req.temperature,
            tools=[_tool_to_genai(t) for t in req.tools],
        )
        return ToolCallingResponse(
            text=_response_text(raw) or None,
            tool_calls=_parse_tool_calls(raw),
            usage=_usage_from(raw),
            model=self._config.model_name,
            provider=self.name,
        )

    async def create_embeddings(self, req: EmbeddingRequest) -> EmbeddingResponse:
        raise CapabilityNotSupportedError("embeddings")

    async def _generate(self, **kwargs: Any) -> Any:
        from google.genai import types

        client = self._get_client()
        config = types.GenerateContentConfig(
            max_output_tokens=kwargs.pop("max_tokens", self._config.max_output_tokens),
            temperature=kwargs.pop("temperature", None),
            tools=kwargs.pop("tools", None),
            http_options=types.HttpOptions(timeout=self._config.timeout_seconds * 1000),
        )
        try:
            return await client.aio.models.generate_content(
                model=self._config.model_name,
                contents=kwargs["contents"],
                config=config,
            )
        except Exception as exc:
            raise _map_provider_error(exc) from exc

    async def _open_stream(self, req: GenerateTextRequest) -> Any:
        from google.genai import types

        client = self._get_client()
        config = types.GenerateContentConfig(
            max_output_tokens=req.max_output_tokens or self._config.max_output_tokens,
            temperature=req.temperature,
            http_options=types.HttpOptions(timeout=self._config.timeout_seconds * 1000),
        )
        try:
            return await client.aio.models.generate_content_stream(
                model=self._config.model_name,
                contents=_to_contents(req.messages),
                config=config,
            )
        except Exception as exc:
            raise _map_provider_error(exc) from exc

    async def _structured(self, req: StructuredOutputRequest[T]) -> T:
        import instructor
        from google import genai

        client = instructor.from_genai(genai.Client(api_key=self._config.api_key))
        try:
            # instructor stubs for from_genai disagree with the async create API.
            create = cast(Any, client.chat.completions.create)
            result = await create(
                model=self._config.model_name,
                messages=_to_openai_messages(req.messages),
                response_model=req.response_model,
                max_retries=self._config.max_retries,
            )
            return cast(T, result)
        except Exception as exc:
            raise _map_provider_error(exc) from exc


def _to_contents(messages: Sequence[Message]) -> list[Any]:
    from google.genai import types

    contents: list[Any] = []
    for msg in messages:
        if msg.role == Role.SYSTEM:
            # Fold system into a user preamble for models without system role.
            contents.append(
                types.Content(role="user", parts=[types.Part.from_text(text=msg.content)])
            )
            continue
        role = "model" if msg.role == Role.ASSISTANT else "user"
        if msg.role == Role.TOOL:
            role = "user"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg.content)]))
    return contents


def _to_openai_messages(messages: Sequence[Message]) -> list[dict[str, str]]:
    return [{"role": m.role.value, "content": m.content} for m in messages]


def _tool_to_genai(tool: ToolSpec) -> Any:
    from google.genai import types

    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters,
            )
        ]
    )


def _response_text(raw: Any) -> str:
    text = getattr(raw, "text", None)
    if isinstance(text, str):
        return text
    return ""


def _finish_reason(raw: Any) -> str | None:
    try:
        candidates = getattr(raw, "candidates", None) or []
        if not candidates:
            return None
        reason = getattr(candidates[0], "finish_reason", None)
        return str(reason) if reason is not None else None
    except (AttributeError, IndexError, TypeError):
        return None


def _usage_from(raw: Any) -> Usage:
    meta = getattr(raw, "usage_metadata", None)
    if meta is None:
        return Usage(tokens_in=0, tokens_out=0)
    return Usage(
        tokens_in=int(getattr(meta, "prompt_token_count", 0) or 0),
        tokens_out=int(getattr(meta, "candidates_token_count", 0) or 0),
    )


def _parse_tool_calls(raw: Any) -> list[ToolCall]:
    result: list[ToolCall] = []
    try:
        candidates = getattr(raw, "candidates", None) or []
        if not candidates:
            return []
        parts = getattr(candidates[0].content, "parts", None) or []
    except (AttributeError, IndexError, TypeError):
        return []
    for index, part in enumerate(parts):
        fn = getattr(part, "function_call", None)
        if fn is None:
            continue
        args = getattr(fn, "args", None) or {}
        if not isinstance(args, dict):
            try:
                args = dict(args)
            except (TypeError, ValueError):
                args = {}
        result.append(
            ToolCall(
                id=f"call_{index}",
                name=str(getattr(fn, "name", "")),
                arguments=cast(dict[str, Any], args),
            )
        )
    return result


def _map_provider_error(exc: Exception) -> LlmProviderError:
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if "timeout" in name or "timeout" in text:
        return LlmTimeoutError(str(exc))
    if "rate" in name or "429" in text or "quota" in text:
        return LlmRateLimitError(str(exc))
    return LlmProviderError(str(exc))
