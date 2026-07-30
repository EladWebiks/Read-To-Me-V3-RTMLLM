"""LlmService — domain facade; callers request capabilities."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import aclosing
from dataclasses import asdict
from datetime import datetime
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.llm import catalog
from app.modules.llm.capabilities import ModelCapability
from app.modules.llm.exceptions import (
    LlmConfigError,
    LlmDisabledError,
    LlmProviderError,
    NoCandidateModelError,
)
from app.modules.llm.model_router import ModelRouter
from app.modules.llm.providers.gemini_provider import GeminiProvider
from app.modules.llm.registry import ModelSpec
from app.modules.llm.repository import LlmRepository
from app.modules.llm.schemas import (
    AdminUsageOverview,
    LlmExecutionRead,
    ModelListResponse,
    ModelRead,
    ModelUsageRead,
    TaskUsageRead,
    UserUsageRead,
    UserUsageSummary,
)
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
    ToolCallingStreamChunk,
    Usage,
)

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R")


class LlmService:
    """Entry point for capability-based LLM calls."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._router = ModelRouter(settings)
        self._telemetry = LlmTelemetry(
            session,
            build_tracer(langfuse_enabled=settings.llm.langfuse_enabled),
        )
        self._repo = LlmRepository(session)

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
        if not self._settings.llm.enabled:
            raise LlmDisabledError("LLM_ENABLED is false")
        if self._settings.llm.provider == "gemini" and not self._settings.llm.gemini_api_key:
            raise LlmConfigError("GEMINI_API_KEY is required when LLM is enabled")

    async def ensure_ready(self) -> None:
        """Raise if LLM is off, misconfigured, or no catalog model is enabled."""
        self.ensure_enabled()
        await catalog.ensure_loaded(self._session)
        if not catalog.list_models(enabled_only=True):
            raise NoCandidateModelError("no enabled models in catalog")

    async def list_public_models(self) -> ModelListResponse:
        """Catalog for GET /api/llm/models (no secrets)."""
        await catalog.ensure_loaded(self._session)
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
            for m in catalog.list_models(enabled_only=False)
        ]
        return ModelListResponse(
            llm_enabled=self._settings.llm.enabled,
            default_provider=self._settings.llm.provider,
            default_model=self._settings.llm.model,
            models=models,
        )

    async def generate_text(
        self,
        req: GenerateTextRequest,
        *,
        user_id: UUID,
        capability: ModelCapability = ModelCapability.FAST_CHAT,
        conversation_id: UUID | None = None,
    ) -> GenerateTextResponse:
        """Generate text via routed provider."""
        await self.ensure_ready()

        async def _call(
            provider: GeminiProvider,
            _model: ModelSpec,
        ) -> GenerateTextResponse:
            return await provider.generate_text(req)

        result, model, fallback = await self._router.run(capability, _call)
        ctx = TelemetryContext(
            task=req.task,
            model=model,
            fallback_used=fallback,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        return await self._record(ctx, result, result.usage)

    async def call_tools(
        self,
        req: ToolCallingRequest,
        *,
        user_id: UUID,
        capability: ModelCapability = ModelCapability.TOOL_CALLING,
        conversation_id: UUID | None = None,
    ) -> ToolCallingResponse:
        """Tool-calling completion via routed provider."""
        await self.ensure_ready()

        async def _call(
            provider: GeminiProvider,
            _model: ModelSpec,
        ) -> ToolCallingResponse:
            return await provider.call_tools(req)

        result, model, fallback = await self._router.run(capability, _call)
        ctx = TelemetryContext(
            task=req.task,
            model=model,
            fallback_used=fallback,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        return await self._record(ctx, result, result.usage)

    async def stream_tools(
        self,
        req: ToolCallingRequest,
        *,
        user_id: UUID,
        capability: ModelCapability = ModelCapability.TOOL_CALLING,
        conversation_id: UUID | None = None,
    ) -> AsyncGenerator[ToolCallingStreamChunk, None]:
        """Stream a tool-capable round from one provider; no mid-stream fallback."""
        await self.ensure_ready()
        matches = self._router.candidates(capability)
        if not matches:
            raise NoCandidateModelError(capability.value)
        model = matches[0]
        provider = self._router.build(model)
        context = TelemetryContext(
            task=req.task,
            model=model,
            fallback_used=False,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        async with aclosing(self._stream_tools_from(provider, req, context)) as stream:
            async for chunk in stream:
                yield chunk

    async def _stream_tools_from(
        self,
        provider: GeminiProvider,
        req: ToolCallingRequest,
        context: TelemetryContext,
    ) -> AsyncGenerator[ToolCallingStreamChunk, None]:
        started = time.perf_counter()
        terminal: ToolCallingResponse | None = None
        status, error = "cancelled", None
        try:
            async with aclosing(provider.stream_tools(req)) as stream:
                async for chunk in stream:
                    if chunk.done:
                        terminal = chunk.response
                    yield chunk
            terminal = _require_terminal(terminal)
            status = "ok"
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            status, error = "error", str(exc)
            raise
        finally:
            usage = terminal.usage if terminal is not None else Usage(0, 0)
            await self._record_stream(context, started, usage, status, error)

    async def generate_structured(
        self,
        req: StructuredOutputRequest[T],
        *,
        user_id: UUID,
        capability: ModelCapability = ModelCapability.STRUCTURED_EXTRACTION,
        conversation_id: UUID | None = None,
    ) -> T:
        """Structured output via routed provider."""
        result, _provider, _model = await self.generate_structured_with_model(
            req,
            user_id=user_id,
            capability=capability,
            conversation_id=conversation_id,
        )
        return result

    async def generate_structured_with_model(
        self,
        req: StructuredOutputRequest[T],
        *,
        user_id: UUID,
        capability: ModelCapability = ModelCapability.STRUCTURED_EXTRACTION,
        conversation_id: UUID | None = None,
    ) -> tuple[T, str, str]:
        """Structured output plus provider/model provenance."""
        await self.ensure_ready()

        async def _call(provider: GeminiProvider, _model: ModelSpec) -> T:
            return await provider.generate_structured_output(req)

        result, model, fallback = await self._router.run(capability, _call)
        ctx = TelemetryContext(
            task=req.task,
            model=model,
            fallback_used=fallback,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        recorded = await self._record(ctx, result, Usage(0, 0))
        return recorded, model.provider, model.model_name

    async def stream_text(
        self,
        req: GenerateTextRequest,
        *,
        capability: ModelCapability = ModelCapability.FAST_CHAT,
    ) -> AsyncIterator[StreamChunk]:
        """Stream from the first candidate (no mid-stream fallback)."""
        await self.ensure_ready()
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
        user_id: UUID,
        capability: ModelCapability = ModelCapability.EMBEDDING,
    ) -> EmbeddingResponse:
        """Embeddings via routed provider (may be unsupported in B1)."""
        await self.ensure_ready()

        async def _call(
            provider: GeminiProvider,
            _model: ModelSpec,
        ) -> EmbeddingResponse:
            return await provider.create_embeddings(req)

        result, model, fallback = await self._router.run(capability, _call)
        ctx = TelemetryContext(
            task=req.task,
            model=model,
            fallback_used=fallback,
            user_id=user_id,
            conversation_id=None,
        )
        return await self._record(ctx, result, result.usage)

    async def usage_summary(
        self,
        user_id: UUID,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> UserUsageSummary:
        """Per-user usage aggregate over [period_start, period_end); no HTTP route yet."""
        totals = await self._repo.usage_summary_for_user(
            user_id,
            period_start=period_start,
            period_end=period_end,
        )
        return UserUsageSummary(
            user_id=user_id,
            period_start=period_start,
            period_end=period_end,
            tokens_in=totals.tokens_in,
            tokens_out=totals.tokens_out,
            total_cost=totals.total_cost,
            execution_count=totals.execution_count,
        )

    async def usage_overview_admin(
        self, *, period_start: datetime, period_end: datetime
    ) -> AdminUsageOverview:
        """Backoffice cross-user usage totals with model/task breakdowns."""
        totals = await self._repo.usage_totals_admin(
            period_start=period_start, period_end=period_end
        )
        by_model = await self._repo.usage_by_model_admin(
            period_start=period_start, period_end=period_end
        )
        by_task = await self._repo.usage_by_task_admin(
            period_start=period_start, period_end=period_end
        )
        return AdminUsageOverview(
            period_start=period_start,
            period_end=period_end,
            tokens_in=totals.tokens_in,
            tokens_out=totals.tokens_out,
            total_cost=totals.total_cost,
            execution_count=totals.execution_count,
            by_model=[ModelUsageRead(**asdict(row)) for row in by_model],
            by_task=[TaskUsageRead(**asdict(row)) for row in by_task],
        )

    async def usage_by_user_admin(
        self, *, period_start: datetime, period_end: datetime, limit: int, offset: int
    ) -> tuple[list[UserUsageRead], int]:
        """Backoffice per-user usage rows (usernames resolved by the caller)."""
        rows, total = await self._repo.usage_by_user_admin(
            period_start=period_start, period_end=period_end, limit=limit, offset=offset
        )
        return [UserUsageRead(**asdict(row)) for row in rows], total

    async def list_executions_admin(
        self, *, period_start: datetime, period_end: datetime, limit: int, offset: int
    ) -> tuple[list[LlmExecutionRead], int]:
        """Backoffice recent-executions page, newest first."""
        rows, total = await self._repo.list_executions_admin(
            period_start=period_start, period_end=period_end, limit=limit, offset=offset
        )
        return [LlmExecutionRead.model_validate(row) for row in rows], total

    async def _record(self, ctx: TelemetryContext, result: R, usage: Usage) -> R:
        async def _once() -> tuple[R, Usage]:
            return result, usage

        return await self._telemetry.record_call(ctx, _once)

    async def _record_stream(
        self,
        context: TelemetryContext,
        started: float,
        usage: Usage,
        status: str,
        error: str | None,
    ) -> None:
        await self._telemetry.write_result(
            context,
            usage=usage,
            latency_ms=int((time.perf_counter() - started) * 1000),
            status=status,
            error=error,
        )


def _require_terminal(response: ToolCallingResponse | None) -> ToolCallingResponse:
    if response is None:
        raise LlmProviderError("Provider tool stream ended without a terminal response")
    return response
