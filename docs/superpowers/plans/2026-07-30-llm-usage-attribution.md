# LLM Usage Attribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Attribute every LLM provider call to a user by adding a NOT NULL `user_id` FK to `llm_executions`, threading `user_id` as a required parameter through the telemetry write API, and adding a per-user usage-summary query that the composite index serves.

**Architecture:** All `llm_executions` inserts funnel through one method (`LlmRepository.record_execution` ← `LlmTelemetry` ← `LlmService`), so Task 1 lands the wipe-and-add migration, the model change, and the required-`user_id` threading through that funnel plus its three live call sites (orchestration streaming loop, conversation-context summarizer, book-summary generation) as one atomic, gate-green commit. Task 2 adds the read path: an aggregate repository query over `(user_id, created_at)` exposed via `LlmService.usage_summary`.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Postgres, pytest (unit/integration markers), strict mypy, ruff.

**Spec:** `docs/superpowers/specs/2026-07-30-llm-usage-attribution-design.md` (approved).

## Global Constraints

- All backend gates must pass per task (run from `backend/`): `uv run ruff check . --fix && uv run ruff format .`, `uv run mypy .`, `uv run pytest -m "unit or integration"`.
- Integration tests need Postgres/Redis/MinIO and `TEST_DATABASE_URL` pointing at a separate test DB (e.g. `rtm_test`) — **never** the app DB.
- Apply the new migration to BOTH the app DB and the test DB before running integration tests.
- Commit with `bash scripts/git-commit-clean.sh /tmp/msg.txt` (write the message to `/tmp/msg.txt` first). **Never** add `Co-authored-by`/`Made-with` trailers. Verify with `git log -1 --format=%B`.
- Ruff limits: complexity ≤10, statements ≤20, branches ≤6, args ≤6 (this is why `LlmService._record` is refactored to take a `TelemetryContext` instead of gaining a 7th loose argument).
- Full type hints; strict mypy. Module boundaries: only the llm module's repository touches `llm_executions`; other modules call the llm module's service.
- Alembic: `uv run alembic heads` must show exactly ONE head after generating the revision (chains off `db448309b4a6`, the feature/sso `google_sub` migration). If another migration landed first, regenerate so the chain stays linear.

---

### Task 1: Migration + model + required `user_id` through the write path

This task is atomic on purpose: the NOT NULL column and the required
parameter must land together — the migration alone would turn
`tests/llm/test_llm_telemetry.py` red (INSERT without `user_id` violates
NOT NULL), and the parameter alone has no column to write to.

**Files:**
- Modify: `backend/tests/llm/test_llm_telemetry.py` (updated deliberately — the only structurally broken test)
- Modify: `backend/app/modules/llm/models.py` (LlmExecution)
- Create: `backend/migrations/versions/<generated>_wipe_llm_telemetry_add_user_id.py`
- Modify: `backend/app/modules/llm/repository.py` (`ExecutionWrite`, `record_execution`)
- Modify: `backend/app/modules/llm/telemetry.py` (`TelemetryContext`, `_write`)
- Modify: `backend/app/modules/llm/service.py` (all recording entry points + `_record`)
- Modify: `backend/app/modules/orchestration/service.py` (`_StreamedRound.events` + its call site)
- Modify: `backend/app/modules/llm/conversation_context.py` (`_summarize`)
- Modify: `backend/app/modules/summaries/service.py` (`ensure`)

**Interfaces:**
- Consumes: existing `users.id` (UUID PK), `LlmExecution`, `ToolContext.user_id`.
- Produces (Task 2 and all future callers rely on these exact shapes):
  - `LlmExecution.user_id: Mapped[uuid.UUID]` (NOT NULL, FK `users.id`, composite index `ix_llm_executions_user_id_created_at`)
  - `ExecutionWrite(..., user_id: uuid.UUID, conversation_id: uuid.UUID | None = None)` — `user_id` required
  - `TelemetryContext(task, model, fallback_used, user_id, conversation_id=None)` — `user_id: uuid.UUID` required
  - `LlmService.generate_text / call_tools / stream_tools / generate_structured / generate_structured_with_model / create_embeddings` each take keyword-only required `user_id: UUID`

- [ ] **Step 1: Write the failing test**

Replace `backend/tests/llm/test_llm_telemetry.py` with:

```python
"""Telemetry persistence tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
from app.core.config import get_settings
from app.modules.llm.models import CostRecord, LlmExecution
from app.modules.llm.registry import get_model
from app.modules.llm.telemetry import LlmTelemetry, NoOpTracer, TelemetryContext
from app.modules.llm.types import Usage
from app.modules.users.models import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def llm_session() -> AsyncGenerator[AsyncSession, None]:
    """Fresh session against the test DB tables."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _user(session: AsyncSession) -> User:
    """Unique throwaway user so the NOT NULL FK has a real target."""
    user = User(
        username=f"telemetry-{uuid.uuid4().hex[:10]}",
        password_hash=None,
        role="user",
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.integration
@pytest.mark.asyncio
async def test_telemetry_writes_execution_and_cost(llm_session: AsyncSession) -> None:
    model = get_model("gemini", "gemini-3.5-flash-lite")
    assert model is not None
    user = await _user(llm_session)
    telemetry = LlmTelemetry(llm_session, NoOpTracer())

    async def _call() -> tuple[str, Usage]:
        return "ok", Usage(tokens_in=10, tokens_out=5)

    result = await telemetry.record_call(
        TelemetryContext(
            task="chat",
            model=model,
            fallback_used=False,
            user_id=user.id,
        ),
        _call,
    )
    assert result == "ok"

    executions = (
        (await llm_session.execute(select(LlmExecution).order_by(LlmExecution.created_at.desc())))
        .scalars()
        .all()
    )
    assert executions
    assert executions[0].task == "chat"
    assert executions[0].tokens_in == 10
    assert executions[0].status == "ok"
    assert executions[0].user_id == user.id

    costs = (
        (await llm_session.execute(select(CostRecord).order_by(CostRecord.created_at.desc())))
        .scalars()
        .all()
    )
    assert costs
    assert costs[0].llm_execution_id == executions[0].id
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `uv run pytest tests/llm/test_llm_telemetry.py -v`
Expected: FAIL with `TypeError: TelemetryContext.__init__() got an unexpected keyword argument 'user_id'`.

- [ ] **Step 3: Update the model**

In `backend/app/modules/llm/models.py`:

Add `Index` to the sqlalchemy import block:

```python
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
```

In `LlmExecution`, add `user_id` right after the `conversation_id` column, and the composite index via `__table_args__` right after `__tablename__`:

```python
class LlmExecution(Base):
    """One provider call (tokens, cost, latency)."""

    __tablename__ = "llm_executions"
    # Composite (user_id, created_at): billing-month aggregation does one
    # index range scan; leftmost prefix also covers user_id-only lookups.
    __table_args__ = (Index("ix_llm_executions_user_id_created_at", "user_id", "created_at"),)
```

```python
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
```

(No `index=True` on the column — the composite index covers it. Plain FK, no cascade: usage rows must survive user soft-deletion for billing/audit.)

- [ ] **Step 4: Generate the migration skeleton**

Run (from `backend/`): `uv run alembic revision -m "wipe llm telemetry and add user_id attribution"`
Then run `uv run alembic heads` — expected: exactly one head, and the generated file's `down_revision` is `"db448309b4a6"`. If it is not (another migration landed first), keep the generated `down_revision` and verify heads is still exactly one.

- [ ] **Step 5: Fill in upgrade/downgrade**

Replace the generated module docstring and `upgrade`/`downgrade` bodies (keep the generated `revision`/`down_revision` identifiers). Add `from sqlalchemy.dialects import postgresql` to the imports:

```python
"""wipe llm telemetry and add user_id attribution

DATA LOSS: intentionally deletes ALL rows from cost_records and
llm_executions (dev-only telemetry; approved fresh start so user_id can be
NOT NULL with no backfill). Downgrade removes the column/index/FK but the
wiped rows are unrecoverable in both directions.
"""
```

```python
def upgrade() -> None:
    # FK order: cost_records.llm_execution_id references llm_executions.id,
    # so the child table is wiped first. cost_records is the only table
    # referencing llm_executions.
    op.execute(sa.text("DELETE FROM cost_records"))
    op.execute(sa.text("DELETE FROM llm_executions"))
    # Table is empty here, so NOT NULL needs no server_default.
    op.add_column(
        "llm_executions",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        "fk_llm_executions_user_id_users",
        "llm_executions",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_index(
        "ix_llm_executions_user_id_created_at",
        "llm_executions",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_llm_executions_user_id_created_at", table_name="llm_executions")
    op.drop_constraint(
        "fk_llm_executions_user_id_users",
        "llm_executions",
        type_="foreignkey",
    )
    op.drop_column("llm_executions", "user_id")
```

- [ ] **Step 6: Verify the migration is reversible, apply to app + test DB**

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
uv run alembic heads
```

Expected: all three migration commands succeed; `heads` prints exactly one revision. Then apply to the test DB so integration tests see the new column — run `uv run alembic upgrade head` once more with `DATABASE_URL` set to your `TEST_DATABASE_URL` value.

- [ ] **Step 7: Thread `user_id` through repository + telemetry**

In `backend/app/modules/llm/repository.py`, `ExecutionWrite` — add the required field just above the defaulted `conversation_id`:

```python
    unit_cost_in: float
    unit_cost_out: float
    user_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
```

In `record_execution`, add `user_id` to the `LlmExecution(...)` constructor:

```python
        execution = LlmExecution(
            conversation_id=data.conversation_id,
            user_id=data.user_id,
            task=data.task,
```

In `backend/app/modules/llm/telemetry.py`, `TelemetryContext` — add the required field above the defaulted `conversation_id`:

```python
@dataclass(frozen=True, slots=True)
class TelemetryContext:
    """Inputs for recording a routed call."""

    task: str
    model: ModelSpec
    fallback_used: bool
    user_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
```

In `LlmTelemetry._write`, pass it into `ExecutionWrite`:

```python
                unit_cost_in=ctx.model.input_cost_per_1m,
                unit_cost_out=ctx.model.output_cost_per_1m,
                user_id=ctx.user_id,
                conversation_id=ctx.conversation_id,
```

- [ ] **Step 8: Thread `user_id` through LlmService**

In `backend/app/modules/llm/service.py`:

Refactor `_record` to take a prebuilt context (avoids breaching ruff `max-args 6`):

```python
    async def _record(self, ctx: TelemetryContext, result: R, usage: Usage) -> R:
        async def _once() -> tuple[R, Usage]:
            return result, usage

        return await self._telemetry.record_call(ctx, _once)
```

`generate_text` — new signature and recording call:

```python
    async def generate_text(
        self,
        req: GenerateTextRequest,
        *,
        user_id: UUID,
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
        ctx = TelemetryContext(
            task=req.task,
            model=model,
            fallback_used=fallback,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        return await self._record(ctx, result, result.usage)
```

`call_tools` — same pattern:

```python
    async def call_tools(
        self,
        req: ToolCallingRequest,
        *,
        user_id: UUID,
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
        ctx = TelemetryContext(
            task=req.task,
            model=model,
            fallback_used=fallback,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        return await self._record(ctx, result, result.usage)
```

`stream_tools` — add the parameter and pass it into the context (body of `_stream_tools_from` is unchanged):

```python
    async def stream_tools(
        self,
        req: ToolCallingRequest,
        *,
        user_id: UUID,
        capability: ModelCapability = ModelCapability.TOOL_CALLING,
        conversation_id: UUID | None = None,
    ) -> AsyncGenerator[ToolCallingStreamChunk, None]:
        """Stream a tool-capable round from one provider; no mid-stream fallback."""
        self.ensure_enabled()
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
```

`generate_structured` and `generate_structured_with_model` — add and forward the parameter:

```python
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
        self.ensure_enabled()

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
```

`create_embeddings` — no conversation in scope, but attribution is still required:

```python
    async def create_embeddings(
        self,
        req: EmbeddingRequest,
        *,
        user_id: UUID,
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
        ctx = TelemetryContext(
            task=req.task,
            model=model,
            fallback_used=fallback,
            user_id=user_id,
            conversation_id=None,
        )
        return await self._record(ctx, result, result.usage)
```

`stream_text` is deliberately unchanged — it records no telemetry today (pre-existing gap, documented in the spec; do not silently "fix" it here).

- [ ] **Step 9: Update the three live call sites**

**Call site 1 — orchestration loop** (`backend/app/modules/orchestration/service.py`). Change `_StreamedRound.events` to take the `ToolContext` (already imported in this file) instead of a bare conversation id:

```python
    async def events(
        self,
        llm: LlmService,
        request: ToolCallingRequest,
        ctx: ToolContext,
    ) -> AsyncIterator[ChatSseEvent]:
        stream = llm.stream_tools(
            request,
            user_id=ctx.user_id,
            conversation_id=ctx.conversation_id,
        )
        async with aclosing(stream) as chunks:
            async for chunk in chunks:
                if chunk.text:
                    if self.prefix and not self.started:
                        yield ChatSseEvent("delta", {"text": "\n\n"})
                    self.started = True
                    yield ChatSseEvent("delta", {"text": chunk.text})
                if chunk.done:
                    self.response = chunk.response
```

And its single call site in `_loop`:

```python
            async for event in streamed.events(
                self._llm,
                self._tool_request(state.messages, state.ctx),
                state.ctx,
            ):
                yield event
```

**Call site 2 — conversation summarizer** (`backend/app/modules/llm/conversation_context.py`). `_summarize` gains `user_id`; `build` supplies it. In `build`, change the call:

```python
            summary = await self._summarize(
                stored.summary if stored else None,
                older,
                user_id,
                conversation_id,
            )
```

And the method:

```python
    async def _summarize(
        self,
        existing: str | None,
        rows: list[ConversationMessage],
        user_id: UUID,
        conversation_id: UUID,
    ) -> str:
        summary = existing
        for chunk in _message_chunks(rows):
            request = StructuredOutputRequest(
                messages=[
                    Message(role=Role.SYSTEM, content=_SUMMARY_SYSTEM_PROMPT),
                    Message(role=Role.USER, content=_summary_source(summary, chunk)),
                ],
                response_model=_SummaryResult,
                max_output_tokens=self._settings.llm_summary_max_output_tokens,
                temperature=0.1,
                task="conversation_summary",
            )
            result = await self._llm.generate_structured(
                request,
                user_id=user_id,
                conversation_id=conversation_id,
            )
            summary = result.summary.strip()
        if not summary:
            raise LlmError("conversation summarizer returned empty output")
        return summary
```

**Call site 3 — book summaries** (`backend/app/modules/summaries/service.py`), in `ensure` (its `user_id` parameter already exists; the `summarize_book` tool passes `ctx.user_id` into it — no tool change needed):

```python
        draft, provider, model = await self._llm.generate_structured_with_model(
            _request(book, kind, source),
            user_id=user_id,
            capability=ModelCapability.LONG_CONTEXT_SUMMARIZATION,
            conversation_id=conversation_id,
        )
```

- [ ] **Step 10: mypy sweep — prove the call-site list is exhaustive**

Run: `uv run mypy .`
Expected: PASS. If mypy reports any OTHER caller of the changed signatures (beyond the three updated in Step 9), STOP: it is a write path the audit missed — add it to the spec's audit table and to this task, sourcing `user_id` from the authenticated context; if that path genuinely has no authenticated user, flag it in the spec as an open question instead of inventing a sentinel user.

- [ ] **Step 11: Run tests to verify they pass**

Run: `uv run pytest tests/llm/test_llm_telemetry.py -v`
Expected: PASS (asserts `user_id` round-trips).

The pre-existing monkeypatch fakes are unaffected by design: `tests/llm/stream_fakes.py` and the fakes in `test_chat.py`/`test_orchestration.py`/`test_hitl.py` accept `**kwargs`, and `test_conversation_context.py`/`test_book_summaries.py` use `AsyncMock`. Confirm with the full suite in the next step — if any of them fails on the new kwarg, fix the fake's signature to accept `**kwargs` rather than weakening the service signature.

- [ ] **Step 12: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat!: attribute llm_executions to users with NOT NULL user_id\n\nWipes dev-only telemetry (cost_records then llm_executions) and requires\nuser_id through the telemetry write API and all LlmService entry points.\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 2: Per-user usage summary (read path)

**Files:**
- Create: `backend/tests/llm/test_llm_usage_summary.py`
- Modify: `backend/app/modules/llm/repository.py` (add `UsageTotals` + `usage_summary_for_user`)
- Modify: `backend/app/modules/llm/schemas.py` (add `UserUsageSummary`)
- Modify: `backend/app/modules/llm/service.py` (add `usage_summary`, hold an `LlmRepository`)

**Interfaces:**
- Consumes: `LlmExecution.user_id` + `ix_llm_executions_user_id_created_at` (Task 1), `ExecutionWrite` with required `user_id` (Task 1).
- Produces (the future backoffice/quota plan consumes these — no HTTP route yet):
  - `UsageTotals` frozen dataclass: `tokens_in: int, tokens_out: int, total_cost: float, execution_count: int`
  - `async LlmRepository.usage_summary_for_user(user_id: uuid.UUID, *, period_start: datetime, period_end: datetime) -> UsageTotals` — half-open interval `[period_start, period_end)`
  - `class UserUsageSummary(BaseModel)`: `user_id: UUID, period_start: datetime, period_end: datetime, tokens_in: int, tokens_out: int, total_cost: float, execution_count: int`
  - `async LlmService.usage_summary(user_id: UUID, *, period_start: datetime, period_end: datetime) -> UserUsageSummary`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/llm/test_llm_usage_summary.py
"""Per-user usage aggregation tests (needs Postgres test DB)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import get_settings
from app.modules.llm.models import LlmExecution
from app.modules.llm.repository import ExecutionWrite, LlmRepository
from app.modules.llm.service import LlmService
from app.modules.users.models import User
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def llm_session() -> AsyncGenerator[AsyncSession, None]:
    """Fresh session against the test DB tables."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _user(session: AsyncSession) -> User:
    user = User(
        username=f"usage-{uuid.uuid4().hex[:10]}",
        password_hash=None,
        role="user",
    )
    session.add(user)
    await session.flush()
    return user


def _write(user_id: uuid.UUID, tokens_in: int, tokens_out: int, cost: float) -> ExecutionWrite:
    return ExecutionWrite(
        task="chat",
        provider="gemini",
        model="gemini-3.5-flash-lite",
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost=cost,
        latency_ms=100,
        status="ok",
        fallback_used=False,
        trace_id=None,
        error=None,
        unit_cost_in=0.0,
        unit_cost_out=0.0,
        user_id=user_id,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_usage_summary_sums_owner_rows_in_range(llm_session: AsyncSession) -> None:
    repo = LlmRepository(llm_session)
    owner = await _user(llm_session)
    other = await _user(llm_session)
    await repo.record_execution(_write(owner.id, 100, 40, 0.002))
    await repo.record_execution(_write(owner.id, 50, 10, 0.001))
    await repo.record_execution(_write(other.id, 999, 999, 9.9))
    # Owner row far outside the queried period (billing months are half-open).
    llm_session.add(
        LlmExecution(
            user_id=owner.id,
            task="chat",
            provider="gemini",
            model="gemini-3.5-flash-lite",
            tokens_in=777,
            tokens_out=777,
            cost=7.7,
            latency_ms=1,
            status="ok",
            fallback_used=False,
            created_at=datetime.now(UTC) - timedelta(days=90),
        )
    )
    await llm_session.commit()

    now = datetime.now(UTC)
    summary = await LlmService(llm_session, get_settings()).usage_summary(
        owner.id,
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=1),
    )
    assert summary.user_id == owner.id
    assert summary.execution_count == 2
    assert summary.tokens_in == 150
    assert summary.tokens_out == 50
    assert summary.total_cost == pytest.approx(0.003)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_usage_summary_empty_range_returns_zeros(llm_session: AsyncSession) -> None:
    owner = await _user(llm_session)
    await llm_session.commit()
    now = datetime.now(UTC)
    summary = await LlmService(llm_session, get_settings()).usage_summary(
        owner.id,
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=1),
    )
    assert summary.execution_count == 0
    assert summary.tokens_in == 0
    assert summary.tokens_out == 0
    assert summary.total_cost == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/llm/test_llm_usage_summary.py -v`
Expected: FAIL with `AttributeError: 'LlmService' object has no attribute 'usage_summary'`.

- [ ] **Step 3: Add the repository aggregate**

In `backend/app/modules/llm/repository.py`:

Extend the sqlalchemy import: `from sqlalchemy import func, select`

Add the dataclass next to the other write/read dataclasses:

```python
@dataclass(frozen=True, slots=True)
class UsageTotals:
    """Aggregate of llm_executions for one user over a period."""

    tokens_in: int
    tokens_out: int
    total_cost: float
    execution_count: int
```

Add the method to `LlmRepository`:

```python
    async def usage_summary_for_user(
        self,
        user_id: uuid.UUID,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> UsageTotals:
        """Billing-month aggregate over [period_start, period_end).

        Served by ix_llm_executions_user_id_created_at as one index range scan.
        """
        result = await self._session.execute(
            select(
                func.coalesce(func.sum(LlmExecution.tokens_in), 0),
                func.coalesce(func.sum(LlmExecution.tokens_out), 0),
                func.coalesce(func.sum(LlmExecution.cost), 0.0),
                func.count(LlmExecution.id),
            ).where(
                LlmExecution.user_id == user_id,
                LlmExecution.created_at >= period_start,
                LlmExecution.created_at < period_end,
            )
        )
        tokens_in, tokens_out, total_cost, count = result.one()
        return UsageTotals(
            tokens_in=int(tokens_in),
            tokens_out=int(tokens_out),
            total_cost=float(total_cost),
            execution_count=int(count),
        )
```

(`datetime` is already imported in this file.)

- [ ] **Step 4: Add the schema DTO**

In `backend/app/modules/llm/schemas.py` (add `from datetime import datetime` and `from uuid import UUID` to the imports if not already present):

```python
class UserUsageSummary(BaseModel):
    """Aggregated per-user LLM usage for a period (tier quotas / billing)."""

    user_id: UUID
    period_start: datetime
    period_end: datetime
    tokens_in: int
    tokens_out: int
    total_cost: float
    execution_count: int
```

- [ ] **Step 5: Expose it on the service**

In `backend/app/modules/llm/service.py`:

Add imports: `from datetime import datetime`, extend the repository import to `from app.modules.llm.repository import LlmRepository`, and extend the schemas import to include `UserUsageSummary`.

In `__init__`, keep a repository handle (after the existing assignments):

```python
        self._repo = LlmRepository(session)
```

Add the method:

```python
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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/llm/test_llm_usage_summary.py -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add per-user LLM usage summary query\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```
