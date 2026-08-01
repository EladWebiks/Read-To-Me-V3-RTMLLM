# Backoffice 06 — Tool-Call Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Paginated cross-user tool-call audit viewer with filters (tool_name, status, risk_level, date range), pretty-printed collapsed input/output JSON, duration, confirmation state, and per-row user attribution.

**Architecture:** `tool_calls` has no `user_id`; attribution joins `message_id → conversation_messages → conversations.user_id` — all llm-module tables, so the join lives in `LlmRepository`. `modules/admin/audit_router.py` is a thin HTTP layer. Rows with `message_id NULL` attribute to `null`.

**Tech Stack:** FastAPI, SQLAlchemy async, pydantic v2, pytest; React 19, react-query.

**Spec:** `docs/superpowers/specs/2026-07-30-backoffice-mvp-design.md`. **Depends on:** `2026-07-30-backoffice-01-foundation.md` (Page/PageParams, aggregator, test harness, pagination primitives).

## Global Constraints

- Backend gates per task (run from `backend/`): `uv run ruff check . --fix && uv run ruff format .`, `uv run mypy .`, `uv run pytest -m "unit or integration"`. Integration tests need Postgres/Redis/MinIO and `TEST_DATABASE_URL` pointing at a separate test DB.
- Frontend gates per task (run from `frontend/`): `npm run lint`, `npm run build`, `npm run test`.
- Commit with `bash scripts/git-commit-clean.sh /tmp/msg.txt`. **Never** add attribution trailers. Verify with `git log -1 --format=%B`.
- Ruff limits: complexity ≤10, statements ≤20, branches ≤6, args ≤6. ESLint limits: file ≤110 lines, function ≤60, nesting ≤3 (tests/barrels exempt).
- Every new route registers in `backend/tests/admin/test_authz_matrix.py::ROUTES`. No Alembic migrations.

---

### Task 1: Tool-call audit API

**Files:**
- Modify: `backend/app/modules/llm/schemas.py`
- Modify: `backend/app/modules/llm/repository.py`
- Modify: `backend/app/modules/llm/service.py`
- Create: `backend/app/modules/admin/audit_router.py`
- Modify: `backend/app/modules/admin/router.py`
- Modify: `backend/tests/admin/test_authz_matrix.py`
- Test: `backend/tests/admin/test_tool_calls_admin_api.py`

**Interfaces:**
- Consumes: `ToolCallRecord`, `Conversation`, `ConversationMessage` models; foundation's `Page`/`PageParams` and test harness. If plan 05 already added `ColumnElement`/`and_` imports to `llm/repository.py`, reuse them.
- Produces:
  - llm schemas: `ToolCallAdminFilters` (`tool_name`, `status`, `risk_level`, `period_start`, `period_end` — all optional), `ToolCallAdminRead` (`id`, `tool_name`, `status`, `risk_level`, `confirmed_by_user`, `duration_ms`, `input`, `output`, `error`, `user_id: UUID | None`, `created_at`).
  - `LlmRepository.list_tool_calls_admin(filters, *, limit, offset) -> tuple[list[tuple[ToolCallRecord, uuid.UUID | None]], int]`
  - `LlmService.list_tool_calls_admin(filters, *, limit, offset) -> tuple[list[ToolCallAdminRead], int]`
  - Route `GET /api/admin/tool-calls?tool_name&status&risk_level&from&to&limit&offset` (used by Task 2's screen).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/admin/test_tool_calls_admin_api.py
"""Backoffice tool-call audit listing with attribution join (needs Postgres)."""

from __future__ import annotations

from uuid import UUID

import pytest
from app.modules.llm.models import Conversation, ConversationMessage, ToolCallRecord
from httpx import AsyncClient

from tests.admin.helpers import create_user, login, seed_session

BASE = "/api/admin/tool-calls"


@pytest.fixture
async def admin(client: AsyncClient) -> UUID:
    user_id = await create_user("boss", is_admin=True)
    login(client, user_id, "boss")
    return user_id


async def seed_tool_calls(user_id: UUID) -> None:
    """One attributed success + one orphan failure (message_id NULL)."""
    async with seed_session() as session:
        conversation = Conversation(user_id=user_id, title="audit")
        session.add(conversation)
        await session.flush()
        message = ConversationMessage(
            conversation_id=conversation.id, role="assistant", content="…"
        )
        session.add(message)
        await session.flush()
        session.add(
            ToolCallRecord(
                message_id=message.id,
                tool_name="search_books",
                input={"q": "dragons"},
                output={"ok": True},
                status="success",
                risk_level="read_only",
                duration_ms=12,
                confirmed_by_user=False,
            )
        )
        session.add(
            ToolCallRecord(
                message_id=None,
                tool_name="scrape_url",
                input={},
                status="failed",
                risk_level="confirmation_required",
                error="boom",
            )
        )


@pytest.mark.integration
async def test_lists_all_with_attribution(client: AsyncClient, admin: UUID) -> None:
    reader = await create_user("reader")
    await seed_tool_calls(reader)
    response = await client.get(BASE)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    by_tool = {row["tool_name"]: row for row in payload["items"]}
    assert by_tool["search_books"]["user_id"] == str(reader)
    assert by_tool["search_books"]["input"] == {"q": "dragons"}
    assert by_tool["search_books"]["duration_ms"] == 12
    assert by_tool["scrape_url"]["user_id"] is None
    assert by_tool["scrape_url"]["error"] == "boom"


@pytest.mark.integration
async def test_filters(client: AsyncClient, admin: UUID) -> None:
    reader = await create_user("reader")
    await seed_tool_calls(reader)
    by_name = await client.get(BASE, params={"tool_name": "search_books"})
    assert by_name.json()["total"] == 1
    assert by_name.json()["items"][0]["tool_name"] == "search_books"
    by_status = await client.get(BASE, params={"status": "failed"})
    assert by_status.json()["total"] == 1
    by_risk = await client.get(BASE, params={"risk_level": "read_only"})
    assert by_risk.json()["total"] == 1
    none_left = await client.get(
        BASE, params={"tool_name": "search_books", "status": "failed"}
    )
    assert none_left.json()["total"] == 0


@pytest.mark.integration
async def test_pagination_envelope(client: AsyncClient, admin: UUID) -> None:
    reader = await create_user("reader")
    await seed_tool_calls(reader)
    response = await client.get(BASE, params={"limit": 1, "offset": 0})
    payload = response.json()
    assert payload["total"] == 2
    assert len(payload["items"]) == 1
    assert payload["limit"] == 1
```

Append to `ROUTES` in `backend/tests/admin/test_authz_matrix.py`:

```python
    ("GET", "/api/admin/tool-calls", None),
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/admin/test_tool_calls_admin_api.py -v`
Expected: FAIL with 404 (route missing).

- [ ] **Step 3: Add llm schemas**

Append to `backend/app/modules/llm/schemas.py` (ensure `from typing import Any` is imported):

```python
class ToolCallAdminFilters(BaseModel):
    """Optional filters for the backoffice tool-call audit list."""

    tool_name: str | None = None
    status: str | None = None
    risk_level: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None


class ToolCallAdminRead(BaseModel):
    """One tool_call audit row; user_id resolved via its conversation."""

    id: UUID
    tool_name: str
    status: str
    risk_level: str
    confirmed_by_user: bool
    duration_ms: int | None
    input: dict[str, Any]
    output: dict[str, Any] | None
    error: str | None
    user_id: UUID | None
    created_at: datetime
```

- [ ] **Step 4: Add the repository query**

In `backend/app/modules/llm/repository.py` (extend imports with `from sqlalchemy import ColumnElement, and_` if plan 05 hasn't already, and `from app.modules.llm.schemas import ToolCallAdminFilters`), add a module-level helper:

```python
def _tool_call_conditions(filters: ToolCallAdminFilters) -> list[ColumnElement[bool]]:
    """Translate the optional filter set into WHERE conditions."""
    conditions: list[ColumnElement[bool]] = []
    if filters.tool_name:
        conditions.append(ToolCallRecord.tool_name == filters.tool_name)
    if filters.status:
        conditions.append(ToolCallRecord.status == filters.status)
    if filters.risk_level:
        conditions.append(ToolCallRecord.risk_level == filters.risk_level)
    if filters.period_start:
        conditions.append(ToolCallRecord.created_at >= filters.period_start)
    if filters.period_end:
        conditions.append(ToolCallRecord.created_at < filters.period_end)
    return conditions
```

and a `LlmRepository` method:

```python
    async def list_tool_calls_admin(
        self, filters: ToolCallAdminFilters, *, limit: int, offset: int
    ) -> tuple[list[tuple[ToolCallRecord, uuid.UUID | None]], int]:
        """Cross-user audit rows, newest first, with owner via the conversation.

        tool_calls has no user_id; attribution joins message → conversation
        (both llm-module tables). message_id NULL rows attribute to None.
        """
        conditions = _tool_call_conditions(filters)
        total_stmt = select(func.count()).select_from(ToolCallRecord).where(*conditions)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(ToolCallRecord, Conversation.user_id)
            .join(
                ConversationMessage,
                ToolCallRecord.message_id == ConversationMessage.id,
                isouter=True,
            )
            .join(
                Conversation,
                ConversationMessage.conversation_id == Conversation.id,
                isouter=True,
            )
            .where(*conditions)
            .order_by(ToolCallRecord.created_at.desc(), ToolCallRecord.id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows], total
```

- [ ] **Step 5: Add the service method**

Append to `LlmService` in `backend/app/modules/llm/service.py` (extend the schemas import with `ToolCallAdminFilters`, `ToolCallAdminRead`):

```python
    async def list_tool_calls_admin(
        self, filters: ToolCallAdminFilters, *, limit: int, offset: int
    ) -> tuple[list[ToolCallAdminRead], int]:
        """Backoffice tool-call audit page with per-row user attribution."""
        rows, total = await self._repo.list_tool_calls_admin(
            filters, limit=limit, offset=offset
        )
        items = [
            ToolCallAdminRead(
                id=record.id,
                tool_name=record.tool_name,
                status=record.status,
                risk_level=record.risk_level,
                confirmed_by_user=record.confirmed_by_user,
                duration_ms=record.duration_ms,
                input=record.input,
                output=record.output,
                error=record.error,
                user_id=user_id,
                created_at=record.created_at,
            )
            for record, user_id in rows
        ]
        return items, total
```

- [ ] **Step 6: Add the audit router and include it**

```python
# backend/app/modules/admin/audit_router.py
"""Backoffice tool-call audit routes. HTTP only; logic in LlmService."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.deps import get_db, require_admin
from app.modules.admin.params import PageParams
from app.modules.admin.schemas import Page
from app.modules.llm.schemas import ToolCallAdminFilters, ToolCallAdminRead
from app.modules.llm.service import LlmService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/tool-calls")


def _llm(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LlmService:
    return LlmService(session, settings)


def _filters(
    tool_name: str | None = None,
    status: str | None = None,
    risk_level: str | None = None,
    period_start: Annotated[datetime | None, Query(alias="from")] = None,
    period_end: Annotated[datetime | None, Query(alias="to")] = None,
) -> ToolCallAdminFilters:
    return ToolCallAdminFilters(
        tool_name=tool_name,
        status=status,
        risk_level=risk_level,
        period_start=period_start,
        period_end=period_end,
    )


@router.get("")
async def list_tool_calls(
    filters: Annotated[ToolCallAdminFilters, Depends(_filters)],
    page: Annotated[PageParams, Depends()],
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[LlmService, Depends(_llm)],
) -> Page[ToolCallAdminRead]:
    """Cross-user tool_call audit rows, newest first."""
    items, total = await service.list_tool_calls_admin(
        filters, limit=page.limit, offset=page.offset
    )
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)
```

In `backend/app/modules/admin/router.py`, add:

```python
from app.modules.admin.audit_router import router as audit_router
```

and:

```python
router.include_router(audit_router)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/admin -v`
Expected: PASS (3 tool-call tests + matrix includes `/tool-calls`)

- [ ] **Step 8: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add backoffice tool-call audit API\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 2: Tool-call audit screen

**Files:**
- Create: `frontend/src/features/admin/api/toolCalls.ts`
- Create: `frontend/src/features/admin/hooks/useToolCalls.ts`
- Create: `frontend/src/features/admin/components/common/JsonBlock.tsx`
- Create: `frontend/src/features/admin/components/toolcalls/ToolCallsPage.tsx`
- Create: `frontend/src/features/admin/components/toolcalls/ToolCallFilters.tsx`
- Create: `frontend/src/features/admin/components/toolcalls/ToolCallRow.tsx`
- Modify: `frontend/src/features/admin/index.ts`
- Modify: `frontend/src/app/App.tsx` (swap the tool-calls placeholder)

**Interfaces:**
- Consumes: Task 1's route; foundation's `usePageState`, `PaginationControls`, `Page<T>`.
- Produces: `ToolCallsPage` export; `JsonBlock` (collapsed pretty-printed JSON).

- [ ] **Step 1: Implement API + hooks**

```typescript
// frontend/src/features/admin/api/toolCalls.ts
import type { Page } from '@/features/admin/types'
import { apiGet } from '@/shared/lib/api'

/** Mirrors ToolCallAdminRead (llm/schemas.py) exactly. */
export type ToolCall = {
  id: string
  tool_name: string
  status: string
  risk_level: string
  confirmed_by_user: boolean
  duration_ms: number | null
  input: Record<string, unknown>
  output: Record<string, unknown> | null
  error: string | null
  user_id: string | null
  created_at: string
}

export type ToolCallFilterValues = {
  tool_name?: string
  status?: string
  risk_level?: string
  from?: string
  to?: string
}

export const RISK_LEVELS = ['read_only', 'low_risk', 'confirmation_required'] as const

export function fetchToolCalls(
  filters: ToolCallFilterValues,
  limit: number,
  offset: number,
): Promise<Page<ToolCall>> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  for (const [key, value] of Object.entries(filters)) {
    if (value) {
      params.set(key, value)
    }
  }
  return apiGet(`/api/admin/tool-calls?${params.toString()}`)
}
```

```typescript
// frontend/src/features/admin/hooks/useToolCalls.ts
import { useQuery } from '@tanstack/react-query'
import { fetchToolCalls, type ToolCallFilterValues } from '@/features/admin/api/toolCalls'

export function useToolCalls(filters: ToolCallFilterValues, limit: number, offset: number) {
  return useQuery({
    queryKey: ['admin', 'tool-calls', filters, limit, offset],
    queryFn: () => fetchToolCalls(filters, limit, offset),
  })
}
```

- [ ] **Step 2: Implement the components**

```tsx
// frontend/src/features/admin/components/common/JsonBlock.tsx
export function JsonBlock({ label, value }: { label: string; value: unknown }) {
  if (value === null || value === undefined) {
    return <p className="text-xs text-muted-foreground">{label}: —</p>
  }
  return (
    <details className="text-xs">
      <summary className="cursor-pointer text-muted-foreground">{label}</summary>
      <pre className="mt-1 max-h-64 overflow-auto rounded bg-muted/40 p-2">
        {JSON.stringify(value, null, 2)}
      </pre>
    </details>
  )
}
```

```tsx
// frontend/src/features/admin/components/toolcalls/ToolCallFilters.tsx
import { RISK_LEVELS, type ToolCallFilterValues } from '@/features/admin/api/toolCalls'

const FIELD = 'rounded border border-border bg-background px-2 py-1 text-sm'

export function ToolCallFilters({
  filters,
  onChange,
}: {
  filters: ToolCallFilterValues
  onChange: (filters: ToolCallFilterValues) => void
}) {
  return (
    <div className="mb-4 flex flex-wrap gap-2">
      <input
        className={FIELD}
        placeholder="Tool name"
        aria-label="Filter by tool name"
        value={filters.tool_name ?? ''}
        onChange={(event) => onChange({ ...filters, tool_name: event.target.value })}
      />
      <input
        className={FIELD}
        placeholder="Status"
        aria-label="Filter by status"
        value={filters.status ?? ''}
        onChange={(event) => onChange({ ...filters, status: event.target.value })}
      />
      <select
        className={FIELD}
        aria-label="Filter by risk level"
        value={filters.risk_level ?? ''}
        onChange={(event) => onChange({ ...filters, risk_level: event.target.value })}
      >
        <option value="">Any risk</option>
        {RISK_LEVELS.map((risk) => (
          <option key={risk} value={risk}>
            {risk}
          </option>
        ))}
      </select>
    </div>
  )
}
```

```tsx
// frontend/src/features/admin/components/toolcalls/ToolCallRow.tsx
import type { ToolCall } from '@/features/admin/api/toolCalls'
import { JsonBlock } from '@/features/admin/components/common/JsonBlock'

export function ToolCallRow({ call }: { call: ToolCall }) {
  return (
    <div className="rounded-lg border border-border/70 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs font-medium">{call.tool_name}</span>
        <span className="rounded bg-muted px-1.5 py-0.5 text-xs">{call.status}</span>
        <span className="rounded bg-muted px-1.5 py-0.5 text-xs">{call.risk_level}</span>
        {call.confirmed_by_user && (
          <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-xs text-emerald-600">
            confirmed
          </span>
        )}
        <span className="ml-auto text-xs text-muted-foreground">
          {call.duration_ms !== null ? `${call.duration_ms}ms · ` : ''}
          {new Date(call.created_at).toLocaleString()}
        </span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">user: {call.user_id ?? '—'}</p>
      <div className="mt-2 space-y-1">
        <JsonBlock label="Input" value={call.input} />
        <JsonBlock label="Output" value={call.output} />
      </div>
      {call.error ? <p className="mt-1 text-xs text-destructive">{call.error}</p> : null}
    </div>
  )
}
```

```tsx
// frontend/src/features/admin/components/toolcalls/ToolCallsPage.tsx
import { useState } from 'react'
import type { ToolCallFilterValues } from '@/features/admin/api/toolCalls'
import { PaginationControls } from '@/features/admin/components/common/PaginationControls'
import { usePageState } from '@/features/admin/hooks/usePageState'
import { useToolCalls } from '@/features/admin/hooks/useToolCalls'
import { ToolCallFilters } from './ToolCallFilters'
import { ToolCallRow } from './ToolCallRow'

export function ToolCallsPage() {
  const [filters, setFilters] = useState<ToolCallFilterValues>({})
  const page = usePageState(25)
  const { data, isLoading, error } = useToolCalls(filters, page.limit, page.offset)

  const applyFilters = (next: ToolCallFilterValues) => {
    setFilters(next)
    page.reset()
  }

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading tool calls…</p>
  }
  if (error || !data) {
    return <p className="text-sm text-destructive">Failed to load tool calls.</p>
  }
  return (
    <section>
      <h1 className="mb-1 text-lg font-semibold">Tool-call audit</h1>
      <ToolCallFilters filters={filters} onChange={applyFilters} />
      <div className="space-y-2">
        {data.items.map((call) => (
          <ToolCallRow key={call.id} call={call} />
        ))}
        {data.items.length === 0 && (
          <p className="text-sm text-muted-foreground">No tool calls match the filters.</p>
        )}
      </div>
      <PaginationControls
        total={data.total}
        limit={page.limit}
        offset={page.offset}
        onPrev={page.prev}
        onNext={() => page.next(data.total)}
      />
    </section>
  )
}
```

- [ ] **Step 3: Wire the route and barrel**

Append to `frontend/src/features/admin/index.ts`:

```typescript
export { ToolCallsPage } from './components/toolcalls/ToolCallsPage'
```

In `frontend/src/app/App.tsx`: extend the `@/features/admin` import with `ToolCallsPage` and change the tool-calls route to:

```tsx
<Route path="tool-calls" element={<ToolCallsPage />} />
```

- [ ] **Step 4: Gates + commit**

```bash
cd frontend && npm run lint && npm run build && npm run test && cd ..
printf 'feat: add backoffice tool-call audit screen\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```
