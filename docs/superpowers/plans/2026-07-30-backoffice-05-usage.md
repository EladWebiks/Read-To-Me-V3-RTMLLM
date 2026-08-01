# Backoffice 05 — AI Usage & Cost Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cross-user AI usage/cost visibility: global totals with by-model/by-task breakdowns, per-user aggregates with usernames, and a recent-executions table over a `[from, to)` date range. Stat tiles + tables — no chart library.

**Architecture:** Aggregates live in the llm module (`LlmRepository` GROUP BYs over `llm_executions`, `LlmService` admin methods); `modules/admin/usage_router.py` composes per-user rows with usernames from `UserService.usernames_for_ids` (added here — the users module owns the query). Frontend screen composes foundation primitives plus new `StatTile`/`DateRangeField`.

**Tech Stack:** FastAPI, SQLAlchemy async, pydantic v2, pytest; React 19, react-query, vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-07-30-backoffice-mvp-design.md`. **Depends on:** `2026-07-30-backoffice-01-foundation.md` (Page/PageParams/PeriodParams, aggregator, test harness, pagination primitives).

## Global Constraints

- Backend gates per task (run from `backend/`): `uv run ruff check . --fix && uv run ruff format .`, `uv run mypy .`, `uv run pytest -m "unit or integration"`. Integration tests need Postgres/Redis/MinIO and `TEST_DATABASE_URL` pointing at a separate test DB.
- Frontend gates per task (run from `frontend/`): `npm run lint`, `npm run build`, `npm run test`.
- Commit with `bash scripts/git-commit-clean.sh /tmp/msg.txt`. **Never** add attribution trailers. Verify with `git log -1 --format=%B`.
- Ruff limits: complexity ≤10, statements ≤20, branches ≤6, args ≤6. ESLint limits: file ≤110 lines, function ≤60, nesting ≤3 (tests/barrels exempt).
- Aggregates read `llm_executions` only (it carries provider/model/task/cost per row). The existing ownership-scoped `usage_summary` stays untouched.
- Every new route registers in `backend/tests/admin/test_authz_matrix.py::ROUTES`.
- Responses contain aggregates and metadata — never prompt/content text. No Alembic migrations.

---

### Task 1: Usage aggregates API

**Files:**
- Modify: `backend/app/modules/llm/repository.py`
- Modify: `backend/app/modules/llm/schemas.py`
- Modify: `backend/app/modules/llm/service.py`
- Modify: `backend/app/modules/users/repository.py`
- Modify: `backend/app/modules/users/service.py`
- Modify: `backend/app/modules/admin/schemas.py`
- Create: `backend/app/modules/admin/usage_router.py`
- Modify: `backend/app/modules/admin/router.py`
- Modify: `backend/tests/admin/helpers.py`
- Modify: `backend/tests/admin/test_authz_matrix.py`
- Test: `backend/tests/admin/test_usage_admin_api.py`

**Interfaces:**
- Consumes: `LlmExecution` model, `UsageTotals` dataclass; foundation's `Page`/`PageParams`/`PeriodParams` and test harness.
- Produces:
  - llm schemas: `UsageBreakdownRead` (`tokens_in: int`, `tokens_out: int`, `total_cost: float`, `execution_count: int`), `ModelUsageRead(UsageBreakdownRead)` (+`provider`, `model`), `TaskUsageRead(UsageBreakdownRead)` (+`task`), `UserUsageRead(UsageBreakdownRead)` (+`user_id: UUID`), `AdminUsageOverview` (period + totals + `by_model`/`by_task`), `LlmExecutionRead` (from_attributes row).
  - `LlmService.usage_overview_admin(*, period_start, period_end) -> AdminUsageOverview`
  - `LlmService.usage_by_user_admin(*, period_start, period_end, limit, offset) -> tuple[list[UserUsageRead], int]`
  - `LlmService.list_executions_admin(*, period_start, period_end, limit, offset) -> tuple[list[LlmExecutionRead], int]`
  - `UserService.usernames_for_ids(user_ids: list[UUID]) -> dict[UUID, str]` (soft-deleted included).
  - admin schema `AdminUserUsageRead(UserUsageRead)` with `username: str | None = None`.
  - Routes `GET /api/admin/usage/summary`, `/api/admin/usage/by-user`, `/api/admin/usage/executions` (`from`/`to` required; used by Task 2's screen).
  - Test helper `seed_execution(...)` in `tests/admin/helpers.py`.

- [ ] **Step 1: Add the seeding helper**

Append to `backend/tests/admin/helpers.py` (extend imports with `from app.modules.llm.models import LlmExecution`):

```python
async def seed_execution(  # noqa: PLR0913 — test seeding needs the full column set
    user_id: UUID,
    *,
    created_at: datetime,
    task: str = "chat",
    provider: str = "gemini",
    model: str = "gemini-3.5-flash",
    tokens_in: int = 100,
    tokens_out: int = 10,
    cost: float = 0.5,
) -> None:
    """Insert one llm_execution row with an explicit timestamp."""
    async with seed_session() as session:
        session.add(
            LlmExecution(
                user_id=user_id,
                task=task,
                provider=provider,
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost=cost,
                latency_ms=100,
                status="ok",
                created_at=created_at,
            )
        )
```

(Drop the `# noqa` if ruff does not flag it.)

- [ ] **Step 2: Write the failing tests**

```python
# backend/tests/admin/test_usage_admin_api.py
"""Backoffice usage/cost aggregates against seeded rows (needs Postgres)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import AsyncClient

from tests.admin.helpers import create_user, login, seed_execution

FROM = datetime(2026, 7, 1, tzinfo=UTC)
TO = datetime(2026, 8, 1, tzinfo=UTC)
PERIOD = {"from": "2026-07-01T00:00:00Z", "to": "2026-08-01T00:00:00Z"}


@pytest.fixture
async def admin(client: AsyncClient) -> UUID:
    user_id = await create_user("boss", is_admin=True)
    login(client, user_id, "boss")
    return user_id


@pytest.fixture
async def seeded(admin: UUID) -> tuple[UUID, UUID]:
    """Known sums: alice 300/30 tokens $0.75 (2 execs), bob 400/40 $1.00 (1 exec).

    A row exactly at `from` is included; a row exactly at `to` is excluded.
    """
    alice = await create_user("alice")
    bob = await create_user("bob")
    await seed_execution(
        alice, created_at=FROM, model="m1", task="chat", tokens_in=100, tokens_out=10, cost=0.5
    )
    await seed_execution(
        alice,
        created_at=datetime(2026, 7, 20, tzinfo=UTC),
        model="m2",
        task="summarize",
        tokens_in=200,
        tokens_out=20,
        cost=0.25,
    )
    await seed_execution(
        bob,
        created_at=datetime(2026, 7, 30, tzinfo=UTC),
        model="m1",
        task="chat",
        tokens_in=400,
        tokens_out=40,
        cost=1.0,
    )
    await seed_execution(
        bob, created_at=TO, model="m1", task="chat", tokens_in=999, tokens_out=999, cost=9.9
    )
    return alice, bob


@pytest.mark.integration
async def test_summary_totals_and_breakdowns(
    client: AsyncClient, seeded: tuple[UUID, UUID]
) -> None:
    response = await client.get("/api/admin/usage/summary", params=PERIOD)
    assert response.status_code == 200
    payload = response.json()
    assert payload["tokens_in"] == 700
    assert payload["tokens_out"] == 70
    assert payload["total_cost"] == pytest.approx(1.75)
    assert payload["execution_count"] == 3
    by_model = {row["model"]: row for row in payload["by_model"]}
    assert by_model["m1"]["tokens_in"] == 500
    assert by_model["m1"]["execution_count"] == 2
    assert by_model["m2"]["total_cost"] == pytest.approx(0.25)
    assert payload["by_model"][0]["model"] == "m1"  # ordered by cost desc
    by_task = {row["task"]: row for row in payload["by_task"]}
    assert by_task["chat"]["tokens_in"] == 500
    assert by_task["summarize"]["execution_count"] == 1


@pytest.mark.integration
async def test_by_user_rows_with_usernames(
    client: AsyncClient, seeded: tuple[UUID, UUID]
) -> None:
    alice, bob = seeded
    response = await client.get("/api/admin/usage/by-user", params=PERIOD)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    first = payload["items"][0]  # ordered by cost desc → bob first
    assert first["user_id"] == str(bob)
    assert first["username"] == "bob"
    assert first["total_cost"] == pytest.approx(1.0)
    second = payload["items"][1]
    assert second["user_id"] == str(alice)
    assert second["tokens_in"] == 300
    assert second["execution_count"] == 2


@pytest.mark.integration
async def test_by_user_pagination(client: AsyncClient, seeded: tuple[UUID, UUID]) -> None:
    response = await client.get(
        "/api/admin/usage/by-user", params={**PERIOD, "limit": 1, "offset": 0}
    )
    payload = response.json()
    assert payload["total"] == 2
    assert len(payload["items"]) == 1


@pytest.mark.integration
async def test_recent_executions(client: AsyncClient, seeded: tuple[UUID, UUID]) -> None:
    response = await client.get("/api/admin/usage/executions", params=PERIOD)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    newest = payload["items"][0]
    assert newest["model"] == "m1"
    assert newest["tokens_in"] == 400
    assert newest["status"] == "ok"
```

Append to `ROUTES` in `backend/tests/admin/test_authz_matrix.py`:

```python
    ("GET", "/api/admin/usage/summary?from=2026-07-01T00:00:00Z&to=2026-08-01T00:00:00Z", None),
    ("GET", "/api/admin/usage/by-user?from=2026-07-01T00:00:00Z&to=2026-08-01T00:00:00Z", None),
    ("GET", "/api/admin/usage/executions?from=2026-07-01T00:00:00Z&to=2026-08-01T00:00:00Z", None),
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/admin/test_usage_admin_api.py -v`
Expected: FAIL with 404 (routes missing).

- [ ] **Step 4: Add repository aggregates (llm module)**

Append the dataclasses next to `UsageTotals` in `backend/app/modules/llm/repository.py` (extend imports with `from sqlalchemy import ColumnElement, and_`):

```python
@dataclass(frozen=True, slots=True)
class ModelUsageRow:
    """Cross-user aggregate for one (provider, model)."""

    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    total_cost: float
    execution_count: int


@dataclass(frozen=True, slots=True)
class TaskUsageRow:
    """Cross-user aggregate for one task."""

    task: str
    tokens_in: int
    tokens_out: int
    total_cost: float
    execution_count: int


@dataclass(frozen=True, slots=True)
class UserUsageRow:
    """Aggregate for one user over a period."""

    user_id: uuid.UUID
    tokens_in: int
    tokens_out: int
    total_cost: float
    execution_count: int
```

Append the methods to `LlmRepository`:

```python
    @staticmethod
    def _in_period(period_start: datetime, period_end: datetime) -> ColumnElement[bool]:
        return and_(
            LlmExecution.created_at >= period_start,
            LlmExecution.created_at < period_end,
        )

    @staticmethod
    def _usage_sums() -> tuple[Any, ...]:
        return (
            func.coalesce(func.sum(LlmExecution.tokens_in), 0),
            func.coalesce(func.sum(LlmExecution.tokens_out), 0),
            func.coalesce(func.sum(LlmExecution.cost), 0.0),
            func.count(LlmExecution.id),
        )

    async def usage_totals_admin(
        self, *, period_start: datetime, period_end: datetime
    ) -> UsageTotals:
        """Cross-user totals over [period_start, period_end)."""
        result = await self._session.execute(
            select(*self._usage_sums()).where(self._in_period(period_start, period_end))
        )
        tokens_in, tokens_out, total_cost, count = result.one()
        return UsageTotals(
            tokens_in=int(tokens_in),
            tokens_out=int(tokens_out),
            total_cost=float(total_cost),
            execution_count=int(count),
        )

    async def usage_by_model_admin(
        self, *, period_start: datetime, period_end: datetime
    ) -> list[ModelUsageRow]:
        """Cross-user aggregates grouped by (provider, model), cost-desc."""
        stmt = (
            select(LlmExecution.provider, LlmExecution.model, *self._usage_sums())
            .where(self._in_period(period_start, period_end))
            .group_by(LlmExecution.provider, LlmExecution.model)
            .order_by(func.coalesce(func.sum(LlmExecution.cost), 0.0).desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            ModelUsageRow(
                provider=row[0],
                model=row[1],
                tokens_in=int(row[2]),
                tokens_out=int(row[3]),
                total_cost=float(row[4]),
                execution_count=int(row[5]),
            )
            for row in rows
        ]

    async def usage_by_task_admin(
        self, *, period_start: datetime, period_end: datetime
    ) -> list[TaskUsageRow]:
        """Cross-user aggregates grouped by task, cost-desc."""
        stmt = (
            select(LlmExecution.task, *self._usage_sums())
            .where(self._in_period(period_start, period_end))
            .group_by(LlmExecution.task)
            .order_by(func.coalesce(func.sum(LlmExecution.cost), 0.0).desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            TaskUsageRow(
                task=row[0],
                tokens_in=int(row[1]),
                tokens_out=int(row[2]),
                total_cost=float(row[3]),
                execution_count=int(row[4]),
            )
            for row in rows
        ]

    async def usage_by_user_admin(
        self, *, period_start: datetime, period_end: datetime, limit: int, offset: int
    ) -> tuple[list[UserUsageRow], int]:
        """Per-user aggregates, cost-desc, with total distinct-user count."""
        condition = self._in_period(period_start, period_end)
        total_stmt = select(func.count(func.distinct(LlmExecution.user_id))).where(condition)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(LlmExecution.user_id, *self._usage_sums())
            .where(condition)
            .group_by(LlmExecution.user_id)
            .order_by(func.coalesce(func.sum(LlmExecution.cost), 0.0).desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).all()
        items = [
            UserUsageRow(
                user_id=row[0],
                tokens_in=int(row[1]),
                tokens_out=int(row[2]),
                total_cost=float(row[3]),
                execution_count=int(row[4]),
            )
            for row in rows
        ]
        return items, total

    async def list_executions_admin(
        self, *, period_start: datetime, period_end: datetime, limit: int, offset: int
    ) -> tuple[list[LlmExecution], int]:
        """Cross-user execution rows, newest first."""
        condition = self._in_period(period_start, period_end)
        total_stmt = select(func.count()).select_from(LlmExecution).where(condition)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(LlmExecution)
            .where(condition)
            .order_by(LlmExecution.created_at.desc(), LlmExecution.id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows), total
```

- [ ] **Step 5: Add llm schemas + service methods**

Append to `backend/app/modules/llm/schemas.py` (ensure `ConfigDict` is in the pydantic import):

```python
class UsageBreakdownRead(BaseModel):
    """Shared aggregate fields for admin usage buckets."""

    tokens_in: int
    tokens_out: int
    total_cost: float
    execution_count: int


class ModelUsageRead(UsageBreakdownRead):
    """Cross-user aggregate for one (provider, model)."""

    provider: str
    model: str


class TaskUsageRead(UsageBreakdownRead):
    """Cross-user aggregate for one task."""

    task: str


class UserUsageRead(UsageBreakdownRead):
    """Aggregate for one user over the period."""

    user_id: UUID


class AdminUsageOverview(UsageBreakdownRead):
    """GET /api/admin/usage/summary payload."""

    period_start: datetime
    period_end: datetime
    by_model: list[ModelUsageRead] = Field(default_factory=list)
    by_task: list[TaskUsageRead] = Field(default_factory=list)


class LlmExecutionRead(BaseModel):
    """One llm_execution row for the backoffice recent-executions table."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    conversation_id: UUID | None
    task: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost: float
    latency_ms: int
    status: str
    fallback_used: bool
    error: str | None
    created_at: datetime
```

Append to `LlmService` in `backend/app/modules/llm/service.py` (add `from dataclasses import asdict` and extend the schemas import with `AdminUsageOverview`, `LlmExecutionRead`, `ModelUsageRead`, `TaskUsageRead`, `UserUsageRead`):

```python
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
```

- [ ] **Step 6: Add `usernames_for_ids` (users module)**

Append to `UserRepository` in `backend/app/modules/users/repository.py` (add `from collections.abc import Sequence` to the imports):

```python
    async def usernames_for_ids(self, user_ids: Sequence[UUID]) -> dict[UUID, str]:
        """Map ids → usernames, soft-deleted included (backoffice attribution)."""
        if not user_ids:
            return {}
        stmt = select(User.id, User.username).where(User.id.in_(user_ids))
        rows = (await self._session.execute(stmt)).all()
        return {row[0]: row[1] for row in rows}
```

Append to `UserService` in `backend/app/modules/users/service.py`:

```python
    async def usernames_for_ids(self, user_ids: list[UUID]) -> dict[UUID, str]:
        """Backoffice attribution: ids → usernames, soft-deleted included."""
        return await self._repo.usernames_for_ids(user_ids)
```

- [ ] **Step 7: Add the composed admin schema and usage router**

Append to `backend/app/modules/admin/schemas.py` (add `from app.modules.llm.schemas import UserUsageRead` to imports):

```python
class AdminUserUsageRead(UserUsageRead):
    """Per-user usage row + username resolved by the admin router."""

    username: str | None = None
```

```python
# backend/app/modules/admin/usage_router.py
"""Backoffice AI usage/cost routes. HTTP only; aggregates live in LlmService."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.deps import get_db, require_admin
from app.modules.admin.params import PageParams, PeriodParams
from app.modules.admin.schemas import AdminUserUsageRead, Page
from app.modules.llm.schemas import AdminUsageOverview, LlmExecutionRead
from app.modules.llm.service import LlmService
from app.modules.users.schemas import UserRead
from app.modules.users.service import UserService

router = APIRouter(prefix="/usage")


def _llm(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LlmService:
    return LlmService(session, settings)


@router.get("/summary")
async def usage_summary(
    period: Annotated[PeriodParams, Depends()],
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[LlmService, Depends(_llm)],
) -> AdminUsageOverview:
    """Global tokens/cost/executions with model and task breakdowns."""
    return await service.usage_overview_admin(
        period_start=period.period_start, period_end=period.period_end
    )


@router.get("/by-user")
async def usage_by_user(
    period: Annotated[PeriodParams, Depends()],
    page: Annotated[PageParams, Depends()],
    _admin: Annotated[UserRead, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[LlmService, Depends(_llm)],
) -> Page[AdminUserUsageRead]:
    """Per-user usage rows with usernames resolved via the users service."""
    rows, total = await service.usage_by_user_admin(
        period_start=period.period_start,
        period_end=period.period_end,
        limit=page.limit,
        offset=page.offset,
    )
    names = await UserService(session).usernames_for_ids([row.user_id for row in rows])
    items = [
        AdminUserUsageRead(username=names.get(row.user_id), **row.model_dump())
        for row in rows
    ]
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/executions")
async def recent_executions(
    period: Annotated[PeriodParams, Depends()],
    page: Annotated[PageParams, Depends()],
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[LlmService, Depends(_llm)],
) -> Page[LlmExecutionRead]:
    """Cross-user execution rows, newest first."""
    items, total = await service.list_executions_admin(
        period_start=period.period_start,
        period_end=period.period_end,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)
```

In `backend/app/modules/admin/router.py`, add:

```python
from app.modules.admin.usage_router import router as usage_router
```

and:

```python
router.include_router(usage_router)
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/admin -v`
Expected: PASS (4 usage tests; matrix includes the three usage routes)

- [ ] **Step 9: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add backoffice AI usage and cost aggregates API\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 2: Usage screen

**Files:**
- Create: `frontend/src/features/admin/logic/period.ts`
- Create: `frontend/src/features/admin/api/usage.ts`
- Create: `frontend/src/features/admin/hooks/useUsage.ts`
- Create: `frontend/src/features/admin/components/common/StatTile.tsx`
- Create: `frontend/src/features/admin/components/common/DateRangeField.tsx`
- Create: `frontend/src/features/admin/components/usage/UsagePage.tsx`
- Create: `frontend/src/features/admin/components/usage/UsageSummaryTiles.tsx`
- Create: `frontend/src/features/admin/components/usage/BreakdownTable.tsx`
- Create: `frontend/src/features/admin/components/usage/ByUserTable.tsx`
- Create: `frontend/src/features/admin/components/usage/ExecutionsTable.tsx`
- Modify: `frontend/src/features/admin/index.ts`
- Modify: `frontend/src/app/App.tsx` (swap the usage placeholder)
- Test: `frontend/src/features/admin/components/usage/UsagePage.test.tsx`

**Interfaces:**
- Consumes: Task 1 routes; foundation's `usePageState`/`PaginationControls`/`Page<T>`.
- Produces: `UsagePage` export; `StatTile`, `DateRangeField`, `Period` + `defaultPeriod()` (reusable by other screens' filters).

- [ ] **Step 1: Write the failing screen test**

```tsx
// frontend/src/features/admin/components/usage/UsagePage.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { UsagePage } from './UsagePage'
import {
  fetchExecutions,
  fetchUsageByUser,
  fetchUsageOverview,
} from '@/features/admin/api/usage'

vi.mock('@/features/admin/api/usage', () => ({
  fetchUsageOverview: vi.fn(),
  fetchUsageByUser: vi.fn(),
  fetchExecutions: vi.fn(),
}))

const BREAKDOWN = { tokens_in: 700, tokens_out: 70, total_cost: 1.75, execution_count: 3 }

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <UsagePage />
    </QueryClientProvider>,
  )
}

describe('UsagePage', () => {
  it('renders tiles, breakdowns, per-user rows, and executions', async () => {
    vi.mocked(fetchUsageOverview).mockResolvedValue({
      ...BREAKDOWN,
      period_start: '2026-07-01T00:00:00Z',
      period_end: '2026-08-01T00:00:00Z',
      by_model: [{ ...BREAKDOWN, provider: 'gemini', model: 'm1' }],
      by_task: [{ ...BREAKDOWN, task: 'chat' }],
    })
    vi.mocked(fetchUsageByUser).mockResolvedValue({
      items: [{ ...BREAKDOWN, user_id: 'u2', username: 'bob' }],
      total: 1,
      limit: 25,
      offset: 0,
    })
    vi.mocked(fetchExecutions).mockResolvedValue({
      items: [
        {
          id: 'e1',
          user_id: 'u2',
          conversation_id: null,
          task: 'chat',
          provider: 'gemini',
          model: 'm1',
          tokens_in: 400,
          tokens_out: 40,
          cost: 1,
          latency_ms: 120,
          status: 'ok',
          fallback_used: false,
          error: null,
          created_at: '2026-07-30T12:00:00Z',
        },
      ],
      total: 1,
      limit: 25,
      offset: 0,
    })
    renderPage()
    expect(await screen.findByText('700')).toBeTruthy()
    expect(screen.getByText('$1.7500')).toBeTruthy()
    expect(await screen.findByText('gemini/m1')).toBeTruthy()
    expect(await screen.findByText('bob')).toBeTruthy()
    expect((await screen.findAllByText('ok')).length).toBeGreaterThan(0)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- UsagePage`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement logic + API + hooks**

```typescript
// frontend/src/features/admin/logic/period.ts
export type Period = { from: string; to: string }

/** Default range: the last 30 days, as ISO strings. */
export function defaultPeriod(): Period {
  const to = new Date()
  const from = new Date(to.getTime() - 30 * 24 * 60 * 60 * 1000)
  return { from: from.toISOString(), to: to.toISOString() }
}

/** ISO → value for <input type="datetime-local"> (local time, minute precision). */
export function isoToLocal(iso: string): string {
  const date = new Date(iso)
  const pad = (part: number) => String(part).padStart(2, '0')
  const day = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
  return `${day}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function localToIso(local: string): string {
  return new Date(local).toISOString()
}
```

```typescript
// frontend/src/features/admin/api/usage.ts
import type { Page } from '@/features/admin/types'
import type { Period } from '@/features/admin/logic/period'
import { apiGet } from '@/shared/lib/api'

export type UsageBreakdown = {
  tokens_in: number
  tokens_out: number
  total_cost: number
  execution_count: number
}

export type ModelUsage = UsageBreakdown & { provider: string; model: string }
export type TaskUsage = UsageBreakdown & { task: string }
export type UserUsage = UsageBreakdown & { user_id: string; username: string | null }

export type UsageOverview = UsageBreakdown & {
  period_start: string
  period_end: string
  by_model: ModelUsage[]
  by_task: TaskUsage[]
}

export type LlmExecutionRow = {
  id: string
  user_id: string
  conversation_id: string | null
  task: string
  provider: string
  model: string
  tokens_in: number
  tokens_out: number
  cost: number
  latency_ms: number
  status: string
  fallback_used: boolean
  error: string | null
  created_at: string
}

function rangeQuery(period: Period): string {
  return `from=${encodeURIComponent(period.from)}&to=${encodeURIComponent(period.to)}`
}

export function fetchUsageOverview(period: Period): Promise<UsageOverview> {
  return apiGet(`/api/admin/usage/summary?${rangeQuery(period)}`)
}

export function fetchUsageByUser(
  period: Period,
  limit: number,
  offset: number,
): Promise<Page<UserUsage>> {
  return apiGet(`/api/admin/usage/by-user?${rangeQuery(period)}&limit=${limit}&offset=${offset}`)
}

export function fetchExecutions(
  period: Period,
  limit: number,
  offset: number,
): Promise<Page<LlmExecutionRow>> {
  return apiGet(
    `/api/admin/usage/executions?${rangeQuery(period)}&limit=${limit}&offset=${offset}`,
  )
}
```

```typescript
// frontend/src/features/admin/hooks/useUsage.ts
import { useQuery } from '@tanstack/react-query'
import {
  fetchExecutions,
  fetchUsageByUser,
  fetchUsageOverview,
} from '@/features/admin/api/usage'
import type { Period } from '@/features/admin/logic/period'

export function useUsageOverview(period: Period) {
  return useQuery({
    queryKey: ['admin', 'usage', 'summary', period],
    queryFn: () => fetchUsageOverview(period),
  })
}

export function useUsageByUser(period: Period, limit: number, offset: number) {
  return useQuery({
    queryKey: ['admin', 'usage', 'by-user', period, limit, offset],
    queryFn: () => fetchUsageByUser(period, limit, offset),
  })
}

export function useExecutions(period: Period, limit: number, offset: number) {
  return useQuery({
    queryKey: ['admin', 'usage', 'executions', period, limit, offset],
    queryFn: () => fetchExecutions(period, limit, offset),
  })
}
```

- [ ] **Step 4: Implement common components**

```tsx
// frontend/src/features/admin/components/common/StatTile.tsx
export function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/70 bg-card px-4 py-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-xl font-semibold tabular-nums">{value}</p>
    </div>
  )
}
```

```tsx
// frontend/src/features/admin/components/common/DateRangeField.tsx
import { isoToLocal, localToIso, type Period } from '@/features/admin/logic/period'

const INPUT = 'rounded border border-border bg-background px-2 py-1'

export function DateRangeField({
  period,
  onChange,
}: {
  period: Period
  onChange: (period: Period) => void
}) {
  return (
    <div className="mb-4 flex flex-wrap items-end gap-2 text-sm">
      <label className="flex flex-col gap-1">
        <span className="text-xs text-muted-foreground">From</span>
        <input
          type="datetime-local"
          className={INPUT}
          value={isoToLocal(period.from)}
          onChange={(event) => onChange({ ...period, from: localToIso(event.target.value) })}
        />
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-xs text-muted-foreground">To (exclusive)</span>
        <input
          type="datetime-local"
          className={INPUT}
          value={isoToLocal(period.to)}
          onChange={(event) => onChange({ ...period, to: localToIso(event.target.value) })}
        />
      </label>
    </div>
  )
}
```

- [ ] **Step 5: Implement the usage components**

```tsx
// frontend/src/features/admin/components/usage/UsagePage.tsx
import { useState } from 'react'
import { DateRangeField } from '@/features/admin/components/common/DateRangeField'
import { defaultPeriod } from '@/features/admin/logic/period'
import { ByUserTable } from './ByUserTable'
import { ExecutionsTable } from './ExecutionsTable'
import { UsageSummaryTiles } from './UsageSummaryTiles'

export function UsagePage() {
  const [period, setPeriod] = useState(defaultPeriod)
  return (
    <section>
      <h1 className="mb-1 text-lg font-semibold">AI usage &amp; cost</h1>
      <DateRangeField period={period} onChange={setPeriod} />
      <UsageSummaryTiles period={period} />
      <ByUserTable period={period} />
      <ExecutionsTable period={period} />
    </section>
  )
}
```

```tsx
// frontend/src/features/admin/components/usage/UsageSummaryTiles.tsx
import { StatTile } from '@/features/admin/components/common/StatTile'
import { useUsageOverview } from '@/features/admin/hooks/useUsage'
import type { Period } from '@/features/admin/logic/period'
import { BreakdownTable } from './BreakdownTable'

export function UsageSummaryTiles({ period }: { period: Period }) {
  const { data, isLoading } = useUsageOverview(period)
  if (isLoading || !data) {
    return <p className="text-sm text-muted-foreground">Loading usage…</p>
  }
  return (
    <>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Tokens in" value={data.tokens_in.toLocaleString()} />
        <StatTile label="Tokens out" value={data.tokens_out.toLocaleString()} />
        <StatTile label="Cost (USD)" value={`$${data.total_cost.toFixed(4)}`} />
        <StatTile label="Executions" value={data.execution_count.toLocaleString()} />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <BreakdownTable
          title="By model"
          rows={data.by_model.map((row) => ({ ...row, label: `${row.provider}/${row.model}` }))}
        />
        <BreakdownTable
          title="By task"
          rows={data.by_task.map((row) => ({ ...row, label: row.task }))}
        />
      </div>
    </>
  )
}
```

```tsx
// frontend/src/features/admin/components/usage/BreakdownTable.tsx
import type { UsageBreakdown } from '@/features/admin/api/usage'

type Row = UsageBreakdown & { label: string }

export function BreakdownTable({ title, rows }: { title: string; rows: Row[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border/70">
      <p className="border-b border-border/60 px-3 py-1.5 text-sm font-medium">{title}</p>
      <table className="w-full text-left text-sm">
        <thead className="text-muted-foreground">
          <tr>
            <th className="px-3 py-1.5 font-medium">Bucket</th>
            <th className="px-3 py-1.5 font-medium">In</th>
            <th className="px-3 py-1.5 font-medium">Out</th>
            <th className="px-3 py-1.5 font-medium">Cost</th>
            <th className="px-3 py-1.5 font-medium">Execs</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-t border-border/50 tabular-nums">
              <td className="px-3 py-1.5 font-mono text-xs">{row.label}</td>
              <td className="px-3 py-1.5">{row.tokens_in.toLocaleString()}</td>
              <td className="px-3 py-1.5">{row.tokens_out.toLocaleString()}</td>
              <td className="px-3 py-1.5">${row.total_cost.toFixed(4)}</td>
              <td className="px-3 py-1.5">{row.execution_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

```tsx
// frontend/src/features/admin/components/usage/ByUserTable.tsx
import { PaginationControls } from '@/features/admin/components/common/PaginationControls'
import { usePageState } from '@/features/admin/hooks/usePageState'
import { useUsageByUser } from '@/features/admin/hooks/useUsage'
import type { Period } from '@/features/admin/logic/period'

export function ByUserTable({ period }: { period: Period }) {
  const page = usePageState(25)
  const { data } = useUsageByUser(period, page.limit, page.offset)
  if (!data) {
    return null
  }
  return (
    <div className="mt-4">
      <p className="mb-1 text-sm font-medium">By user</p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-muted-foreground">
            <tr>
              <th className="px-2 py-1.5 font-medium">User</th>
              <th className="px-2 py-1.5 font-medium">Tokens in</th>
              <th className="px-2 py-1.5 font-medium">Tokens out</th>
              <th className="px-2 py-1.5 font-medium">Cost</th>
              <th className="px-2 py-1.5 font-medium">Execs</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((row) => (
              <tr key={row.user_id} className="border-t border-border/60 tabular-nums">
                <td className="px-2 py-1.5">{row.username ?? row.user_id}</td>
                <td className="px-2 py-1.5">{row.tokens_in.toLocaleString()}</td>
                <td className="px-2 py-1.5">{row.tokens_out.toLocaleString()}</td>
                <td className="px-2 py-1.5">${row.total_cost.toFixed(4)}</td>
                <td className="px-2 py-1.5">{row.execution_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <PaginationControls
        total={data.total}
        limit={page.limit}
        offset={page.offset}
        onPrev={page.prev}
        onNext={() => page.next(data.total)}
      />
    </div>
  )
}
```

```tsx
// frontend/src/features/admin/components/usage/ExecutionsTable.tsx
import { PaginationControls } from '@/features/admin/components/common/PaginationControls'
import { useExecutions } from '@/features/admin/hooks/useUsage'
import { usePageState } from '@/features/admin/hooks/usePageState'
import type { Period } from '@/features/admin/logic/period'

export function ExecutionsTable({ period }: { period: Period }) {
  const page = usePageState(25)
  const { data } = useExecutions(period, page.limit, page.offset)
  if (!data) {
    return null
  }
  return (
    <div className="mt-4">
      <p className="mb-1 text-sm font-medium">Recent executions</p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-muted-foreground">
            <tr>
              <th className="px-2 py-1.5 font-medium">Time</th>
              <th className="px-2 py-1.5 font-medium">Task</th>
              <th className="px-2 py-1.5 font-medium">Model</th>
              <th className="px-2 py-1.5 font-medium">Tokens</th>
              <th className="px-2 py-1.5 font-medium">Cost</th>
              <th className="px-2 py-1.5 font-medium">Latency</th>
              <th className="px-2 py-1.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((row) => (
              <tr key={row.id} className="border-t border-border/60 tabular-nums">
                <td className="px-2 py-1.5">{new Date(row.created_at).toLocaleString()}</td>
                <td className="px-2 py-1.5">{row.task}</td>
                <td className="px-2 py-1.5 font-mono text-xs">
                  {row.provider}/{row.model}
                </td>
                <td className="px-2 py-1.5">
                  {row.tokens_in}/{row.tokens_out}
                </td>
                <td className="px-2 py-1.5">${row.cost.toFixed(4)}</td>
                <td className="px-2 py-1.5">{row.latency_ms}ms</td>
                <td className="px-2 py-1.5">{row.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <PaginationControls
        total={data.total}
        limit={page.limit}
        offset={page.offset}
        onPrev={page.prev}
        onNext={() => page.next(data.total)}
      />
    </div>
  )
}
```

- [ ] **Step 6: Wire the route and barrel**

Append to `frontend/src/features/admin/index.ts`:

```typescript
export { UsagePage } from './components/usage/UsagePage'
```

In `frontend/src/app/App.tsx`: extend the `@/features/admin` import with `UsagePage` and change the usage route to:

```tsx
<Route path="usage" element={<UsagePage />} />
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `npm run test -- UsagePage`
Expected: PASS (1 test)

- [ ] **Step 8: Gates + commit**

```bash
cd frontend && npm run lint && npm run build && npm run test && cd ..
printf 'feat: add backoffice AI usage and cost screen\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```
