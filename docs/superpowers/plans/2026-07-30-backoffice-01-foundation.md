# Backoffice 01 — Shared Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Everything the six backoffice screens share: the backend `modules/admin` scaffold with pagination/period conventions and the authz test harness, and the frontend admin foundation (guard, layout, nav gating, API-client fixes, pagination primitives).

**Architecture:** `modules/admin` is a thin aggregation module — routers + DTOs only, no repository/models/service; screen plans add sub-routers to its aggregator. On the frontend, `RequireAdmin`/`useIsAdmin` live in `features/auth`; layout, placeholder routes, and shared primitives live in `features/admin`.

**Tech Stack:** FastAPI, pydantic v2, pytest; React 19, react-router, @tanstack/react-query, vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-07-30-backoffice-mvp-design.md`. **Overview:** `2026-07-30-backoffice-00-overview.md`.

## Global Constraints

- Backend gates per task (run from `backend/`): `uv run ruff check . --fix && uv run ruff format .`, `uv run mypy .`, `uv run pytest -m "unit or integration"`. Integration tests need Postgres/Redis/MinIO and `TEST_DATABASE_URL` pointing at a separate test DB.
- Frontend gates per task (run from `frontend/`): `npm run lint`, `npm run build`, `npm run test`.
- Commit with `bash scripts/git-commit-clean.sh /tmp/msg.txt` (write the message to `/tmp/msg.txt` first). **Never** add `Co-authored-by`/`Made-with` trailers. Verify with `git log -1 --format=%B`.
- Ruff limits: complexity ≤10, statements ≤20, branches ≤6, args ≤6. ESLint limits: file ≤110 lines, function ≤60, nesting ≤3 (tests and barrels exempt).
- Module direction: router → service → repository; `modules/admin` holds no business logic and no data access.
- pydantic response schemas everywhere; no Alembic migrations in this plan.
- Never log or return secrets.

---

### Task 1: Backend `modules/admin` scaffold + test harness

**Files:**
- Create: `backend/app/modules/admin/__init__.py`
- Create: `backend/app/modules/admin/schemas.py`
- Create: `backend/app/modules/admin/params.py`
- Create: `backend/app/modules/admin/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/admin/__init__.py`
- Create: `backend/tests/admin/helpers.py`
- Create: `backend/tests/admin/conftest.py`
- Create: `backend/tests/admin/test_authz_matrix.py`
- Test: `backend/tests/admin/test_scaffold.py`

**Interfaces:**
- Produces (used by every screen plan):
  - `Page[ItemT]` (pydantic generic): `items: list[ItemT]`, `total: int`, `limit: int`, `offset: int`.
  - `PageParams` dependency class: `limit` (ge=1, le=200, default 50), `offset` (ge=0, default 0).
  - `PeriodParams` dependency class: required `period_start`/`period_end` datetimes from `from`/`to` query aliases, meaning `[from, to)`.
  - Aggregator `router = APIRouter(prefix="/admin", tags=["admin"])` — screen plans add `router.include_router(<sub_router>)` lines to `router.py`.
  - Test helpers: `HOST`, `seed_session()` (committing standalone session), `create_user(username, *, is_admin=False, deleted=False) -> UUID`, `login(client, user_id, username)`; shared `client` fixture (DB-override + FK-ordered cleanup).
  - `test_authz_matrix.py::ROUTES` — screen plans append `(method, path, body)` entries; the matrix asserts 401 anonymous / 403 non-admin for every entry.

- [ ] **Step 1: Write the failing scaffold test**

```python
# backend/tests/admin/test_scaffold.py
"""Pin the admin aggregator wiring."""

import pytest
from app.modules.admin.router import router


@pytest.mark.unit
def test_admin_router_prefix() -> None:
    assert router.prefix == "/admin"
```

Also create the (empty) package marker:

```python
# backend/tests/admin/__init__.py
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `uv run pytest tests/admin/test_scaffold.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.modules.admin'`.

- [ ] **Step 3: Implement the module**

```python
# backend/app/modules/admin/__init__.py
"""Backoffice aggregation module — routers + DTOs only, no data layer."""
```

```python
# backend/app/modules/admin/schemas.py
"""Aggregation-only DTOs for the backoffice API."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

ItemT = TypeVar("ItemT")


class Page(BaseModel, Generic[ItemT]):
    """Uniform limit/offset pagination envelope for admin lists."""

    items: list[ItemT]
    total: int
    limit: int
    offset: int
```

```python
# backend/app/modules/admin/params.py
"""Reusable admin query-parameter dependency groups."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import Query


class PageParams:
    """limit/offset pagination inputs shared by every admin list route."""

    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset


class PeriodParams:
    """Required [from, to) date range for usage aggregates."""

    def __init__(
        self,
        period_start: Annotated[datetime, Query(alias="from")],
        period_end: Annotated[datetime, Query(alias="to")],
    ) -> None:
        self.period_start = period_start
        self.period_end = period_end
```

```python
# backend/app/modules/admin/router.py
"""Backoffice aggregation router — thin composition over owning modules.

Screen plans register their sub-routers here (users, usage, tool-calls,
jobs). The aggregator itself defines no endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])
```

- [ ] **Step 4: Register in `main.py`**

In `backend/app/main.py`, add the import (alphabetically with the other module routers):

```python
from app.modules.admin.router import router as admin_router
```

and in `create_app()`, after the `runtime_config_router` line:

```python
    app.include_router(admin_router, prefix=settings.app.api_prefix)
```

- [ ] **Step 5: Create the shared test harness**

```python
# backend/tests/admin/helpers.py
"""Seed/login helpers shared by backoffice API tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

from app.core.config import get_settings
from app.core.deps import COOKIE_NAME
from app.core.security import create_access_token
from app.modules.users.models import User
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# http.cookiejar drops cookies scoped to a single-label host (see test_auth_api.py).
HOST = "test.local"


@asynccontextmanager
async def seed_session() -> AsyncIterator[AsyncSession]:
    """Standalone committing session for seeding rows outside the app."""
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
        await session.commit()
    await engine.dispose()


async def create_user(
    username: str,
    *,
    is_admin: bool = False,
    deleted: bool = False,
) -> UUID:
    """Insert a user directly; returns its id."""
    async with seed_session() as session:
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=None,
            google_sub=f"{username}-sub",
            is_admin=is_admin,
            deleted_at=datetime.now(UTC) if deleted else None,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
    return user_id


def login(client: AsyncClient, user_id: UUID, username: str) -> None:
    """Set a valid session cookie on the test client."""
    token = create_access_token(user_id=user_id, username=username, settings=get_settings())
    client.cookies.set(COOKIE_NAME, token, domain=HOST, path="/")
```

```python
# backend/tests/admin/conftest.py
"""Shared HTTP client fixture for backoffice API tests (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import pytest
from app.core.config import get_settings
from app.core.deps import get_db
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.admin.helpers import HOST
from tests.dbcleanup import clear_users


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


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await clear_users(conn)
    app.dependency_overrides[get_db] = _make_db_override(session_factory)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=f"http://{HOST}") as http:
        yield http
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await clear_users(conn)
    await engine.dispose()
```

```python
# backend/tests/admin/test_authz_matrix.py
"""401/403 authorization matrix over every backoffice route (needs Postgres).

Every /api/admin route added by a backoffice screen plan MUST register in
ROUTES. With no entries yet, pytest emits one skipped instance per test —
that is expected until the first screen plan lands.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.admin.helpers import create_user, login

ZERO = "00000000-0000-0000-0000-000000000000"

# (method, path, json body) — screen plans append here.
ROUTES: list[tuple[str, str, dict[str, object] | None]] = []


@pytest.mark.integration
@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
async def test_anonymous_gets_401(
    client: AsyncClient, method: str, path: str, body: dict[str, object] | None
) -> None:
    response = await client.request(method, path, json=body)
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
async def test_non_admin_gets_403(
    client: AsyncClient, method: str, path: str, body: dict[str, object] | None
) -> None:
    user_id = await create_user("matrix-plain")
    login(client, user_id, "matrix-plain")
    response = await client.request(method, path, json=body)
    assert response.status_code == 403
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/admin -v`
Expected: `test_scaffold` PASSES; the two matrix tests show as skipped ("empty parameter set") — expected until a screen plan appends routes.

- [ ] **Step 7: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: scaffold backoffice admin module and authz test harness\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 2: Frontend foundation — guard, layout, nav gating, API client

**Files:**
- Modify: `frontend/src/shared/lib/api.ts` (parse error `detail`; add `apiPatch`)
- Create: `frontend/src/features/auth/hooks/useIsAdmin.ts`
- Modify: `frontend/src/features/auth/hooks/index.ts`
- Create: `frontend/src/features/auth/components/RequireAdmin.tsx`
- Modify: `frontend/src/features/auth/index.ts`
- Create: `frontend/src/features/admin/types.ts`
- Create: `frontend/src/features/admin/components/AdminNav.tsx`
- Create: `frontend/src/features/admin/components/AdminLayout.tsx`
- Create: `frontend/src/features/admin/components/AdminPlaceholder.tsx`
- Create: `frontend/src/features/admin/index.ts`
- Modify: `frontend/src/app/App.tsx`
- Modify: `frontend/src/layout/ShellNav.tsx`
- Test: `frontend/src/features/auth/components/RequireAdmin.test.tsx`
- Test: `frontend/src/layout/ShellNav.test.tsx`

**Interfaces:**
- Consumes: existing `useMe`, `MeResponse`, `ApiError`.
- Produces (used by every screen plan):
  - `apiPatch<T>(path, body?)` in `@/shared/lib/api`; `ApiError.message` now carries the backend `detail` string when present.
  - `useIsAdmin(): boolean` (from `@/features/auth/hooks`).
  - `RequireAdmin` route guard (from `@/features/auth`).
  - `Page<T> = { items: T[]; total: number; limit: number; offset: number }` (from `@/features/admin/types`).
  - `/admin/*` routes rendering `AdminLayout`; each section renders `AdminPlaceholder` until its screen plan swaps the element in `App.tsx`.

- [ ] **Step 1: Write the failing tests**

```tsx
// frontend/src/features/auth/components/RequireAdmin.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { RequireAdmin } from './RequireAdmin'
import { fetchMe } from '@/features/auth/api'
import type { MeResponse } from '@/features/auth/types'

vi.mock('@/features/auth/api', () => ({
  fetchMe: vi.fn(),
}))

function me(isAdmin: boolean): MeResponse {
  return {
    user: {
      id: 'u1',
      username: 'boss',
      email: null,
      picture_url: null,
      is_admin: isAdmin,
      membership: 'free',
      created_at: '2026-01-01T00:00:00Z',
    },
  }
}

function renderGuard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route path="/" element={<p>home</p>} />
          <Route element={<RequireAdmin />}>
            <Route path="/admin" element={<p>admin area</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('RequireAdmin', () => {
  it('renders admin content for admins', async () => {
    vi.mocked(fetchMe).mockResolvedValue(me(true))
    renderGuard()
    expect(await screen.findByText('admin area')).toBeTruthy()
  })

  it('redirects non-admins home', async () => {
    vi.mocked(fetchMe).mockResolvedValue(me(false))
    renderGuard()
    expect(await screen.findByText('home')).toBeTruthy()
    expect(screen.queryByText('admin area')).toBeNull()
  })
})
```

```tsx
// frontend/src/layout/ShellNav.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { ShellNavLinks } from './ShellNav'
import { fetchMe } from '@/features/auth/api'
import type { MeResponse } from '@/features/auth/types'

vi.mock('@/features/auth/api', () => ({
  fetchMe: vi.fn(),
}))

function me(isAdmin: boolean): MeResponse {
  return {
    user: {
      id: 'u1',
      username: 'boss',
      email: null,
      picture_url: null,
      is_admin: isAdmin,
      membership: 'free',
      created_at: '2026-01-01T00:00:00Z',
    },
  }
}

function renderNav() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ShellNavLinks readerActive={false} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ShellNavLinks admin gating', () => {
  it('shows the Admin link for admins', async () => {
    vi.mocked(fetchMe).mockResolvedValue(me(true))
    renderNav()
    expect(await screen.findByText('Admin')).toBeTruthy()
  })

  it('hides the Admin link for non-admins', async () => {
    vi.mocked(fetchMe).mockResolvedValue(me(false))
    renderNav()
    expect(await screen.findByText('Library')).toBeTruthy()
    expect(screen.queryByText('Admin')).toBeNull()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `frontend/`): `npm run test -- RequireAdmin ShellNav`
Expected: FAIL — `./RequireAdmin` module not found; ShellNav renders no Admin link.

- [ ] **Step 3: Extend the shared API client**

In `frontend/src/shared/lib/api.ts`, replace `parseJson` with the pair below and add `apiPatch` next to `apiPut`:

```typescript
async function errorDetail(response: Response): Promise<string> {
  const fallback = `Request failed: ${response.status}`
  try {
    const payload = (await response.json()) as { detail?: unknown }
    return typeof payload.detail === 'string' && payload.detail ? payload.detail : fallback
  } catch {
    return fallback
  }
}

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new ApiError(response.status, await errorDetail(response))
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}
```

```typescript
export function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('PATCH', path, body)
}
```

- [ ] **Step 4: Add the hook and guard**

```typescript
// frontend/src/features/auth/hooks/useIsAdmin.ts
import { useMe } from './hooks'

export function useIsAdmin(): boolean {
  const { data } = useMe()
  return data?.user?.is_admin === true
}
```

Append to `frontend/src/features/auth/hooks/index.ts`:

```typescript
export { useIsAdmin } from './useIsAdmin'
```

```tsx
// frontend/src/features/auth/components/RequireAdmin.tsx
import { Navigate, Outlet } from 'react-router'
import { useMe } from '@/features/auth/hooks'

/** Nested inside ProtectedRoute: the session exists; only the flag is checked. */
export function RequireAdmin() {
  const { data, isLoading } = useMe()
  if (isLoading) {
    return <p className="p-8 text-sm text-muted-foreground">Checking access…</p>
  }
  if (!data?.user?.is_admin) {
    return <Navigate to="/" replace />
  }
  return <Outlet />
}
```

Append to `frontend/src/features/auth/index.ts`:

```typescript
export { RequireAdmin } from './components/RequireAdmin'
```

- [ ] **Step 5: Create the admin feature skeleton**

```typescript
// frontend/src/features/admin/types.ts
/** Mirrors the backend Page[T] envelope (modules/admin/schemas.py). */
export type Page<T> = {
  items: T[]
  total: number
  limit: number
  offset: number
}
```

```tsx
// frontend/src/features/admin/components/AdminNav.tsx
import { NavLink } from 'react-router'

const LINKS = [
  { to: '/admin/users', label: 'Users' },
  { to: '/admin/settings', label: 'Settings' },
  { to: '/admin/usage', label: 'AI Usage' },
  { to: '/admin/catalog', label: 'LLM Catalog' },
  { to: '/admin/tool-calls', label: 'Tool Calls' },
  { to: '/admin/jobs', label: 'Jobs' },
]

export function AdminNav() {
  return (
    <nav className="w-full shrink-0 space-y-1 text-sm sm:w-44" aria-label="Admin sections">
      {LINKS.map(({ to, label }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            `block rounded-md px-3 py-1.5 transition-colors ${
              isActive
                ? 'bg-muted font-medium text-foreground'
                : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
            }`
          }
        >
          {label}
        </NavLink>
      ))}
    </nav>
  )
}
```

```tsx
// frontend/src/features/admin/components/AdminLayout.tsx
import { Outlet } from 'react-router'
import { AdminNav } from './AdminNav'

export function AdminLayout() {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:gap-6">
      <AdminNav />
      <div className="min-w-0 flex-1">
        <Outlet />
      </div>
    </div>
  )
}
```

```tsx
// frontend/src/features/admin/components/AdminPlaceholder.tsx
export function AdminPlaceholder() {
  return <p className="text-sm text-muted-foreground">This section is coming soon.</p>
}
```

```typescript
// frontend/src/features/admin/index.ts
export { AdminLayout } from './components/AdminLayout'
export { AdminPlaceholder } from './components/AdminPlaceholder'
```

- [ ] **Step 6: Wire routes and nav**

Replace `frontend/src/app/App.tsx` with:

```tsx
import { BrowserRouter, Navigate, Route, Routes, useParams } from 'react-router'
import { AdminLayout, AdminPlaceholder } from '@/features/admin'
import { LoginPage, ProtectedRoute, PublicOnlyRoute, RequireAdmin } from '@/features/auth'
import { ChapterEditorPage, ChapterNewPage, LibraryPage } from '@/features/library'
import { libraryBookHref } from '@/features/library/logic/libraryPaths'
import { ReaderHubPage, ReaderPage, ResumeReadingPage } from '@/features/reader'
import { ScraperPage } from '@/features/scraping'
import { AppShell } from '@/layout/AppShell'

function LegacyBookDetailRedirect() {
  const { bookId = '' } = useParams()
  return <Navigate to={libraryBookHref(bookId)} replace />
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<PublicOnlyRoute />}>
          <Route path="/login" element={<LoginPage />} />
        </Route>
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route path="/" element={<Navigate to="/reader" replace />} />
            <Route path="/library" element={<LibraryPage />} />
            <Route path="/library/books/:bookId" element={<LegacyBookDetailRedirect />} />
            <Route
              path="/library/books/:bookId/chapters/new"
              element={<ChapterNewPage />}
            />
            <Route
              path="/library/books/:bookId/chapters/:chapterId/edit"
              element={<ChapterEditorPage />}
            />
            <Route path="/reader" element={<ReaderHubPage />} />
            <Route path="/read/:bookId" element={<ResumeReadingPage />} />
            <Route path="/read/:bookId/:chapterId" element={<ReaderPage />} />
            <Route path="/scraper" element={<ScraperPage />} />
            <Route element={<RequireAdmin />}>
              <Route path="/admin" element={<AdminLayout />}>
                <Route index element={<Navigate to="/admin/users" replace />} />
                <Route path="users" element={<AdminPlaceholder />} />
                <Route path="settings" element={<AdminPlaceholder />} />
                <Route path="usage" element={<AdminPlaceholder />} />
                <Route path="catalog" element={<AdminPlaceholder />} />
                <Route path="tool-calls" element={<AdminPlaceholder />} />
                <Route path="jobs" element={<AdminPlaceholder />} />
              </Route>
            </Route>
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
```

In `frontend/src/layout/ShellNav.tsx`, replace the imports and `ShellNavLinks` (keep the private `ShellNav` component unchanged):

```tsx
import type { ReactNode } from 'react'
import { BookOpen, Library, ShieldCheck, Wand2 } from 'lucide-react'
import { NavLink } from 'react-router'
import { useIsAdmin } from '@/features/auth/hooks'

export function ShellNavLinks({ readerActive }: { readerActive: boolean }) {
  const isAdmin = useIsAdmin()
  return (
    <nav className="mr-1 flex items-center gap-1 text-sm">
      <ShellNav to="/library" label="Library" icon={<Library className="h-4 w-4" />} />
      <ShellNav
        to="/reader"
        label="Reader"
        icon={<BookOpen className="h-4 w-4" />}
        active={readerActive}
      />
      <ShellNav to="/scraper" label="Scraper" icon={<Wand2 className="h-4 w-4" />} />
      {isAdmin && (
        <ShellNav to="/admin" label="Admin" icon={<ShieldCheck className="h-4 w-4" />} />
      )}
    </nav>
  )
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `npm run test -- RequireAdmin ShellNav`
Expected: PASS (4 tests)

- [ ] **Step 8: Gates + commit**

```bash
cd frontend && npm run lint && npm run build && npm run test && cd ..
printf 'feat: add admin frontend foundation (RequireAdmin, layout, nav gating)\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 3: Shared pagination primitives

**Files:**
- Create: `frontend/src/features/admin/hooks/usePageState.ts`
- Create: `frontend/src/features/admin/components/common/PaginationControls.tsx`
- Test: `frontend/src/features/admin/hooks/usePageState.test.ts`

**Interfaces:**
- Produces (used by the users/usage/tool-calls/jobs screens):
  - `usePageState(limit = 50)` → `{ limit: number; offset: number; prev(): void; next(total: number): void; reset(): void }`
  - `PaginationControls` props: `{ total, limit, offset, onPrev, onNext }`

- [ ] **Step 1: Write the failing hook test**

```typescript
// frontend/src/features/admin/hooks/usePageState.test.ts
import { act } from 'react'
import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { usePageState } from './usePageState'

describe('usePageState', () => {
  it('pages forward and back within bounds', () => {
    const { result } = renderHook(() => usePageState(10))
    expect(result.current.offset).toBe(0)
    act(() => result.current.next(25))
    expect(result.current.offset).toBe(10)
    act(() => result.current.next(25))
    expect(result.current.offset).toBe(20)
    act(() => result.current.next(25))
    expect(result.current.offset).toBe(20)
    act(() => result.current.prev())
    expect(result.current.offset).toBe(10)
    act(() => result.current.reset())
    expect(result.current.offset).toBe(0)
  })

  it('never goes below zero', () => {
    const { result } = renderHook(() => usePageState(10))
    act(() => result.current.prev())
    expect(result.current.offset).toBe(0)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- usePageState`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```typescript
// frontend/src/features/admin/hooks/usePageState.ts
import { useState } from 'react'

/** limit/offset paging for the backend Page[T] envelope. */
export function usePageState(limit = 50) {
  const [offset, setOffset] = useState(0)
  return {
    limit,
    offset,
    prev: () => setOffset((current) => Math.max(0, current - limit)),
    next: (total: number) =>
      setOffset((current) => (current + limit < total ? current + limit : current)),
    reset: () => setOffset(0),
  }
}
```

```tsx
// frontend/src/features/admin/components/common/PaginationControls.tsx
export function PaginationControls({
  total,
  limit,
  offset,
  onPrev,
  onNext,
}: {
  total: number
  limit: number
  offset: number
  onPrev: () => void
  onNext: () => void
}) {
  const start = total === 0 ? 0 : offset + 1
  const end = Math.min(offset + limit, total)
  return (
    <div className="mt-3 flex items-center gap-3 text-sm text-muted-foreground">
      <span>
        {start}–{end} of {total}
      </span>
      <button
        type="button"
        className="underline disabled:opacity-40"
        disabled={offset === 0}
        onClick={onPrev}
      >
        Prev
      </button>
      <button
        type="button"
        className="underline disabled:opacity-40"
        disabled={offset + limit >= total}
        onClick={onNext}
      >
        Next
      </button>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test -- usePageState`
Expected: PASS (2 tests)

- [ ] **Step 5: Gates + commit**

```bash
cd frontend && npm run lint && npm run build && npm run test && cd ..
printf 'feat: add shared admin pagination primitives\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```
