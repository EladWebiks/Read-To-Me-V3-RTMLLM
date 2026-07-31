# Usage Rollup (Part D) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `usage` module with keyed daily rollup tables, quota-rejection event recording, a nightly trailing-window builder in the arq worker, and switch quota enforcement + admin usage endpoints to hybrid reads (closed days from rollup, today live from raw).

**Architecture:** `modules/usage/` owns four tables (`usage_daily` keyed by user×day×metric, `llm_model_daily`, `llm_task_daily`, `quota_rejections`) and a code-side `UsageMetric` registry (adding a metric = enum + registry entry, no migration). Import discipline keeps it cycle-free: `usage/kinds.py` and `usage/read_service.py` import **no domain modules** (so domain services and orchestration can call them), while `usage/rollup.py` — the only domain-importing file — collects each module's facts via its public service and upserts idempotently, re-rolling a runtime-tunable trailing window nightly (facts land late: scrape counts grow while jobs run, EPUBs complete next day). Hybrid reads: month usage = Σ rolled closed days + a today-tail the **caller** supplies from its own repository (the existing meter methods already take arbitrary windows — the tail is just a today-window call). Raw tables stay the source of truth forever; the rollup is rebuildable via a backfill CLI.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, arq (cron), pydantic v2.

**Spec:** `docs/superpowers/specs/2026-07-31-usage-rollup-design.md` (approved). Read §4 (module + import discipline), §6 (builder), §7 (hybrid reads) before starting.

**Sequencing:** **Strictly after Part C is fully merged** (the builder rolls `epub_imports`, `download_jobs.deleted_at`/`size_bytes`, and the Part B quotas module). Verify before starting: `backend/app/modules/quotas/service.py` and `backend/app/modules/imports/models.py` exist, and `uv run alembic heads` shows exactly one head (Part C's last migration). Part E (user-facing usage surface) builds on this plan.

## Global Constraints

- Backend gates per task (from `backend/`, **via the Bash tool** — `uv` is not on the PowerShell PATH): `uv run ruff check . --fix && uv run ruff format .`, `uv run mypy .`, `uv run pytest -m "unit or integration"`.
- Integration tests need Postgres/Redis/MinIO and `TEST_DATABASE_URL` pointing at a separate test DB. Apply new migrations to the test DB too (`DATABASE_URL=<TEST_DATABASE_URL value> uv run alembic upgrade head`).
- Commit per task via `/tmp/msg.txt` + `bash scripts/git-commit-clean.sh /tmp/msg.txt`; verify `git log -1 --format=%B`. **Never** add attribution trailers.
- Ruff limits: complexity ≤10, statements ≤20, branches ≤6, args ≤6 — extract helpers. Tests build settings via `tests/factories.py::make_settings`.
- **Import discipline (spec §4):** `usage/kinds.py` + `usage/read_service.py` + `usage/models.py` + `usage/repository.py` import NO domain modules (only `quotas.kinds`, `users` FKs, core). ONLY `usage/rollup.py` imports domain services. `usage` never imports `orchestration`.
- **Semantics (spec §2, §8):** days are UTC dates; rolled rows cover closed days only, today is always read raw; `usage_daily` is **sparse** (zero-amount rows omitted); `storage_bytes` is never rolled (live level meter); soft-deleted download jobs keep counting (rolled by `created_at`, `deleted_at` ignored); raw tables are truth forever — every rollup row must be rebuildable.
- Quota behavior must not change: `>=` blocks, admins exempt, UTC months, one-unit overage. Existing Part B/C quota tests keep passing (their seeded raw rows are all "today" → served by the tail path).

---

### Task 1: `usage` module foundation (metrics, tables, repository, settings)

**Files:**
- Create: `backend/app/modules/usage/__init__.py` (empty)
- Create: `backend/app/modules/usage/kinds.py`
- Create: `backend/app/modules/usage/models.py`
- Create: `backend/app/modules/usage/repository.py`
- Create: `backend/app/modules/usage/read_service.py`
- Modify: `backend/app/core/orm.py` (register models)
- Modify: `backend/app/core/config.py` (`UsageSettings` group)
- Modify: `backend/app/modules/runtime_config/registry.py` (register the group)
- Create: `backend/migrations/versions/<generated>_add_usage_rollup_tables.py`
- Test: `backend/tests/usage/__init__.py` (empty), `backend/tests/usage/test_usage_foundation.py`

**Interfaces:**
- Consumes: `QuotaKind` (Part B), `QuotaService.current_month_window` (Part B).
- Produces (used by every later task):
  - `UsageMetric(StrEnum)` — values: `llm_tokens_in`, `llm_tokens_out`, `llm_cost_usd`, `llm_executions`, `llm_failures`, `audio_chapters`, `audio_jobs`, `audio_jobs_failed`, `scrape_chapters`, `scrape_jobs`, `scrape_jobs_failed`, `epub_imports`, `epub_imports_failed`, `rejected_llm_tokens`, `rejected_llm_cost_usd`, `rejected_audio_chapters`, `rejected_storage_bytes`, `rejected_scrape_chapters`, `rejected_epub_imports`
  - `METRIC_REGISTRY: dict[UsageMetric, MetricMeta]` (`label: str`, `unit: str`); `KIND_METRICS: dict[QuotaKind, tuple[UsageMetric, ...]]` (no `STORAGE_BYTES` key); `REJECTION_METRICS: dict[QuotaKind, UsageMetric]` (all six kinds)
  - Fact dataclasses: `UsageFact(user_id: UUID, metric: UsageMetric, amount: float)`, `LlmModelFact(provider: str, model: str, tokens_in: int, tokens_out: int, cost_usd: float, executions: int)`, `LlmTaskFact(task: str, tokens_in: int, tokens_out: int, cost_usd: float, executions: int)`
  - Models: `UsageDaily`, `LlmModelDaily`, `LlmTaskDaily`, `QuotaRejection`
  - `UsageRepository(session)`: `replace_day(day, facts)`, `replace_llm_day(day, model_rows, task_rows)`, `rolled_amount(user_id, metrics, *, start_day, end_day) -> float`, `rolled_user_table(*, start_day, end_day) -> dict[UUID, dict[UsageMetric, float]]`, `rolled_totals(metrics, *, start_day, end_day) -> dict[UsageMetric, float]`, `rolled_model_rows(*, start_day, end_day) -> list[LlmModelFact]`, `rolled_task_rows(*, start_day, end_day) -> list[LlmTaskFact]`, `add_rejection(user_id, quota_kind, source)`, `rejection_facts(day) -> list[UsageFact]`
  - `UsageReadService(session)`: `rolled_amount(...)` passthrough, `async rolled_month_amount(user_id, kind, now) -> float`, `@staticmethod hybrid_split(now) -> tuple[date, datetime]` (today's UTC date, today's 00:00 UTC datetime), `async record_rejection(user_id, kind, source) -> None` (flush only; caller commits)
  - `Settings.usage.rollup_window_days` (default 7, `ge=1`, env `USAGE_ROLLUP_WINDOW_DAYS`), runtime-tunable

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/usage/test_usage_foundation.py
"""Metric registry + rollup repository roundtrip (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.modules.quotas.kinds import QuotaKind
from app.modules.usage.kinds import (
    KIND_METRICS,
    METRIC_REGISTRY,
    REJECTION_METRICS,
    UsageFact,
    UsageMetric,
)
from app.modules.usage.models import QuotaRejection, UsageDaily
from app.modules.usage.repository import UsageRepository
from app.modules.users.schemas import UserCreate
from app.modules.users.service import UserService
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(delete(UsageDaily))
        await db.execute(delete(QuotaRejection))
        await db.commit()
        yield db
        await db.rollback()
        await db.execute(delete(UsageDaily))
        await db.execute(delete(QuotaRejection))
        await db.commit()
    await engine.dispose()


async def _user_id(session: AsyncSession):
    user = await UserService(session).ensure_user(
        UserCreate(username=f"usg_{uuid4().hex[:8]}", password="test-pass-123")
    )
    return user.id


@pytest.mark.unit
def test_registry_covers_every_metric_and_kind() -> None:
    assert set(METRIC_REGISTRY) == set(UsageMetric)
    # Every quota kind except the level meter maps to usage metrics...
    assert set(KIND_METRICS) == set(QuotaKind) - {QuotaKind.STORAGE_BYTES}
    # ...and every kind (storage included) has a rejection metric.
    assert set(REJECTION_METRICS) == set(QuotaKind)
    assert KIND_METRICS[QuotaKind.LLM_TOKENS] == (
        UsageMetric.LLM_TOKENS_IN,
        UsageMetric.LLM_TOKENS_OUT,
    )


@pytest.mark.unit
def test_usage_settings_default_and_registry() -> None:
    from app.modules.runtime_config.registry import TUNABLE_FIELDS

    from tests.factories import make_settings

    assert make_settings().usage.rollup_window_days == 7
    assert make_settings(usage_rollup_window_days=3).usage.rollup_window_days == 3
    assert "usage.rollup_window_days" in TUNABLE_FIELDS


@pytest.mark.integration
@pytest.mark.asyncio
async def test_replace_day_is_idempotent_and_sparse(session: AsyncSession) -> None:
    uid = await _user_id(session)
    repo = UsageRepository(session)
    day = date(2026, 7, 30)
    facts = [
        UsageFact(uid, UsageMetric.LLM_TOKENS_IN, 100.0),
        UsageFact(uid, UsageMetric.LLM_TOKENS_OUT, 40.0),
        UsageFact(uid, UsageMetric.AUDIO_CHAPTERS, 0.0),  # sparse: must be dropped
    ]
    await repo.replace_day(day, facts)
    await repo.replace_day(day, facts)  # idempotent
    await session.commit()

    rows = (await session.execute(select(UsageDaily))).scalars().all()
    assert len(rows) == 2  # zero-amount row omitted, no duplicates
    amount = await repo.rolled_amount(
        uid,
        (UsageMetric.LLM_TOKENS_IN, UsageMetric.LLM_TOKENS_OUT),
        start_day=date(2026, 7, 1),
        end_day=date(2026, 8, 1),
    )
    assert amount == 140.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rolled_amount_excludes_end_day(session: AsyncSession) -> None:
    """[start_day, end_day) — the hybrid read must not double-count today."""
    uid = await _user_id(session)
    repo = UsageRepository(session)
    await repo.replace_day(
        date(2026, 7, 30), [UsageFact(uid, UsageMetric.LLM_COST_USD, 1.0)]
    )
    await repo.replace_day(
        date(2026, 7, 31), [UsageFact(uid, UsageMetric.LLM_COST_USD, 9.0)]
    )
    await session.commit()
    amount = await repo.rolled_amount(
        uid,
        (UsageMetric.LLM_COST_USD,),
        start_day=date(2026, 7, 1),
        end_day=date(2026, 7, 31),
    )
    assert amount == 1.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rejections_roundtrip_to_facts(session: AsyncSession) -> None:
    uid = await _user_id(session)
    repo = UsageRepository(session)
    repo.add_rejection(uid, QuotaKind.LLM_TOKENS, "chat")
    repo.add_rejection(uid, QuotaKind.LLM_TOKENS, "chat")
    repo.add_rejection(uid, QuotaKind.AUDIO_CHAPTERS, "api")
    await session.commit()

    from datetime import UTC, datetime

    facts = await repo.rejection_facts(datetime.now(UTC).date())
    by_metric = {(f.user_id, f.metric): f.amount for f in facts}
    assert by_metric[(uid, UsageMetric.REJECTED_LLM_TOKENS)] == 2.0
    assert by_metric[(uid, UsageMetric.REJECTED_AUDIO_CHAPTERS)] == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `uv run pytest tests/usage/test_usage_foundation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.modules.usage'`

- [ ] **Step 3: Implement `kinds.py`**

```python
# backend/app/modules/usage/kinds.py
"""Usage metric registry — metrics live in code; daily amounts in usage_daily.

Adding a metric = enum value + METRIC_REGISTRY entry + a fact source in the
owning module's daily_usage_facts(). No migration (same keyed philosophy as
membership_quotas). This file imports NO domain modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.modules.quotas.kinds import QuotaKind


class UsageMetric(StrEnum):
    LLM_TOKENS_IN = "llm_tokens_in"
    LLM_TOKENS_OUT = "llm_tokens_out"
    LLM_COST_USD = "llm_cost_usd"
    LLM_EXECUTIONS = "llm_executions"
    LLM_FAILURES = "llm_failures"
    AUDIO_CHAPTERS = "audio_chapters"
    AUDIO_JOBS = "audio_jobs"
    AUDIO_JOBS_FAILED = "audio_jobs_failed"
    SCRAPE_CHAPTERS = "scrape_chapters"
    SCRAPE_JOBS = "scrape_jobs"
    SCRAPE_JOBS_FAILED = "scrape_jobs_failed"
    EPUB_IMPORTS = "epub_imports"
    EPUB_IMPORTS_FAILED = "epub_imports_failed"
    REJECTED_LLM_TOKENS = "rejected_llm_tokens"
    REJECTED_LLM_COST_USD = "rejected_llm_cost_usd"
    REJECTED_AUDIO_CHAPTERS = "rejected_audio_chapters"
    REJECTED_STORAGE_BYTES = "rejected_storage_bytes"
    REJECTED_SCRAPE_CHAPTERS = "rejected_scrape_chapters"
    REJECTED_EPUB_IMPORTS = "rejected_epub_imports"


@dataclass(frozen=True, slots=True)
class MetricMeta:
    label: str
    unit: str


METRIC_REGISTRY: dict[UsageMetric, MetricMeta] = {
    UsageMetric.LLM_TOKENS_IN: MetricMeta("AI tokens in", "tokens"),
    UsageMetric.LLM_TOKENS_OUT: MetricMeta("AI tokens out", "tokens"),
    UsageMetric.LLM_COST_USD: MetricMeta("AI spend", "USD"),
    UsageMetric.LLM_EXECUTIONS: MetricMeta("AI calls", "calls"),
    UsageMetric.LLM_FAILURES: MetricMeta("AI failures", "calls"),
    UsageMetric.AUDIO_CHAPTERS: MetricMeta("Audio chapters", "chapters"),
    UsageMetric.AUDIO_JOBS: MetricMeta("Audio jobs", "jobs"),
    UsageMetric.AUDIO_JOBS_FAILED: MetricMeta("Audio jobs failed", "jobs"),
    UsageMetric.SCRAPE_CHAPTERS: MetricMeta("Scraped chapters", "chapters"),
    UsageMetric.SCRAPE_JOBS: MetricMeta("Scrape jobs", "jobs"),
    UsageMetric.SCRAPE_JOBS_FAILED: MetricMeta("Scrape jobs failed", "jobs"),
    UsageMetric.EPUB_IMPORTS: MetricMeta("EPUB imports", "imports"),
    UsageMetric.EPUB_IMPORTS_FAILED: MetricMeta("EPUB imports failed", "imports"),
    UsageMetric.REJECTED_LLM_TOKENS: MetricMeta("Blocked: AI tokens", "events"),
    UsageMetric.REJECTED_LLM_COST_USD: MetricMeta("Blocked: AI spend", "events"),
    UsageMetric.REJECTED_AUDIO_CHAPTERS: MetricMeta("Blocked: audio", "events"),
    UsageMetric.REJECTED_STORAGE_BYTES: MetricMeta("Blocked: storage", "events"),
    UsageMetric.REJECTED_SCRAPE_CHAPTERS: MetricMeta("Blocked: scraping", "events"),
    UsageMetric.REJECTED_EPUB_IMPORTS: MetricMeta("Blocked: imports", "events"),
}

# Quota kind -> metrics summed for its monthly usage. STORAGE_BYTES is a
# LEVEL meter (live stored_bytes query) and is deliberately absent.
KIND_METRICS: dict[QuotaKind, tuple[UsageMetric, ...]] = {
    QuotaKind.LLM_TOKENS: (UsageMetric.LLM_TOKENS_IN, UsageMetric.LLM_TOKENS_OUT),
    QuotaKind.LLM_COST_USD: (UsageMetric.LLM_COST_USD,),
    QuotaKind.AUDIO_CHAPTERS: (UsageMetric.AUDIO_CHAPTERS,),
    QuotaKind.SCRAPE_CHAPTERS: (UsageMetric.SCRAPE_CHAPTERS,),
    QuotaKind.EPUB_IMPORTS: (UsageMetric.EPUB_IMPORTS,),
}

REJECTION_METRICS: dict[QuotaKind, UsageMetric] = {
    QuotaKind.LLM_TOKENS: UsageMetric.REJECTED_LLM_TOKENS,
    QuotaKind.LLM_COST_USD: UsageMetric.REJECTED_LLM_COST_USD,
    QuotaKind.AUDIO_CHAPTERS: UsageMetric.REJECTED_AUDIO_CHAPTERS,
    QuotaKind.STORAGE_BYTES: UsageMetric.REJECTED_STORAGE_BYTES,
    QuotaKind.SCRAPE_CHAPTERS: UsageMetric.REJECTED_SCRAPE_CHAPTERS,
    QuotaKind.EPUB_IMPORTS: UsageMetric.REJECTED_EPUB_IMPORTS,
}


@dataclass(frozen=True, slots=True)
class UsageFact:
    """One (user, metric, amount) fact for one day; produced by owning modules."""

    user_id: UUID
    metric: UsageMetric
    amount: float


@dataclass(frozen=True, slots=True)
class LlmModelFact:
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    executions: int


@dataclass(frozen=True, slots=True)
class LlmTaskFact:
    task: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    executions: int
```

- [ ] **Step 4: Implement `models.py`**

```python
# backend/app/modules/usage/models.py
"""SQLAlchemy models for the usage rollup (derived cache; raw stays truth)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UsageDaily(Base):
    """One (user, day, metric) amount. Sparse: zero-amount rows are omitted."""

    __tablename__ = "usage_daily"
    __table_args__ = (
        UniqueConstraint("user_id", "day", "metric", name="uq_usage_daily_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    day: Mapped[date] = mapped_column(Date, index=True)
    metric: Mapped[str] = mapped_column(String(48))
    amount: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LlmModelDaily(Base):
    """Cross-user daily LLM aggregates per (provider, model) for admin tiles."""

    __tablename__ = "llm_model_daily"
    __table_args__ = (
        UniqueConstraint("day", "provider", "model", name="uq_llm_model_daily_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    day: Mapped[date] = mapped_column(Date, index=True)
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(128))
    tokens_in: Mapped[int] = mapped_column(BigInteger, default=0)
    tokens_out: Mapped[int] = mapped_column(BigInteger, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    executions: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LlmTaskDaily(Base):
    """Cross-user daily LLM aggregates per task for admin tiles."""

    __tablename__ = "llm_task_daily"
    __table_args__ = (UniqueConstraint("day", "task", name="uq_llm_task_daily_key"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    day: Mapped[date] = mapped_column(Date, index=True)
    task: Mapped[str] = mapped_column(String(64))
    tokens_in: Mapped[int] = mapped_column(BigInteger, default=0)
    tokens_out: Mapped[int] = mapped_column(BigInteger, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    executions: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class QuotaRejection(Base):
    """Raw rejection event (denied turn / 429); rolled into rejected_* metrics."""

    __tablename__ = "quota_rejections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    quota_kind: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(16))  # "chat" | "api"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
```

Register in `backend/app/core/orm.py::import_all_models` (`from app.modules.usage import models as usage_models` + tuple entry).

- [ ] **Step 5: Implement `repository.py` and `read_service.py`**

```python
# backend/app/modules/usage/repository.py
"""DB access for the usage module's tables only."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.quotas.kinds import QuotaKind
from app.modules.usage.kinds import (
    REJECTION_METRICS,
    LlmModelFact,
    LlmTaskFact,
    UsageFact,
    UsageMetric,
)
from app.modules.usage.models import LlmModelDaily, LlmTaskDaily, QuotaRejection, UsageDaily


def day_window(day: date) -> tuple[datetime, datetime]:
    """[day 00:00 UTC, next day 00:00 UTC) — shared by fact queries."""
    start = datetime.combine(day, time(), tzinfo=UTC)
    return start, start + timedelta(days=1)


class UsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_day(self, day: date, facts: Sequence[UsageFact]) -> None:
        """Idempotent per-day rebuild: delete the day, insert non-zero facts."""
        await self._session.execute(delete(UsageDaily).where(UsageDaily.day == day))
        for fact in facts:
            if fact.amount == 0:
                continue  # sparse: zero rows are omitted (spec §4.2)
            self._session.add(
                UsageDaily(
                    user_id=fact.user_id,
                    day=day,
                    metric=fact.metric.value,
                    amount=fact.amount,
                )
            )
        await self._session.flush()

    async def replace_llm_day(
        self,
        day: date,
        model_rows: Sequence[LlmModelFact],
        task_rows: Sequence[LlmTaskFact],
    ) -> None:
        await self._session.execute(delete(LlmModelDaily).where(LlmModelDaily.day == day))
        await self._session.execute(delete(LlmTaskDaily).where(LlmTaskDaily.day == day))
        for row in model_rows:
            self._session.add(
                LlmModelDaily(
                    day=day,
                    provider=row.provider,
                    model=row.model,
                    tokens_in=row.tokens_in,
                    tokens_out=row.tokens_out,
                    cost_usd=row.cost_usd,
                    executions=row.executions,
                )
            )
        for trow in task_rows:
            self._session.add(
                LlmTaskDaily(
                    day=day,
                    task=trow.task,
                    tokens_in=trow.tokens_in,
                    tokens_out=trow.tokens_out,
                    cost_usd=trow.cost_usd,
                    executions=trow.executions,
                )
            )
        await self._session.flush()

    async def rolled_amount(
        self,
        user_id: UUID,
        metrics: Sequence[UsageMetric],
        *,
        start_day: date,
        end_day: date,
    ) -> float:
        """Sum over [start_day, end_day) for one user."""
        stmt = select(func.coalesce(func.sum(UsageDaily.amount), 0.0)).where(
            UsageDaily.user_id == user_id,
            UsageDaily.metric.in_([m.value for m in metrics]),
            UsageDaily.day >= start_day,
            UsageDaily.day < end_day,
        )
        return float((await self._session.execute(stmt)).scalar_one())

    async def rolled_user_table(
        self, *, start_day: date, end_day: date
    ) -> dict[UUID, dict[UsageMetric, float]]:
        """Per-user metric sums over [start_day, end_day) — admin by-user."""
        stmt = (
            select(UsageDaily.user_id, UsageDaily.metric, func.sum(UsageDaily.amount))
            .where(UsageDaily.day >= start_day, UsageDaily.day < end_day)
            .group_by(UsageDaily.user_id, UsageDaily.metric)
        )
        table: dict[UUID, dict[UsageMetric, float]] = {}
        for user_id, metric, amount in (await self._session.execute(stmt)).all():
            try:
                key = UsageMetric(metric)
            except ValueError:
                continue  # row from a retired metric: skip, never crash
            table.setdefault(user_id, {})[key] = float(amount)
        return table

    async def rolled_totals(
        self, metrics: Sequence[UsageMetric], *, start_day: date, end_day: date
    ) -> dict[UsageMetric, float]:
        stmt = (
            select(UsageDaily.metric, func.sum(UsageDaily.amount))
            .where(
                UsageDaily.metric.in_([m.value for m in metrics]),
                UsageDaily.day >= start_day,
                UsageDaily.day < end_day,
            )
            .group_by(UsageDaily.metric)
        )
        rows = (await self._session.execute(stmt)).all()
        return {UsageMetric(metric): float(amount) for metric, amount in rows}

    async def rolled_model_rows(
        self, *, start_day: date, end_day: date
    ) -> list[LlmModelFact]:
        stmt = (
            select(
                LlmModelDaily.provider,
                LlmModelDaily.model,
                func.sum(LlmModelDaily.tokens_in),
                func.sum(LlmModelDaily.tokens_out),
                func.sum(LlmModelDaily.cost_usd),
                func.sum(LlmModelDaily.executions),
            )
            .where(LlmModelDaily.day >= start_day, LlmModelDaily.day < end_day)
            .group_by(LlmModelDaily.provider, LlmModelDaily.model)
        )
        return [
            LlmModelFact(r[0], r[1], int(r[2]), int(r[3]), float(r[4]), int(r[5]))
            for r in (await self._session.execute(stmt)).all()
        ]

    async def rolled_task_rows(
        self, *, start_day: date, end_day: date
    ) -> list[LlmTaskFact]:
        stmt = (
            select(
                LlmTaskDaily.task,
                func.sum(LlmTaskDaily.tokens_in),
                func.sum(LlmTaskDaily.tokens_out),
                func.sum(LlmTaskDaily.cost_usd),
                func.sum(LlmTaskDaily.executions),
            )
            .where(LlmTaskDaily.day >= start_day, LlmTaskDaily.day < end_day)
            .group_by(LlmTaskDaily.task)
        )
        return [
            LlmTaskFact(r[0], int(r[1]), int(r[2]), float(r[3]), int(r[4]))
            for r in (await self._session.execute(stmt)).all()
        ]

    def add_rejection(self, user_id: UUID, kind: QuotaKind, source: str) -> None:
        self._session.add(
            QuotaRejection(user_id=user_id, quota_kind=kind.value, source=source)
        )

    async def rejection_facts(self, day: date) -> list[UsageFact]:
        """Roll this module's own raw events into rejected_* facts."""
        start, end = day_window(day)
        stmt = (
            select(
                QuotaRejection.user_id,
                QuotaRejection.quota_kind,
                func.count(QuotaRejection.id),
            )
            .where(QuotaRejection.created_at >= start, QuotaRejection.created_at < end)
            .group_by(QuotaRejection.user_id, QuotaRejection.quota_kind)
        )
        facts: list[UsageFact] = []
        for user_id, kind_raw, count in (await self._session.execute(stmt)).all():
            try:
                metric = REJECTION_METRICS[QuotaKind(kind_raw)]
            except ValueError:
                continue
            facts.append(UsageFact(user_id, metric, float(count)))
        return facts
```

```python
# backend/app/modules/usage/read_service.py
"""Rolled reads + rejection recording. Imports NO domain modules.

Hybrid rule (spec §7): closed days come from usage_daily; TODAY is always
read live from raw tables by the CALLER (each domain's existing meter with a
today window) — that one-directional split is what keeps domain -> usage
imports cycle-free. rollup.py is the only usage file importing domains.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.service import QuotaService
from app.modules.usage.kinds import KIND_METRICS, UsageMetric
from app.modules.usage.repository import UsageRepository


class UsageReadService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = UsageRepository(session)

    @staticmethod
    def hybrid_split(now: datetime) -> tuple[date, datetime]:
        """(today's UTC date, today's 00:00 UTC) — rolled reads end BEFORE
        today; the caller's raw tail starts AT today_start."""
        today = now.astimezone(UTC).date()
        return today, datetime.combine(today, time(), tzinfo=UTC)

    async def rolled_amount(
        self,
        user_id: UUID,
        metrics: tuple[UsageMetric, ...],
        *,
        start_day: date,
        end_day: date,
    ) -> float:
        return await self._repo.rolled_amount(
            user_id, metrics, start_day=start_day, end_day=end_day
        )

    async def rolled_month_amount(
        self, user_id: UUID, kind: QuotaKind, now: datetime
    ) -> float:
        """Rolled part of the current month for a quota kind: [month start, today)."""
        month_start, _ = QuotaService.current_month_window(now)
        today, _ = self.hybrid_split(now)
        return await self._repo.rolled_amount(
            user_id, KIND_METRICS[kind], start_day=month_start.date(), end_day=today
        )

    async def record_rejection(self, user_id: UUID, kind: QuotaKind, source: str) -> None:
        """Queue a rejection event on the caller's session (caller commits)."""
        self._repo.add_rejection(user_id, kind, source)
```

- [ ] **Step 6: Settings group + runtime_config registration + migration**

In `backend/app/core/config.py`, add after `LlmRuntimeSettings`:

```python
class UsageSettings(_GroupSettings):
    """Usage rollup knobs (Part D)."""

    # Nightly re-roll horizon: late-arriving facts (running scrape jobs,
    # next-day EPUB completions) converge within this many days.
    rollup_window_days: int = Field(default=7, ge=1, validation_alias="usage_rollup_window_days")
```

and `usage: UsageSettings = Field(default_factory=UsageSettings)` on `Settings`. In `backend/app/modules/runtime_config/registry.py`, import `UsageSettings` and add `"usage": UsageSettings,` to `_FULL_SECTIONS`.

Migration: `uv run alembic revision -m "add usage rollup tables"` (single head; `down_revision` = Part C's last migration). Fill:

```python
def upgrade() -> None:
    op.create_table(
        "usage_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("metric", sa.String(length=48), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "day", "metric", name="uq_usage_daily_key"),
    )
    op.create_index(op.f("ix_usage_daily_user_id"), "usage_daily", ["user_id"])
    op.create_index(op.f("ix_usage_daily_day"), "usage_daily", ["day"])
    op.create_table(
        "llm_model_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("tokens_in", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("executions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day", "provider", "model", name="uq_llm_model_daily_key"),
    )
    op.create_index(op.f("ix_llm_model_daily_day"), "llm_model_daily", ["day"])
    op.create_table(
        "llm_task_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("task", sa.String(length=64), nullable=False),
        sa.Column("tokens_in", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("executions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day", "task", name="uq_llm_task_daily_key"),
    )
    op.create_index(op.f("ix_llm_task_daily_day"), "llm_task_daily", ["day"])
    op.create_table(
        "quota_rejections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("quota_kind", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quota_rejections_user_id"), "quota_rejections", ["user_id"])
    op.create_index(
        op.f("ix_quota_rejections_created_at"), "quota_rejections", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_quota_rejections_created_at"), table_name="quota_rejections")
    op.drop_index(op.f("ix_quota_rejections_user_id"), table_name="quota_rejections")
    op.drop_table("quota_rejections")
    op.drop_index(op.f("ix_llm_task_daily_day"), table_name="llm_task_daily")
    op.drop_table("llm_task_daily")
    op.drop_index(op.f("ix_llm_model_daily_day"), table_name="llm_model_daily")
    op.drop_table("llm_model_daily")
    op.drop_index(op.f("ix_usage_daily_day"), table_name="usage_daily")
    op.drop_index(op.f("ix_usage_daily_user_id"), table_name="usage_daily")
    op.drop_table("usage_daily")
```

Verify reversibility; apply to the test DB.

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/usage/test_usage_foundation.py -v`
Expected: PASS (6 tests)

- [ ] **Step 8: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add usage module with daily rollup tables and metric registry\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 2: Record quota rejections (chat + REST paths)

**Files:**
- Modify: `backend/app/modules/quotas/exceptions.py` (`user_id` on the error)
- Modify: `backend/app/modules/quotas/service.py` (`enforce` passes `user_id` into the error)
- Modify: `backend/app/modules/orchestration/service.py` (record on the chat catch)
- Modify: `backend/app/core/exceptions.py` (record in the 429 handler)
- Test: `backend/tests/usage/test_rejection_recording.py`

**Interfaces:**
- Consumes: `UsageReadService.record_rejection` (Task 1), `QuotaRejection` model.
- Produces: `QuotaExceededError.user_id: UUID | None`; module function `record_rejection_detached(user_id, kind, source) -> None` in `backend/app/modules/usage/read_service.py` (own `SessionLocal` transaction — survives the request rollback; best-effort, never raises). Chat rejections carry `source="chat"`, REST `source="api"`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/usage/test_rejection_recording.py
"""Rejections leave rows: chat path (same session) + detached path (own txn)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from app.core.config import Settings, get_settings
from app.modules.llm.chat_service import ChatService
from app.modules.llm.models import LlmExecution
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.seed import seed_membership_policies
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
from app.modules.usage.models import QuotaRejection
from app.modules.usage.read_service import record_rejection_detached
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.factories import make_settings
from tests.llm.stream_fakes import stream_from_call


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        for model in (QuotaRejection, MembershipQuota, MembershipPolicy):
            await db.execute(delete(model))
        await db.commit()
        await seed_membership_policies(db)
        yield db
        await db.rollback()
        for model in (QuotaRejection, MembershipQuota, MembershipPolicy):
            await db.execute(delete(model))
        await db.commit()
        await seed_membership_policies(db)
    await engine.dispose()


def _settings() -> Settings:
    return make_settings(
        llm_enabled=True,
        gemini_api_key="test-key",
        llm_provider="gemini",
        llm_model="gemini-3.5-flash-lite",
    )


async def _user(session: AsyncSession) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(username=f"rej_{uuid4().hex[:8]}", password="test-pass-123")
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chat_rejection_writes_row(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(session)
    session.add(
        MembershipQuota(
            membership=Membership.FREE.value,
            quota_kind=QuotaKind.LLM_TOKENS.value,
            limit_value=10.0,
        )
    )
    session.add(
        LlmExecution(
            user_id=user.id,
            task="chat_tools",
            provider="gemini",
            model="m",
            tokens_in=50,
            tokens_out=50,
            cost=0.0,
            latency_ms=1,
            status="ok",
        )
    )
    await session.commit()

    service = ChatService(session, _settings())

    async def _never_called(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("provider must not be called")

    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_never_called))
    events = [e async for e in service.stream_chat(user, "hi", None)]
    assert next(e for e in events if e.event == "error").data["code"] == "quota_exceeded"

    row = (
        await session.execute(
            select(QuotaRejection).where(QuotaRejection.user_id == user.id)
        )
    ).scalar_one()
    assert row.quota_kind == "llm_tokens"
    assert row.source == "chat"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_detached_recording_survives_caller_rollback(
    session: AsyncSession,
) -> None:
    """The 429 handler's write must not die with the request transaction."""
    user = await _user(session)
    await record_rejection_detached(user.id, QuotaKind.AUDIO_CHAPTERS, "api")
    await session.rollback()  # simulate the request txn rolling back afterwards

    row = (
        await session.execute(
            select(QuotaRejection).where(QuotaRejection.user_id == user.id)
        )
    ).scalar_one()
    assert row.quota_kind == "audio_chapters"
    assert row.source == "api"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/usage/test_rejection_recording.py -v`
Expected: FAIL — `ImportError: cannot import name 'record_rejection_detached'`.

- [ ] **Step 3: Carry `user_id` on the error; add the detached writer**

In `backend/app/modules/quotas/exceptions.py`, extend `QuotaExceededError.__init__` with a keyword `user_id: UUID | None = None` stored as `self.user_id` (add `from uuid import UUID` under the datetime import). In `backend/app/modules/quotas/service.py::enforce`, pass it through: `raise QuotaExceededError(kind, limit=limit, used=used, resets_at=resets_at, user_id=user_id)`.

Append to `backend/app/modules/usage/read_service.py` (module level; add `import logging` + `from app.core.db import SessionLocal`):

```python
logger = logging.getLogger(__name__)


async def record_rejection_detached(
    user_id: UUID | None, kind: QuotaKind, source: str
) -> None:
    """Write a rejection event in its OWN transaction (429 handler path).

    The request transaction rolls back when QuotaExceededError propagates,
    so the handler cannot use the request session. Best-effort: a failure
    here must never break the 429 response.
    """
    if user_id is None:
        return
    try:
        async with SessionLocal() as session:
            UsageRepository(session).add_rejection(user_id, kind, source)
            await session.commit()
    except Exception:  # noqa: BLE001 — observability write must stay best-effort
        logger.warning(
            "failed to record quota rejection",
            extra={"user_id": str(user_id), "kind": kind.value},
        )
```

- [ ] **Step 4: Record at the two boundaries**

In `backend/app/modules/orchestration/service.py`, the Part B catch in `run` becomes (add `from app.modules.usage.read_service import UsageReadService` to imports):

```python
        try:
            await self._check_llm_quota(user)
        except QuotaExceededError as exc:
            await UsageReadService(self._session).record_rejection(
                user.id, exc.kind, "chat"
            )
            await self._session.commit()
            yield _quota_error_event(exc)
            return
```

In `backend/app/core/exceptions.py::_register_quota_handlers`, the 429 handler becomes (import `record_rejection_detached` from `app.modules.usage.read_service`):

```python
    @app.exception_handler(QuotaExceededError)
    async def _quota_exceeded(
        _request: Request,
        exc: QuotaExceededError,
    ) -> JSONResponse:
        await record_rejection_detached(exc.user_id, exc.kind, "api")
        return JSONResponse(status_code=429, content={"detail": str(exc)})
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/usage/test_rejection_recording.py tests/orchestration/test_monthly_quota_enforcement.py -v`
Expected: PASS (2 new + the Part B suite unchanged).

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: record quota rejections from chat and REST paths\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 3: Domain `daily_usage_facts` methods

**Files:**
- Modify: `backend/app/modules/llm/repository.py` + `backend/app/modules/llm/service.py`
- Modify: `backend/app/modules/downloads/repository.py` + `backend/app/modules/downloads/service.py`
- Modify: `backend/app/modules/scraping/repository.py` + `backend/app/modules/scraping/service.py`
- Modify: `backend/app/modules/imports/repository.py` + `backend/app/modules/imports/service.py`
- Test: `backend/tests/usage/test_daily_facts.py`

**Interfaces:**
- Consumes: `UsageFact`, `LlmModelFact`, `LlmTaskFact`, `UsageMetric`, `day_window` (Task 1).
- Produces (used by Task 4's builder — exact signatures):
  - `LlmService.daily_usage_facts(day: date) -> list[UsageFact]` (tokens in/out, cost, executions, failures per user), `LlmService.daily_model_facts(day) -> list[LlmModelFact]`, `LlmService.daily_task_facts(day) -> list[LlmTaskFact]`
  - `DownloadService.daily_usage_facts(day) -> list[UsageFact]` (audio_chapters/audio_jobs/audio_jobs_failed; by `created_at`, **soft-deleted included**)
  - `ScrapingService.daily_usage_facts(day) -> list[UsageFact]` (scrape_chapters/scrape_jobs/scrape_jobs_failed)
  - `ImportService.daily_usage_facts(day) -> list[UsageFact]` (epub_imports completed / epub_imports_failed; by `created_at`)
  - Each service method is a one-line pass-through to a repository method over its own tables; domain modules import only `usage.kinds` (allowed leaf).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/usage/test_daily_facts.py
"""Each module reports correct per-day facts from its own tables (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.modules.downloads.models import DownloadJob
from app.modules.downloads.service import DownloadService
from app.modules.imports.repository import EpubImportRepository
from app.modules.imports.service import ImportService
from app.modules.llm.models import LlmExecution
from app.modules.llm.service import LlmService
from app.modules.scraping.models import ScrapingJob, ScrapingSource
from app.modules.scraping.service import ScrapingService
from app.modules.usage.kinds import UsageMetric
from app.modules.users.schemas import UserCreate
from app.modules.users.service import UserService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.factories import make_settings


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
        await db.rollback()
    await engine.dispose()


async def _uid(session: AsyncSession) -> UUID:
    user = await UserService(session).ensure_user(
        UserCreate(username=f"fac_{uuid4().hex[:8]}", password="test-pass-123")
    )
    return user.id


def _metric_map(facts: list, uid: UUID) -> dict[UsageMetric, float]:
    return {f.metric: f.amount for f in facts if f.user_id == uid}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_llm_daily_facts(session: AsyncSession) -> None:
    uid = await _uid(session)
    session.add_all(
        [
            LlmExecution(user_id=uid, task="chat_tools", provider="gemini", model="m1",
                         tokens_in=100, tokens_out=40, cost=0.5, latency_ms=1, status="ok"),
            LlmExecution(user_id=uid, task="summarize", provider="gemini", model="m2",
                         tokens_in=10, tokens_out=5, cost=0.1, latency_ms=1, status="error"),
        ]
    )
    await session.commit()
    today = datetime.now(UTC).date()

    facts = _metric_map(
        await LlmService(session, make_settings()).daily_usage_facts(today), uid
    )
    assert facts[UsageMetric.LLM_TOKENS_IN] == 110.0
    assert facts[UsageMetric.LLM_TOKENS_OUT] == 45.0
    assert facts[UsageMetric.LLM_COST_USD] == pytest.approx(0.6)
    assert facts[UsageMetric.LLM_EXECUTIONS] == 2.0
    assert facts[UsageMetric.LLM_FAILURES] == 1.0

    models = await LlmService(session, make_settings()).daily_model_facts(today)
    m1 = next(m for m in models if m.model == "m1")
    assert (m1.tokens_in, m1.executions) == (100, 1)
    tasks = await LlmService(session, make_settings()).daily_task_facts(today)
    assert {t.task for t in tasks} >= {"chat_tools", "summarize"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_download_daily_facts_include_soft_deleted(session: AsyncSession) -> None:
    uid = await _uid(session)
    book_id = uuid4()  # FK: create via library like Part C tests
    from app.modules.books.schemas import BookCreate
    from app.modules.library.service import LibraryService

    book = await LibraryService(session).add_book(
        uid, BookCreate(title="Facts", author="A", description="d")
    )
    book_id = book.id
    session.add_all(
        [
            DownloadJob(user_id=uid, book_id=book_id, chapter_from=1, chapter_to=3,
                        provider="edge", voice="v", rate="1.0", status="complete",
                        total_count=3),
            DownloadJob(user_id=uid, book_id=book_id, chapter_from=1, chapter_to=2,
                        provider="edge", voice="v", rate="1.0", status="failed",
                        total_count=2, deleted_at=datetime.now(UTC)),
        ]
    )
    await session.commit()
    facts = _metric_map(
        await DownloadService(session).daily_usage_facts(datetime.now(UTC).date()), uid
    )
    assert facts[UsageMetric.AUDIO_CHAPTERS] == 5.0  # deleted row still counts
    assert facts[UsageMetric.AUDIO_JOBS] == 2.0
    assert facts[UsageMetric.AUDIO_JOBS_FAILED] == 1.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scrape_and_epub_daily_facts(session: AsyncSession) -> None:
    uid = await _uid(session)
    source = (await session.execute(select(ScrapingSource).limit(1))).scalar_one_or_none()
    if source is None:
        source = ScrapingSource(name=f"src_{uuid4().hex[:8]}", base_domains=["example.com"])
        session.add(source)
        await session.flush()
    session.add(
        ScrapingJob(user_id=uid, source_id=source.id, start_url="https://x/y",
                    mode="range", status="failed", chapters_done=40)
    )
    repo = EpubImportRepository(session)
    done = await repo.add(uid)
    await repo.set_terminal(done.id, status="completed", chapter_count=9)
    failed = await repo.add(uid)
    await repo.set_terminal(failed.id, status="failed", chapter_count=0)
    await session.commit()
    today = datetime.now(UTC).date()

    scrape = _metric_map(await ScrapingService(session).daily_usage_facts(today), uid)
    assert scrape[UsageMetric.SCRAPE_CHAPTERS] == 40.0
    assert scrape[UsageMetric.SCRAPE_JOBS] == 1.0
    assert scrape[UsageMetric.SCRAPE_JOBS_FAILED] == 1.0

    epub = _metric_map(await ImportService(session).daily_usage_facts(today), uid)
    assert epub[UsageMetric.EPUB_IMPORTS] == 1.0
    assert epub[UsageMetric.EPUB_IMPORTS_FAILED] == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/usage/test_daily_facts.py -v`
Expected: FAIL — `AttributeError: ... has no attribute 'daily_usage_facts'`.

- [ ] **Step 3: Implement the repository fact queries**

Pattern (downloads shown in full; the others follow it). Append to `DownloadRepository` (imports: `from datetime import date`, `from app.modules.usage.kinds import UsageFact, UsageMetric`, `from app.modules.usage.repository import day_window`):

```python
    async def daily_usage_facts(self, day: date) -> list[UsageFact]:
        """Per-user audio facts for one UTC day. Soft-deleted rows INCLUDED
        (flow-meter semantics — deletion never refunds work)."""
        start, end = day_window(day)
        failed = func.count(DownloadJob.id).filter(DownloadJob.status == "failed")
        stmt = (
            select(
                DownloadJob.user_id,
                func.coalesce(func.sum(DownloadJob.total_count), 0),
                func.count(DownloadJob.id),
                failed,
            )
            .where(DownloadJob.created_at >= start, DownloadJob.created_at < end)
            .group_by(DownloadJob.user_id)
        )
        facts: list[UsageFact] = []
        for user_id, chapters, jobs, failed_count in (await self._session.execute(stmt)).all():
            facts.append(UsageFact(user_id, UsageMetric.AUDIO_CHAPTERS, float(chapters)))
            facts.append(UsageFact(user_id, UsageMetric.AUDIO_JOBS, float(jobs)))
            facts.append(UsageFact(user_id, UsageMetric.AUDIO_JOBS_FAILED, float(failed_count)))
        return facts
```

Analogues (each on its own repository, same `day_window` bounds, `GROUP BY user_id`):

- `ScrapingRepository.daily_usage_facts`: `SUM(chapters_done)` → `SCRAPE_CHAPTERS`, `COUNT(id)` → `SCRAPE_JOBS`, `COUNT(id) FILTER (status='failed')` → `SCRAPE_JOBS_FAILED` over `ScrapingJob.created_at`.
- `EpubImportRepository.daily_usage_facts`: `COUNT(id) FILTER (status='completed')` → `EPUB_IMPORTS`, `COUNT(id) FILTER (status='failed')` → `EPUB_IMPORTS_FAILED` over `EpubImportRecord.created_at` (emit both facts even when one is zero — `replace_day` drops zeros).
- `LlmRepository.daily_usage_facts`: per user — `SUM(tokens_in)` → `LLM_TOKENS_IN`, `SUM(tokens_out)` → `LLM_TOKENS_OUT`, `SUM(cost)` → `LLM_COST_USD`, `COUNT(id)` → `LLM_EXECUTIONS`, `COUNT(id) FILTER (status != 'ok')` → `LLM_FAILURES` over `LlmExecution.created_at`.
- `LlmRepository.daily_model_facts`: `GROUP BY provider, model` → `LlmModelFact(provider, model, SUM(tokens_in), SUM(tokens_out), SUM(cost), COUNT(id))`.
- `LlmRepository.daily_task_facts`: `GROUP BY task` → `LlmTaskFact(task, ...)` same sums.

- [ ] **Step 4: Service pass-throughs**

On each service, a one-liner delegating to its repository, e.g. on `DownloadService`:

```python
    async def daily_usage_facts(self, day: date) -> list[UsageFact]:
        """Usage-rollup facts for one UTC day (builder-facing, spec §6)."""
        return await self._repo.daily_usage_facts(day)
```

Same for `ScrapingService`, `ImportService`, and `LlmService` (which also gets `daily_model_facts` / `daily_task_facts` pass-throughs).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/usage/test_daily_facts.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add per-module daily usage fact queries\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 4: Rollup builder, arq cron, backfill CLI

**Files:**
- Create: `backend/app/modules/usage/rollup.py`
- Modify: `backend/app/jobs/worker.py` (cron registration)
- Test: `backend/tests/usage/test_rollup_builder.py`

**Interfaces:**
- Consumes: every `daily_usage_facts`/`daily_model_facts`/`daily_task_facts` (Task 3), `UsageRepository.replace_day/replace_llm_day/rejection_facts` (Task 1), `Settings.usage.rollup_window_days` via `RuntimeConfigService` (jobs read overrides through it, per CLAUDE.md).
- Produces:
  - `async roll_day(session: AsyncSession, day: date) -> None` — collect all facts for one day, replace idempotently
  - `async roll_usage_window(_ctx: object) -> None` — arq cron entry: re-rolls `[today - window, today)` with its own engine (the purge-job pattern)
  - `async backfill(start: date) -> None` + `python -m app.modules.usage.rollup <YYYY-MM-DD>` CLI — rolls `[start, today)`; also the recovery path after worker downtime > window (runbook)

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/usage/test_rollup_builder.py
"""Builder: idempotency, late-arriving convergence, backfill equivalence."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.modules.llm.models import LlmExecution
from app.modules.scraping.models import ScrapingJob, ScrapingSource
from app.modules.usage.kinds import UsageMetric
from app.modules.usage.models import LlmModelDaily, LlmTaskDaily, UsageDaily
from app.modules.usage.repository import UsageRepository
from app.modules.usage.rollup import roll_day
from app.modules.users.schemas import UserCreate
from app.modules.users.service import UserService
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        for model in (UsageDaily, LlmModelDaily, LlmTaskDaily):
            await db.execute(delete(model))
        await db.commit()
        yield db
        await db.rollback()
        for model in (UsageDaily, LlmModelDaily, LlmTaskDaily):
            await db.execute(delete(model))
        await db.commit()
    await engine.dispose()


async def _uid(session: AsyncSession) -> UUID:
    user = await UserService(session).ensure_user(
        UserCreate(username=f"rol_{uuid4().hex[:8]}", password="test-pass-123")
    )
    return user.id


async def _rolled(session: AsyncSession, uid: UUID, metric: UsageMetric) -> float:
    stmt = select(UsageDaily.amount).where(
        UsageDaily.user_id == uid, UsageDaily.metric == metric.value
    )
    value = (await session.execute(stmt)).scalar_one_or_none()
    return float(value) if value is not None else 0.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_roll_day_is_idempotent(session: AsyncSession) -> None:
    uid = await _uid(session)
    session.add(
        LlmExecution(user_id=uid, task="chat_tools", provider="gemini", model="m",
                     tokens_in=100, tokens_out=50, cost=0.2, latency_ms=1, status="ok")
    )
    await session.commit()
    today = datetime.now(UTC).date()

    await roll_day(session, today)
    await session.commit()
    first = (await session.execute(select(UsageDaily))).scalars().all()
    await roll_day(session, today)
    await session.commit()
    second = (await session.execute(select(UsageDaily))).scalars().all()

    assert len(first) == len(second)
    assert await _rolled(session, uid, UsageMetric.LLM_TOKENS_IN) == 100.0
    model_rows = (await session.execute(select(LlmModelDaily))).scalars().all()
    assert len(model_rows) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_late_arriving_facts_converge_on_reroll(session: AsyncSession) -> None:
    """A running scrape job's chapters grow after the first roll (spec §6)."""
    uid = await _uid(session)
    source = (await session.execute(select(ScrapingSource).limit(1))).scalar_one_or_none()
    if source is None:
        source = ScrapingSource(name=f"src_{uuid4().hex[:8]}", base_domains=["example.com"])
        session.add(source)
        await session.flush()
    job = ScrapingJob(user_id=uid, source_id=source.id, start_url="https://x/y",
                      mode="range", status="running", chapters_done=10)
    session.add(job)
    await session.commit()
    today = datetime.now(UTC).date()

    await roll_day(session, today)
    await session.commit()
    assert await _rolled(session, uid, UsageMetric.SCRAPE_CHAPTERS) == 10.0

    await session.execute(
        update(ScrapingJob).where(ScrapingJob.id == job.id)
        .values(chapters_done=25, status="complete")
    )
    await session.commit()
    await roll_day(session, today)  # the nightly window re-roll
    await session.commit()
    assert await _rolled(session, uid, UsageMetric.SCRAPE_CHAPTERS) == 25.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rolled_equals_raw_aggregate(session: AsyncSession) -> None:
    """Backfill equivalence: rolled totals == the on-the-fly aggregate."""
    from app.modules.llm.repository import LlmRepository
    from app.modules.usage.repository import day_window

    uid = await _uid(session)
    session.add_all(
        [
            LlmExecution(user_id=uid, task="chat_tools", provider="gemini", model="m",
                         tokens_in=70, tokens_out=30, cost=0.3, latency_ms=1, status="ok"),
            LlmExecution(user_id=uid, task="summarize", provider="gemini", model="m",
                         tokens_in=20, tokens_out=10, cost=0.1, latency_ms=1, status="ok"),
        ]
    )
    await session.commit()
    today = datetime.now(UTC).date()
    await roll_day(session, today)
    await session.commit()

    start, end = day_window(today)
    raw = await LlmRepository(session).usage_summary_for_user(
        uid, period_start=start, period_end=end
    )
    rolled_in = await _rolled(session, uid, UsageMetric.LLM_TOKENS_IN)
    rolled_out = await _rolled(session, uid, UsageMetric.LLM_TOKENS_OUT)
    rolled_cost = await _rolled(session, uid, UsageMetric.LLM_COST_USD)
    assert (rolled_in, rolled_out) == (raw.tokens_in, raw.tokens_out)
    assert rolled_cost == pytest.approx(raw.total_cost)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/usage/test_rollup_builder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.modules.usage.rollup'`

- [ ] **Step 3: Implement `rollup.py`**

```python
# backend/app/modules/usage/rollup.py
"""Nightly usage rollup + backfill. The ONLY usage file importing domain modules.

Idempotent per day (delete + insert); the cron re-rolls a trailing window
because facts land late (running scrape jobs, next-day EPUB completions).
Raw tables stay the source of truth — this is a rebuildable cache (spec §6).

Runbook: after worker downtime longer than the window, run
    uv run python -m app.modules.usage.rollup <YYYY-MM-DD>
to backfill from that date (also the initial-deploy backfill).
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import UsageSettings, get_settings
from app.modules.downloads.service import DownloadService
from app.modules.imports.service import ImportService
from app.modules.llm.service import LlmService
from app.modules.runtime_config.service import RuntimeConfigService
from app.modules.scraping.service import ScrapingService
from app.modules.usage.repository import UsageRepository

logger = logging.getLogger(__name__)


async def roll_day(session: AsyncSession, day: date) -> None:
    """Collect every module's facts for one UTC day and replace that day."""
    settings = get_settings()
    llm = LlmService(session, settings)
    repo = UsageRepository(session)
    facts = [
        *await llm.daily_usage_facts(day),
        *await DownloadService(session).daily_usage_facts(day),
        *await ScrapingService(session).daily_usage_facts(day),
        *await ImportService(session).daily_usage_facts(day),
        *await repo.rejection_facts(day),
    ]
    await repo.replace_day(day, facts)
    await repo.replace_llm_day(
        day, await llm.daily_model_facts(day), await llm.daily_task_facts(day)
    )


async def _roll_range(session: AsyncSession, start: date, end: date) -> int:
    """Roll [start, end) one day at a time, committing per day."""
    rolled = 0
    day = start
    while day < end:
        await roll_day(session, day)
        await session.commit()
        rolled += 1
        day += timedelta(days=1)
    return rolled


async def roll_usage_window(_ctx: object) -> None:
    """arq cron: re-roll the trailing window (late facts converge, spec §6)."""
    from app.core.orm import import_all_models

    import_all_models()
    settings = get_settings()
    engine = create_async_engine(settings.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with factory() as session:
            effective = await RuntimeConfigService(session, settings).get_effective(
                UsageSettings
            )
            today = datetime.now(UTC).date()
            start = today - timedelta(days=effective.rollup_window_days)
            rolled = await _roll_range(session, start, today)
        logger.info("usage rollup complete", extra={"days": rolled})
    finally:
        await engine.dispose()


async def backfill(start: date) -> None:
    """Roll [start, today). Initial deploy + downtime recovery (see runbook)."""
    from app.core.orm import import_all_models

    import_all_models()
    settings = get_settings()
    engine = create_async_engine(settings.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with factory() as session:
            rolled = await _roll_range(session, start, datetime.now(UTC).date())
        logger.info("usage backfill complete", extra={"start": start.isoformat(), "days": rolled})
    finally:
        await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m app.modules.usage.rollup <YYYY-MM-DD>")
    asyncio.run(backfill(date.fromisoformat(sys.argv[1])))
```

- [ ] **Step 4: Register the cron**

In `backend/app/jobs/worker.py`: add `from app.modules.usage.rollup import roll_usage_window` and extend `cron_jobs`:

```python
    cron_jobs: ClassVar[list[object]] = [
        # Lazy purge also runs on list/create; cron keeps disk tidy if UI is idle.
        cron(cast(WorkerCoroutine, purge_expired_download_jobs), minute={0, 30}),
        # Nightly usage rollup: re-rolls the trailing window at 00:10 UTC.
        cron(cast(WorkerCoroutine, roll_usage_window), hour={0}, minute={10}),
    ]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/usage/test_rollup_builder.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add nightly usage rollup builder with backfill CLI\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 5: Hybrid quota-enforcement reads

**Files:**
- Modify: `backend/app/modules/orchestration/service.py` (`_check_llm_quota`)
- Modify: `backend/app/modules/downloads/service.py` (`_enforce_audio_chapters`)
- Modify: `backend/app/modules/scraping/service.py` (`_enforce_quota`)
- Modify: `backend/app/modules/imports/service.py` (`_enforce_quota`)
- Test: `backend/tests/usage/test_hybrid_enforcement.py`

**Interfaces:**
- Consumes: `UsageReadService.rolled_month_amount(user_id, kind, now)` + `hybrid_split(now)` (Task 1). The today-tail reuses each domain's **existing** meter method with a `[today 00:00 UTC, month end)` window — no new repo methods.
- Produces: identical quota outcomes with bounded reads. `storage_bytes` enforcement is untouched (live level meter).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/usage/test_hybrid_enforcement.py
"""Rolled days count toward quotas even with no raw rows (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from app.core.config import Settings, get_settings
from app.modules.books.schemas import BookCreate
from app.modules.chapters.service import ChapterService
from app.modules.downloads.schemas import DownloadCreate
from app.modules.downloads.service import DownloadService
from app.modules.library.service import LibraryService
from app.modules.llm.chat_service import ChatService
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.seed import seed_membership_policies
from app.modules.quotas.exceptions import QuotaExceededError
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
from app.modules.quotas.service import QuotaService
from app.modules.usage.kinds import UsageFact, UsageMetric
from app.modules.usage.models import UsageDaily
from app.modules.usage.repository import UsageRepository
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.factories import make_settings
from tests.llm.stream_fakes import stream_from_call


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        for model in (UsageDaily, MembershipQuota, MembershipPolicy):
            await db.execute(delete(model))
        await db.commit()
        await seed_membership_policies(db)
        yield db
        await db.rollback()
        for model in (UsageDaily, MembershipQuota, MembershipPolicy):
            await db.execute(delete(model))
        await db.commit()
        await seed_membership_policies(db)
    await engine.dispose()


async def _user(session: AsyncSession) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(username=f"hyb_{uuid4().hex[:8]}", password="test-pass-123")
    )


async def _set_quota(session: AsyncSession, kind: QuotaKind, limit: float) -> None:
    session.add(
        MembershipQuota(
            membership=Membership.FREE.value, quota_kind=kind.value, limit_value=limit
        )
    )
    await session.commit()


async def _seed_rolled_yesterday(
    session: AsyncSession, user_id: Any, metric: UsageMetric, amount: float
) -> None:
    """A rolled row for a PAST day of this month (no raw rows exist for it)."""
    now = datetime.now(UTC)
    month_start, _ = QuotaService.current_month_window(now)
    day = month_start.date()  # first of month: always < today unless day 1...
    if day == now.date():
        pytest.skip("first day of month: no closed days in the current month")
    await UsageRepository(session).replace_day(day, [UsageFact(user_id, metric, amount)])
    await session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chat_quota_counts_rolled_days(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(session)
    await _set_quota(session, QuotaKind.LLM_TOKENS, 100)
    await _seed_rolled_yesterday(session, user.id, UsageMetric.LLM_TOKENS_IN, 150.0)

    service = ChatService(
        session,
        make_settings(
            llm_enabled=True, gemini_api_key="test-key",
            llm_provider="gemini", llm_model="gemini-3.5-flash-lite",
        ),
    )

    async def _never(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("provider must not be called")

    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_never))
    events = [e async for e in service.stream_chat(user, "hi", None)]
    assert next(e for e in events if e.event == "error").data["code"] == "quota_exceeded"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audio_quota_counts_rolled_days(session: AsyncSession) -> None:
    user = await _user(session)
    book = await LibraryService(session).add_book(
        user.id, BookCreate(title="Hybrid", author="A", description="d")
    )
    await ChapterService(session).upsert_by_number(book.id, 1, "Ch 1", "text " * 50)
    await session.commit()
    await _set_quota(session, QuotaKind.AUDIO_CHAPTERS, 10)
    await _seed_rolled_yesterday(session, user.id, UsageMetric.AUDIO_CHAPTERS, 10.0)

    with pytest.raises(QuotaExceededError):
        await DownloadService(session).create(
            user.id, DownloadCreate(book_id=book.id, chapter_from=1, chapter_to=1)
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/usage/test_hybrid_enforcement.py -v`
Expected: FAIL — no error/exception raised (rolled rows are ignored by the raw-only meters).

- [ ] **Step 3: Switch the four enforcement helpers to hybrid**

Pattern — rolled part from `UsageReadService`, tail from the module's own existing meter with a `[today_start, month_end)` window. Orchestration (`_check_llm_quota` from Part B Task 3 becomes):

```python
    async def _check_llm_quota(self, user: UserRead) -> None:
        """Reject the turn BEFORE any provider call when a monthly LLM quota is hit.

        Hybrid read (usage spec §7): closed days from usage_daily, today live
        from llm_executions. Resume-confirm still never re-checks.
        """
        quotas = QuotaService(self._session)
        limits = await quotas.limits_for(user)
        if not limits.any_limited(QuotaKind.LLM_TOKENS, QuotaKind.LLM_COST_USD):
            return
        now = datetime.now(UTC)
        _, end = QuotaService.current_month_window(now)
        _, today_start = UsageReadService.hybrid_split(now)
        usage = UsageReadService(self._session)
        summary = await self._llm.usage_summary(
            user.id, period_start=today_start, period_end=end
        )
        tokens = (
            await usage.rolled_month_amount(user.id, QuotaKind.LLM_TOKENS, now)
            + summary.tokens_in
            + summary.tokens_out
        )
        QuotaService.enforce(QuotaKind.LLM_TOKENS, tokens, limits, resets_at=end, user_id=user.id)
        cost = (
            await usage.rolled_month_amount(user.id, QuotaKind.LLM_COST_USD, now)
            + summary.total_cost
        )
        QuotaService.enforce(QuotaKind.LLM_COST_USD, cost, limits, resets_at=end, user_id=user.id)
```

Downloads (`_enforce_audio_chapters` from Part C Task 1 becomes; add the `UsageReadService` import):

```python
    async def _enforce_audio_chapters(self, user_id: UUID, limits: QuotaLimits) -> None:
        now = datetime.now(UTC)
        _, end = QuotaService.current_month_window(now)
        _, today_start = UsageReadService.hybrid_split(now)
        rolled = await UsageReadService(self._session).rolled_month_amount(
            user_id, QuotaKind.AUDIO_CHAPTERS, now
        )
        tail = await self._repo.chapters_in_period(
            user_id, period_start=today_start, period_end=end
        )
        QuotaService.enforce(
            QuotaKind.AUDIO_CHAPTERS, rolled + tail, limits, resets_at=end, user_id=user_id
        )
```

Scraping and imports: same transformation of their `_enforce_quota` helpers — `rolled_month_amount(user_id, <kind>, now)` plus their existing meter (`chapters_in_period` / `completed_in_period`) called with `period_start=today_start, period_end=end`. The `storage_bytes` branch in downloads is untouched.

- [ ] **Step 4: Run the new tests AND every existing quota suite**

Run: `uv run pytest tests/usage/test_hybrid_enforcement.py tests/orchestration/test_monthly_quota_enforcement.py tests/quotas/ -v`
Expected: ALL PASS — the Part B/C suites seed raw rows created "now" (today), which the tail path serves; identical outcomes prove behavior is unchanged (spec §10.6).

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: switch quota enforcement to hybrid rolled-plus-today reads\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 6: Admin usage endpoints on hybrid reads

**Files:**
- Modify: `backend/app/modules/admin/usage_router.py` (summary + by-user compose hybrid)
- Modify: `backend/app/modules/llm/service.py` (no changes to existing methods — they serve the today-tail with a today window)
- Test: `backend/tests/usage/test_admin_usage_hybrid.py`

**Interfaces:**
- Consumes: `UsageRepository.rolled_user_table/rolled_totals/rolled_model_rows/rolled_task_rows` via `UsageReadService` — add thin passthroughs on `UsageReadService`: `rolled_user_table(*, start_day, end_day)`, `rolled_totals(metrics, *, start_day, end_day)`, `rolled_model_rows(*, start_day, end_day)`, `rolled_task_rows(*, start_day, end_day)` (same signatures as the repository). Existing raw aggregates (`usage_totals_admin`, `usage_by_user_admin`, `usage_by_model_admin`, `usage_by_task_admin`) serve the today-overlap tail.
- Produces: `GET /api/admin/usage/summary` and `/by-user` responses unchanged in shape; reads become bounded (rolled rows for closed days + one-day raw scans). `/executions` stays raw. Range semantics: for `[from, to)`, the rolled part covers `[from_day, min(to_day, today))`, the raw tail covers `[max(from, today_start), to)` when that interval is non-empty. **By-user pagination note:** merging rolled + tail happens in Python, then sort by cost desc and slice — bounded by users *active in the range*, not by history length; the tail sub-query uses `limit=10_000` (today's active users, far above real counts — documented).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/usage/test_admin_usage_hybrid.py
"""Admin summary/by-user = rolled closed days + live today (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from app.core.config import get_settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.llm.models import LlmExecution
from app.modules.usage.kinds import LlmModelFact, LlmTaskFact, UsageFact, UsageMetric
from app.modules.usage.models import LlmModelDaily, LlmTaskDaily, UsageDaily
from app.modules.usage.repository import UsageRepository
from app.modules.users.models import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.dbcleanup import clear_users

_HOST = "test.local"


def _make_db_override(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[], AsyncIterator[AsyncSession]]:
    async def _override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return _override_db


async def _clean(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        for model in (UsageDaily, LlmModelDaily, LlmTaskDaily, LlmExecution):
            await session.execute(delete(model))
        await session.commit()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await _clean(session_factory)
    async with engine.begin() as conn:
        await clear_users(conn)
    app.dependency_overrides[get_db] = _make_db_override(session_factory)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=f"http://{_HOST}") as http:
        yield http
    app.dependency_overrides.clear()
    await _clean(session_factory)
    async with engine.begin() as conn:
        await clear_users(conn)
    await engine.dispose()


async def _seed() -> UUID:
    """Admin; reader with 100/40 tokens rolled YESTERDAY + 10/5 raw TODAY."""
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        admin = User(username="hyb-admin", email="hyb-admin@example.com",
                     password_hash=None, google_sub="hyb-admin-sub", is_admin=True)
        reader = User(username="hyb-reader", email="hyb-reader@example.com",
                      password_hash=None, google_sub="hyb-reader-sub", is_admin=False)
        session.add_all([admin, reader])
        await session.flush()
        yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
        repo = UsageRepository(session)
        await repo.replace_day(
            yesterday,
            [
                UsageFact(reader.id, UsageMetric.LLM_TOKENS_IN, 100.0),
                UsageFact(reader.id, UsageMetric.LLM_TOKENS_OUT, 40.0),
                UsageFact(reader.id, UsageMetric.LLM_COST_USD, 0.5),
                UsageFact(reader.id, UsageMetric.LLM_EXECUTIONS, 2.0),
            ],
        )
        await repo.replace_llm_day(
            yesterday,
            [LlmModelFact("gemini", "m1", 100, 40, 0.5, 2)],
            [LlmTaskFact("chat_tools", 100, 40, 0.5, 2)],
        )
        session.add(
            LlmExecution(user_id=reader.id, task="chat_tools", provider="gemini",
                         model="m1", tokens_in=10, tokens_out=5, cost=0.1,
                         latency_ms=1, status="ok")
        )
        await session.commit()
        admin_id = admin.id
    await engine.dispose()
    return admin_id


@pytest.mark.integration
async def test_summary_and_by_user_combine_rolled_and_today(
    client: AsyncClient,
) -> None:
    admin_id = await _seed()
    token = create_access_token(
        user_id=admin_id, username="hyb-admin", settings=get_settings()
    )
    client.cookies.set(COOKIE_NAME, token, domain=_HOST, path="/")
    now = datetime.now(UTC)
    frm = (now - timedelta(days=3)).strftime("%Y-%m-%dT00:00:00Z")
    to = (now + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")

    summary = (await client.get(f"/api/admin/usage/summary?from={frm}&to={to}")).json()
    assert summary["tokens_in"] == 110  # 100 rolled + 10 today
    assert summary["tokens_out"] == 45
    assert summary["total_cost"] == pytest.approx(0.6)
    m1 = next(m for m in summary["by_model"] if m["model"] == "m1")
    assert m1["tokens_in"] == 110

    by_user = (await client.get(f"/api/admin/usage/by-user?from={frm}&to={to}")).json()
    reader_row = next(r for r in by_user["items"] if r["username"] == "hyb-reader")
    assert reader_row["tokens_in"] == 110
    assert reader_row["execution_count"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/usage/test_admin_usage_hybrid.py -v`
Expected: FAIL — `tokens_in == 10` (rolled rows invisible to the raw-only endpoints).

- [ ] **Step 3: Add `UsageReadService` passthroughs and the hybrid composition**

Append to `UsageReadService` (each a one-line delegation to `self._repo` with identical signature): `rolled_user_table`, `rolled_totals`, `rolled_model_rows`, `rolled_task_rows`.

Rewrite the composition in `backend/app/modules/admin/usage_router.py`. Add a range-split helper and hybrid builders (imports: `date`-related, `UsageReadService`, `UsageMetric`, `LlmModelFact`/`LlmTaskFact`, existing schemas):

```python
def _split_range(period: PeriodParams) -> tuple[date, date, datetime | None, datetime]:
    """(rolled_start_day, rolled_end_day, tail_start | None, tail_end).

    Rolled covers [from_day, min(to_day, today)); the raw tail covers the
    overlap of the range with [today 00:00 UTC, to) — None when the range
    ends before today.
    """
    today, today_start = UsageReadService.hybrid_split(datetime.now(UTC))
    rolled_start = period.period_start.astimezone(UTC).date()
    rolled_end = min(period.period_end.astimezone(UTC).date(), today)
    tail_start = max(period.period_start, today_start)
    if tail_start >= period.period_end:
        return rolled_start, rolled_end, None, period.period_end
    return rolled_start, rolled_end, tail_start, period.period_end
```

Module-level metric map and by-user merge:

```python
_LLM_USER_METRICS: dict[str, UsageMetric] = {
    "tokens_in": UsageMetric.LLM_TOKENS_IN,
    "tokens_out": UsageMetric.LLM_TOKENS_OUT,
    "total_cost": UsageMetric.LLM_COST_USD,
    "execution_count": UsageMetric.LLM_EXECUTIONS,
}


async def _merged_user_rows(
    session: AsyncSession, service: LlmService, period: PeriodParams
) -> list[UserUsageRead]:
    """Rolled per-user LLM sums + live today tail, cost-desc."""
    rolled_start, rolled_end, tail_start, tail_end = _split_range(period)
    rolled = await UsageReadService(session).rolled_user_table(
        start_day=rolled_start, end_day=rolled_end
    )
    merged: dict[UUID, dict[str, float]] = {
        uid: {field: metrics.get(m, 0.0) for field, m in _LLM_USER_METRICS.items()}
        for uid, metrics in rolled.items()
    }
    if tail_start is not None:
        # limit=10_000 >> any realistic count of users active TODAY (documented).
        tail_rows, _ = await service.usage_by_user_admin(
            period_start=tail_start, period_end=tail_end, limit=10_000, offset=0
        )
        for row in tail_rows:
            entry = merged.setdefault(row.user_id, dict.fromkeys(_LLM_USER_METRICS, 0.0))
            entry["tokens_in"] += row.tokens_in
            entry["tokens_out"] += row.tokens_out
            entry["total_cost"] += row.total_cost
            entry["execution_count"] += row.execution_count
    rows = [
        UserUsageRead(
            user_id=uid,
            tokens_in=int(v["tokens_in"]),
            tokens_out=int(v["tokens_out"]),
            total_cost=v["total_cost"],
            execution_count=int(v["execution_count"]),
        )
        for uid, v in merged.items()
    ]
    rows.sort(key=lambda r: r.total_cost, reverse=True)
    return rows
```

`usage_by_user` route body becomes (pagination moves into Python — bounded by users *active in the range*, not history; `_decorate_rows` from Part B/C is reused unchanged on the page slice):

```python
    rows = await _merged_user_rows(session, service, period)
    total = len(rows)
    page_rows = rows[page.offset : page.offset + page.limit]
    items = await _decorate_rows(session, service, page_rows)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)
```

Summary + breakdown merges (`LlmModelFact.cost_usd` maps to the schemas' `total_cost`; `executions` to `execution_count`):

```python
async def _merged_models(
    usage: UsageReadService,
    tail: AdminUsageOverview | None,
    *,
    start_day: date,
    end_day: date,
) -> list[ModelUsageRead]:
    merged: dict[tuple[str, str], ModelUsageRead] = {
        (m.provider, m.model): ModelUsageRead(
            provider=m.provider,
            model=m.model,
            tokens_in=m.tokens_in,
            tokens_out=m.tokens_out,
            total_cost=m.cost_usd,
            execution_count=m.executions,
        )
        for m in await usage.rolled_model_rows(start_day=start_day, end_day=end_day)
    }
    for row in tail.by_model if tail else []:
        base = merged.get((row.provider, row.model))
        merged[(row.provider, row.model)] = ModelUsageRead(
            provider=row.provider,
            model=row.model,
            tokens_in=row.tokens_in + (base.tokens_in if base else 0),
            tokens_out=row.tokens_out + (base.tokens_out if base else 0),
            total_cost=row.total_cost + (base.total_cost if base else 0.0),
            execution_count=row.execution_count + (base.execution_count if base else 0),
        )
    return sorted(merged.values(), key=lambda m: m.total_cost, reverse=True)
```

`_merged_tasks` is the same shape over `rolled_task_rows` / `tail.by_task` keyed by `task`, producing `TaskUsageRead`. The `usage_summary` route body:

```python
    rolled_start, rolled_end, tail_start, tail_end = _split_range(period)
    usage = UsageReadService(session)
    totals = await usage.rolled_totals(
        tuple(_LLM_USER_METRICS.values()), start_day=rolled_start, end_day=rolled_end
    )
    tail = (
        await service.usage_overview_admin(period_start=tail_start, period_end=tail_end)
        if tail_start is not None
        else None
    )
    return AdminUsageOverview(
        period_start=period.period_start,
        period_end=period.period_end,
        tokens_in=int(totals.get(UsageMetric.LLM_TOKENS_IN, 0.0)) + (tail.tokens_in if tail else 0),
        tokens_out=int(totals.get(UsageMetric.LLM_TOKENS_OUT, 0.0)) + (tail.tokens_out if tail else 0),
        total_cost=totals.get(UsageMetric.LLM_COST_USD, 0.0) + (tail.total_cost if tail else 0.0),
        execution_count=int(totals.get(UsageMetric.LLM_EXECUTIONS, 0.0)) + (tail.execution_count if tail else 0),
        by_model=await _merged_models(usage, tail, start_day=rolled_start, end_day=rolled_end),
        by_task=await _merged_tasks(usage, tail, start_day=rolled_start, end_day=rolled_end),
    )
```

(If the route body exceeds the ≤20-statement ruff limit, extract it as `_merged_overview(session, service, period)` and have the route return its result.)

`/executions` route: untouched.

- [ ] **Step 4: Run the new test AND the existing admin usage suites**

Run: `uv run pytest tests/usage/test_admin_usage_hybrid.py tests/quotas/test_admin_usage_quota_api.py -v`
Expected: ALL PASS (the Part B/C admin test seeds today-only raw rows → pure-tail path, same results as before).

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: serve admin usage endpoints from hybrid rollup reads\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

**Deploy note (runbook):** after this plan ships, run the initial backfill once per environment: `uv run python -m app.modules.usage.rollup <first-activity-date>` (any date at or before the oldest `llm_executions.created_at` is safe — empty days produce no rows).
