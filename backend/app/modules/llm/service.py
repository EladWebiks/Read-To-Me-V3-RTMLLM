"""LlmService — domain facade; callers request capabilities."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.llm.capabilities import ModelCapability
from app.modules.llm.exceptions import LlmConfigError, LlmDisabledError, NoCandidateModelError
from app.modules.llm.model_router import ModelRouter
from app.modules.llm.providers.gemini_provider import GeminiProvider
from app.modules.llm.registry import ModelSpec, list_models
from app.modules.llm.schemas import ModelListResponse, ModelRead
from app.modules.llm.telemetry import LlmTelemetry, TelemetryContext, build_tracer
from app.modules.llm.types import (
    EmbeddingRequest,
    EmbeddingResponse,
    GenerateTextRequest,
    GenerateTextResponse,
    StreamChunk,
    StructuredOutputRequest,
    ToolCallingRequest,
    ToolCallingResponse,
    Usage,
)

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R")


class LlmService:
    """Entry point for capability-based LLM calls."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._settings = settings
        self._router = ModelRouter(settings)
        self._telemetry = LlmTelemetry(
            session,
            build_tracer(langfuse_enabled=settings.langfuse_enabled),
        )

    @property
    def router(self) -> ModelRouter:
        """Capability router (used by chat streaming)."""
        return self._router

    @property
    def telemetry(self) -> LlmTelemetry:
        """Telemetry sink (used by chat streaming)."""
        return self._telemetry

    def ensure_enabled(self) -> None:
        """Raise if LLM is off or misconfigured."""
        if not self._settings.llm_enabled:
            raise LlmDisabledError("LLM_ENABLED is false")
        if self._settings.llm_provider == "gemini" and not self._settings.gemini_api_key:
            raise LlmConfigError("GEMINI_API_KEY is required when LLM is enabled")

    def list_public_models(self) -> ModelListResponse:
        """Catalog for GET /api/llm/models (no secrets)."""
        models = [
            ModelRead(
                provider=m.provider,
                model_name=m.model_name,
                capabilities=sorted(c.value for c in m.capabilities),
                context_window=m.context_window,
                supports_tools=m.supports_tools,
                supports_structured=m.supports_structured,
                supports_streaming=m.supports_streaming,
                enabled=m.enabled,
            )
            for m in list_models(enabled_only=False)
        ]
        return ModelListResponse(
            llm_enabled=self._settings.llm_enabled,
            default_provider=self._settings.llm_provider,
            default_model=self._settings.llm_model,
            models=models,
        )

    async def generate_text(
        self,
        req: GenerateTextRequest,
        *,
        capability: ModelCapability = ModelCapability.FAST_CHAT,
        conversation_id: UUID | None = None,
    ) -> GenerateTextResponse:
        """Generate text via routed provider."""
        self.ensure_enabled()

        async def _call(
            provider: GeminiProvider,
            _model: ModelSpec,
        ) -> GenerateTextResponse:
            return await provider.generate_text(req)

        result, model, fallback = await self._router.run(capability, _call)
        return await self._record(req.task, model, fallback, conversation_id, result, result.usage)

    async def call_tools(
        self,
        req: ToolCallingRequest,
        *,
        capability: ModelCapability = ModelCapability.TOOL_CALLING,
        conversation_id: UUID | None = None,
    ) -> ToolCallingResponse:
        """Tool-calling completion via routed provider."""
        self.ensure_enabled()

        async def _call(
            provider: GeminiProvider,
            _model: ModelSpec,
        ) -> ToolCallingResponse:
            return await provider.call_tools(req)

        result, model, fallback = await self._router.run(capability, _call)
        return await self._record(req.task, model, fallback, conversation_id, result, result.usage)

    async def generate_structured(
        self,
        req: StructuredOutputRequest[T],
        *,
        capability: ModelCapability = ModelCapability.STRUCTURED_EXTRACTION,
        conversation_id: UUID | None = None,
    ) -> T:
        """Structured output via routed provider."""
        self.ensure_enabled()

        async def _call(provider: GeminiProvider, _model: ModelSpec) -> T:
            return await provider.generate_structured_output(req)

        result, model, fallback = await self._router.run(capability, _call)
        return await self._record(req.task, model, fallback, conversation_id, result, Usage(0, 0))

    async def stream_text(
        self,
        req: GenerateTextRequest,
        *,
        capability: ModelCapability = ModelCapability.FAST_CHAT,
    ) -> AsyncIterator[StreamChunk]:
        """Stream from the first candidate (no mid-stream fallback)."""
        self.ensure_enabled()
        matches = self._router.candidates(capability)
        if not matches:
            raise NoCandidateModelError(capability.value)
        provider = self._router.build(matches[0])
        async for chunk in provider.stream_text(req):
            yield chunk

    async def create_embeddings(
        self,
        req: EmbeddingRequest,
        *,
        capability: ModelCapability = ModelCapability.EMBEDDING,
    ) -> EmbeddingResponse:
        """Embeddings via routed provider (may be unsupported in B1)."""
        self.ensure_enabled()

        async def _call(
            provider: GeminiProvider,
            _model: ModelSpec,
        ) -> EmbeddingResponse:
            return await provider.create_embeddings(req)

        result, model, fallback = await self._router.run(capability, _call)
        return await self._record(req.task, model, fallback, None, result, result.usage)

    async def _record(
        self,
        task: str,
        model: ModelSpec,
        fallback: bool,
        conversation_id: UUID | None,
        result: R,
        usage: Usage,
    ) -> R:
        async def _once() -> tuple[R, Usage]:
            return result, usage

        return await self._telemetry.record_call(
            TelemetryContext(
                task=task,
                model=model,
                fallback_used=fallback,
                conversation_id=conversation_id,
            ),
            _once,
        )
