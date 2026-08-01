"""Record every LLM call; optional Langfuse (no-op by default)."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.llm.registry import ModelSpec
from app.modules.llm.repository import ExecutionWrite, LlmRepository
from app.modules.llm.types import Usage

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Tracer(Protocol):
    """Optional external trace sink."""

    def start(self, name: str, *, metadata: dict[str, str]) -> str:
        """Begin a span; return trace id."""

    def end(self, trace_id: str, *, status: str, error: str | None = None) -> None:
        """Finish a span."""


class NoOpTracer:
    """Default tracer — generates local ids only."""

    def start(self, name: str, *, metadata: dict[str, str]) -> str:
        return uuid.uuid4().hex

    def end(self, trace_id: str, *, status: str, error: str | None = None) -> None:
        return None


def build_tracer(*, langfuse_enabled: bool) -> Tracer:
    """Return Langfuse tracer when enabled and importable; else no-op."""
    if not langfuse_enabled:
        return NoOpTracer()
    try:
        return _LangfuseTracer()
    except Exception:
        logger.warning("Langfuse unavailable; using no-op tracer")
        return NoOpTracer()


class _LangfuseTracer:
    """Thin Langfuse wrapper (optional extra)."""

    def __init__(self) -> None:
        from langfuse import Langfuse  # type: ignore[import-not-found]

        self._client = Langfuse()
        self._spans: dict[str, object] = {}

    def start(self, name: str, *, metadata: dict[str, str]) -> str:
        trace_id = uuid.uuid4().hex
        span = self._client.trace(id=trace_id, name=name, metadata=metadata)
        self._spans[trace_id] = span
        return trace_id

    def end(self, trace_id: str, *, status: str, error: str | None = None) -> None:
        span = self._spans.pop(trace_id, None)
        if span is None:
            return
        # Best-effort; Langfuse client APIs vary by version.
        update = getattr(span, "update", None)
        if callable(update):
            update(metadata={"status": status, "error": error})


@dataclass(frozen=True, slots=True)
class TelemetryContext:
    """Inputs for recording a routed call."""

    task: str
    model: ModelSpec
    fallback_used: bool
    user_id: uuid.UUID
    conversation_id: uuid.UUID | None = None


class LlmTelemetry:
    """Times a call and persists llm_execution + cost_record."""

    def __init__(self, session: AsyncSession, tracer: Tracer) -> None:
        self._repo = LlmRepository(session)
        self._tracer = tracer

    async def record_call(
        self,
        ctx: TelemetryContext,
        call: Callable[[], Awaitable[tuple[T, Usage]]],
    ) -> T:
        """Run call, always write telemetry (ok or error)."""
        trace_id = self._tracer.start(
            ctx.task,
            metadata={"provider": ctx.model.provider, "model": ctx.model.model_name},
        )
        started = time.perf_counter()
        try:
            value, usage = await call()
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            await self._write(
                ctx,
                usage=Usage(0, 0),
                latency_ms=latency_ms,
                status="error",
                trace_id=trace_id,
                error=str(exc),
            )
            self._tracer.end(trace_id, status="error", error=str(exc))
            raise

        latency_ms = int((time.perf_counter() - started) * 1000)
        await self._write(
            ctx,
            usage=usage,
            latency_ms=latency_ms,
            status="ok",
            trace_id=trace_id,
            error=None,
        )
        self._tracer.end(trace_id, status="ok")
        return value

    async def write_result(
        self,
        ctx: TelemetryContext,
        *,
        usage: Usage,
        latency_ms: int,
        status: str,
        error: str | None,
    ) -> None:
        """Persist telemetry for an already-finished call (e.g. streaming)."""
        trace_id = self._tracer.start(
            ctx.task,
            metadata={"provider": ctx.model.provider, "model": ctx.model.model_name},
        )
        await self._write(
            ctx,
            usage=usage,
            latency_ms=latency_ms,
            status=status,
            trace_id=trace_id,
            error=error,
        )
        self._tracer.end(trace_id, status=status, error=error)

    async def _write(
        self,
        ctx: TelemetryContext,
        *,
        usage: Usage,
        latency_ms: int,
        status: str,
        trace_id: str,
        error: str | None,
    ) -> None:
        cost = estimate_cost(ctx.model, usage)
        await self._repo.record_execution(
            ExecutionWrite(
                task=ctx.task,
                provider=ctx.model.provider,
                model=ctx.model.model_name,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                cost=cost,
                latency_ms=latency_ms,
                status=status,
                fallback_used=ctx.fallback_used,
                trace_id=trace_id,
                error=error,
                unit_cost_in=ctx.model.input_cost_per_1m,
                unit_cost_out=ctx.model.output_cost_per_1m,
                user_id=ctx.user_id,
                conversation_id=ctx.conversation_id,
            )
        )


def estimate_cost(model: ModelSpec, usage: Usage) -> float:
    """USD estimate from catalog unit prices (0 on free-tier accounting is fine)."""
    if usage.cost_usd is not None:
        return usage.cost_usd
    inn = (usage.tokens_in / 1_000_000) * model.input_cost_per_1m
    out = (usage.tokens_out / 1_000_000) * model.output_cost_per_1m
    return round(inn + out, 8)
