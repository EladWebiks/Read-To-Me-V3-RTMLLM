# Backoffice 07 — Jobs Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read-only cross-user jobs monitor for scraping and download jobs with status/progress/timing and a status filter. No job actions (cancel/retry stay in owning features). EPUB import jobs are deliberately excluded — their store is in-memory (`imports/jobs.py`), not DB rows.

**Architecture:** Admin-scoped list methods on `ScrapingService`/`DownloadService` over new cross-user repository reads (no side effects: no expiry purge, no pruning; raw error strings, not `public_scrape_error`). `modules/admin/jobs_router.py` is a thin HTTP layer. `ScrapingService._book_titles` is reused — `BookService.list_read` is not ownership-scoped, so titles resolve for any owner.

**Tech Stack:** FastAPI, SQLAlchemy async, pydantic v2, pytest; React 19, react-query.

**Spec:** `docs/superpowers/specs/2026-07-30-backoffice-mvp-design.md`. **Depends on:** `2026-07-30-backoffice-01-foundation.md` (Page/PageParams, aggregator, test harness, pagination primitives).

## Global Constraints

- Backend gates per task (run from `backend/`): `uv run ruff check . --fix && uv run ruff format .`, `uv run mypy .`, `uv run pytest -m "unit or integration"`. Integration tests need Postgres/Redis/MinIO and `TEST_DATABASE_URL` pointing at a separate test DB.
- Frontend gates per task (run from `frontend/`): `npm run lint`, `npm run build`, `npm run test`.
- Commit with `bash scripts/git-commit-clean.sh /tmp/msg.txt`. **Never** add attribution trailers. Verify with `git log -1 --format=%B`.
- Ruff limits: complexity ≤10, statements ≤20, branches ≤6, args ≤6. ESLint limits: file ≤110 lines, function ≤60, nesting ≤3 (tests/barrels exempt).
- Admin reads are new, admin-named methods — never loosen ownership-scoped ones.
- Every new route registers in `backend/tests/admin/test_authz_matrix.py::ROUTES`. No Alembic migrations.

---

### Task 1: Jobs monitor API (scraping + downloads)

**Files:**
- Modify: `backend/app/modules/scraping/schemas.py`
- Modify: `backend/app/modules/scraping/repository.py`
- Modify: `backend/app/modules/scraping/service.py`
- Modify: `backend/app/modules/downloads/schemas.py`
- Modify: `backend/app/modules/downloads/repository.py`
- Modify: `backend/app/modules/downloads/service.py`
- Create: `backend/app/modules/admin/jobs_router.py`
- Modify: `backend/app/modules/admin/router.py`
- Modify: `backend/tests/admin/test_authz_matrix.py`
- Test: `backend/tests/admin/test_jobs_admin_api.py`

**Interfaces:**
- Consumes: `ScrapingJob`/`DownloadJob` models; `ScrapingService._book_titles`; foundation's `Page`/`PageParams` and test harness.
- Produces (used by Task 2's screen):
  - `ScrapeJobAdminRead` (from_attributes: `id`, `user_id`, `book_id`, `book_title: str | None = None`, `start_url`, `mode`, `status`, `chapters_done`, `chapter_from`, `chapter_to`, `message: str | None`, `error: str | None`, `created_at`, `updated_at`).
  - `DownloadJobAdminRead` (from_attributes: `id`, `user_id`, `book_id`, `chapter_from`, `chapter_to`, `provider`, `voice`, `status`, `ready_count`, `total_count`, `error`, `expires_at`, `created_at`, `updated_at`).
  - `ScrapingService.list_jobs_admin(*, status: str | None, limit: int, offset: int) -> tuple[list[ScrapeJobAdminRead], int]`
  - `DownloadService.list_jobs_admin(*, status: str | None, limit: int, offset: int) -> tuple[list[DownloadJobAdminRead], int]`
  - Routes `GET /api/admin/jobs/scraping` and `GET /api/admin/jobs/downloads` (`status` optional).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/admin/test_jobs_admin_api.py
"""Backoffice cross-user job listings (needs Postgres)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from app.modules.books.models import Book
from app.modules.downloads.models import DownloadJob
from app.modules.scraping.models import ScrapingJob, ScrapingSource
from httpx import AsyncClient

from tests.admin.helpers import create_user, login, seed_session


@pytest.fixture
async def admin(client: AsyncClient) -> UUID:
    user_id = await create_user("boss", is_admin=True)
    login(client, user_id, "boss")
    return user_id


async def seed_scrape_job(user_id: UUID, *, status: str = "pending") -> None:
    async with seed_session() as session:
        source = ScrapingSource(
            name=f"src-{uuid4().hex[:8]}", base_domains=["example.com"]
        )
        session.add(source)
        await session.flush()
        session.add(
            ScrapingJob(
                user_id=user_id,
                source_id=source.id,
                start_url="https://example.com/book",
                status=status,
                message="Queued…",
            )
        )


async def seed_download_job(user_id: UUID, *, status: str = "pending") -> None:
    async with seed_session() as session:
        book = Book(title="Book", normalized_title="book")
        session.add(book)
        await session.flush()
        session.add(
            DownloadJob(
                user_id=user_id,
                book_id=book.id,
                chapter_from=1,
                chapter_to=3,
                provider="edge",
                voice="voice",
                status=status,
                total_count=3,
            )
        )


@pytest.mark.integration
async def test_scraping_jobs_cross_user(client: AsyncClient, admin: UUID) -> None:
    alice = await create_user("alice")
    bob = await create_user("bob")
    await seed_scrape_job(alice, status="running")
    await seed_scrape_job(bob, status="failed")
    response = await client.get("/api/admin/jobs/scraping")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    owners = {row["user_id"] for row in payload["items"]}
    assert owners == {str(alice), str(bob)}


@pytest.mark.integration
async def test_scraping_status_filter_and_paging(client: AsyncClient, admin: UUID) -> None:
    alice = await create_user("alice")
    await seed_scrape_job(alice, status="running")
    await seed_scrape_job(alice, status="failed")
    filtered = await client.get("/api/admin/jobs/scraping", params={"status": "failed"})
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["status"] == "failed"
    paged = await client.get("/api/admin/jobs/scraping", params={"limit": 1})
    assert paged.json()["total"] == 2
    assert len(paged.json()["items"]) == 1


@pytest.mark.integration
async def test_download_jobs_cross_user(client: AsyncClient, admin: UUID) -> None:
    alice = await create_user("alice")
    bob = await create_user("bob")
    await seed_download_job(alice, status="processing")
    await seed_download_job(bob, status="complete")
    response = await client.get("/api/admin/jobs/downloads")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    row = next(item for item in payload["items"] if item["user_id"] == str(alice))
    assert row["status"] == "processing"
    assert row["total_count"] == 3


@pytest.mark.integration
async def test_download_status_filter(client: AsyncClient, admin: UUID) -> None:
    alice = await create_user("alice")
    await seed_download_job(alice, status="processing")
    await seed_download_job(alice, status="complete")
    filtered = await client.get("/api/admin/jobs/downloads", params={"status": "complete"})
    assert filtered.json()["total"] == 1
```

Append to `ROUTES` in `backend/tests/admin/test_authz_matrix.py`:

```python
    ("GET", "/api/admin/jobs/scraping", None),
    ("GET", "/api/admin/jobs/downloads", None),
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/admin/test_jobs_admin_api.py -v`
Expected: FAIL with 404 (routes missing).

- [ ] **Step 3: Add scraping admin read**

Append to `backend/app/modules/scraping/schemas.py`:

```python
class ScrapeJobAdminRead(BaseModel):
    """Backoffice view of one scraping job (cross-user, read-only, raw error)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    book_id: UUID | None
    book_title: str | None = None
    start_url: str
    mode: str
    status: str
    chapters_done: int
    chapter_from: int | None
    chapter_to: int | None
    message: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime
```

Append to `ScrapingRepository` in `backend/app/modules/scraping/repository.py` (ensure `func` is in the sqlalchemy import):

```python
    async def list_jobs_admin(
        self, *, status: str | None, limit: int, offset: int
    ) -> tuple[list[ScrapingJob], int]:
        """Backoffice page over ALL users' jobs, newest first."""
        conditions = [] if status is None else [ScrapingJob.status == status]
        total_stmt = select(func.count()).select_from(ScrapingJob).where(*conditions)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(ScrapingJob)
            .where(*conditions)
            .order_by(ScrapingJob.created_at.desc(), ScrapingJob.id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows), total
```

Append to `ScrapingService` in `backend/app/modules/scraping/service.py` (extend the schemas import with `ScrapeJobAdminRead`):

```python
    async def list_jobs_admin(
        self, *, status: str | None, limit: int, offset: int
    ) -> tuple[list[ScrapeJobAdminRead], int]:
        """Backoffice: all users' jobs with book titles; no pruning, raw errors."""
        jobs, total = await self._repo.list_jobs_admin(
            status=status, limit=limit, offset=offset
        )
        titles = await self._book_titles(jobs)
        items = [
            ScrapeJobAdminRead.model_validate(job).model_copy(
                update={"book_title": titles.get(job.book_id) if job.book_id else None}
            )
            for job in jobs
        ]
        return items, total
```

- [ ] **Step 4: Add downloads admin read**

Append to `backend/app/modules/downloads/schemas.py`:

```python
class DownloadJobAdminRead(BaseModel):
    """Backoffice view of one download job (cross-user, read-only)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    book_id: UUID
    chapter_from: int
    chapter_to: int
    provider: str
    voice: str
    status: str
    ready_count: int
    total_count: int
    error: str | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
```

Append to `DownloadRepository` in `backend/app/modules/downloads/repository.py` (ensure `func` is in the sqlalchemy import):

```python
    async def list_jobs_admin(
        self, *, status: str | None, limit: int, offset: int
    ) -> tuple[list[DownloadJob], int]:
        """Backoffice page over ALL users' jobs, newest first (no expiry purge)."""
        conditions = [] if status is None else [DownloadJob.status == status]
        total_stmt = select(func.count()).select_from(DownloadJob).where(*conditions)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(DownloadJob)
            .where(*conditions)
            .order_by(DownloadJob.created_at.desc(), DownloadJob.id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows), total
```

Append to `DownloadService` in `backend/app/modules/downloads/service.py` (extend the schemas import with `DownloadJobAdminRead`):

```python
    async def list_jobs_admin(
        self, *, status: str | None, limit: int, offset: int
    ) -> tuple[list[DownloadJobAdminRead], int]:
        """Backoffice: all users' jobs, read-only — deliberately no purge."""
        jobs, total = await self._repo.list_jobs_admin(
            status=status, limit=limit, offset=offset
        )
        return [DownloadJobAdminRead.model_validate(job) for job in jobs], total
```

- [ ] **Step 5: Add the jobs router and include it**

```python
# backend/app/modules/admin/jobs_router.py
"""Backoffice read-only job monitor routes. HTTP only; logic in owning services."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_admin
from app.modules.admin.params import PageParams
from app.modules.admin.schemas import Page
from app.modules.downloads.schemas import DownloadJobAdminRead
from app.modules.downloads.service import DownloadService
from app.modules.scraping.schemas import ScrapeJobAdminRead
from app.modules.scraping.service import ScrapingService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/jobs")


def _scraping(session: Annotated[AsyncSession, Depends(get_db)]) -> ScrapingService:
    return ScrapingService(session)


def _downloads(session: Annotated[AsyncSession, Depends(get_db)]) -> DownloadService:
    return DownloadService(session)


@router.get("/scraping")
async def list_scraping_jobs(
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[ScrapingService, Depends(_scraping)],
    page: Annotated[PageParams, Depends()],
    status: str | None = None,
) -> Page[ScrapeJobAdminRead]:
    """All users' scraping jobs, newest first (read-only)."""
    items, total = await service.list_jobs_admin(
        status=status, limit=page.limit, offset=page.offset
    )
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/downloads")
async def list_download_jobs(
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[DownloadService, Depends(_downloads)],
    page: Annotated[PageParams, Depends()],
    status: str | None = None,
) -> Page[DownloadJobAdminRead]:
    """All users' download jobs, newest first (read-only)."""
    items, total = await service.list_jobs_admin(
        status=status, limit=page.limit, offset=page.offset
    )
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)
```

In `backend/app/modules/admin/router.py`, add:

```python
from app.modules.admin.jobs_router import router as jobs_router
```

and:

```python
router.include_router(jobs_router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/admin -v`
Expected: PASS (4 jobs tests + matrix includes both jobs routes)

- [ ] **Step 7: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add backoffice cross-user jobs monitor API\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 2: Jobs monitor screen

**Files:**
- Create: `frontend/src/features/admin/api/jobs.ts`
- Create: `frontend/src/features/admin/hooks/useAdminJobs.ts`
- Create: `frontend/src/features/admin/components/jobs/JobsPage.tsx`
- Create: `frontend/src/features/admin/components/jobs/ScrapingJobsTable.tsx`
- Create: `frontend/src/features/admin/components/jobs/DownloadJobsTable.tsx`
- Modify: `frontend/src/features/admin/index.ts`
- Modify: `frontend/src/app/App.tsx` (swap the jobs placeholder)

**Interfaces:**
- Consumes: Task 1 routes; foundation's `usePageState`, `PaginationControls`, `Page<T>`.
- Produces: `JobsPage` export. Read-only — no job actions by design.

- [ ] **Step 1: Implement API + hooks**

```typescript
// frontend/src/features/admin/api/jobs.ts
import type { Page } from '@/features/admin/types'
import { apiGet } from '@/shared/lib/api'

/** Mirrors ScrapeJobAdminRead (scraping/schemas.py) exactly. */
export type ScrapeJob = {
  id: string
  user_id: string
  book_id: string | null
  book_title: string | null
  start_url: string
  mode: string
  status: string
  chapters_done: number
  chapter_from: number | null
  chapter_to: number | null
  message: string | null
  error: string | null
  created_at: string
  updated_at: string
}

/** Mirrors DownloadJobAdminRead (downloads/schemas.py) exactly. */
export type DownloadJob = {
  id: string
  user_id: string
  book_id: string
  chapter_from: number
  chapter_to: number
  provider: string
  voice: string
  status: string
  ready_count: number
  total_count: number
  error: string | null
  expires_at: string | null
  created_at: string
  updated_at: string
}

function jobsQuery(status: string, limit: number, offset: number): string {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (status) {
    params.set('status', status)
  }
  return params.toString()
}

export function fetchScrapingJobs(
  status: string,
  limit: number,
  offset: number,
): Promise<Page<ScrapeJob>> {
  return apiGet(`/api/admin/jobs/scraping?${jobsQuery(status, limit, offset)}`)
}

export function fetchDownloadJobs(
  status: string,
  limit: number,
  offset: number,
): Promise<Page<DownloadJob>> {
  return apiGet(`/api/admin/jobs/downloads?${jobsQuery(status, limit, offset)}`)
}
```

```typescript
// frontend/src/features/admin/hooks/useAdminJobs.ts
import { useQuery } from '@tanstack/react-query'
import { fetchDownloadJobs, fetchScrapingJobs } from '@/features/admin/api/jobs'

export function useScrapingJobs(status: string, limit: number, offset: number) {
  return useQuery({
    queryKey: ['admin', 'jobs', 'scraping', status, limit, offset],
    queryFn: () => fetchScrapingJobs(status, limit, offset),
  })
}

export function useDownloadJobs(status: string, limit: number, offset: number) {
  return useQuery({
    queryKey: ['admin', 'jobs', 'downloads', status, limit, offset],
    queryFn: () => fetchDownloadJobs(status, limit, offset),
  })
}
```

- [ ] **Step 2: Implement the components**

```tsx
// frontend/src/features/admin/components/jobs/JobsPage.tsx
import { useState } from 'react'
import { DownloadJobsTable } from './DownloadJobsTable'
import { ScrapingJobsTable } from './ScrapingJobsTable'

const TAB = 'rounded-md px-2.5 py-1 text-sm'

export function JobsPage() {
  const [kind, setKind] = useState<'scraping' | 'downloads'>('scraping')
  const [status, setStatus] = useState('')
  return (
    <section>
      <h1 className="mb-1 text-lg font-semibold">Jobs monitor</h1>
      <p className="mb-3 text-sm text-muted-foreground">
        Read-only view across all users. Cancel/retry live in the owning features.
      </p>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          className={`${TAB} ${kind === 'scraping' ? 'bg-muted font-medium' : 'text-muted-foreground'}`}
          onClick={() => setKind('scraping')}
        >
          Scraping
        </button>
        <button
          type="button"
          className={`${TAB} ${kind === 'downloads' ? 'bg-muted font-medium' : 'text-muted-foreground'}`}
          onClick={() => setKind('downloads')}
        >
          Downloads
        </button>
        <input
          className="ml-auto rounded border border-border bg-background px-2 py-1 text-sm"
          placeholder="Filter by status"
          aria-label="Filter by status"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        />
      </div>
      {kind === 'scraping' ? (
        <ScrapingJobsTable status={status} />
      ) : (
        <DownloadJobsTable status={status} />
      )}
    </section>
  )
}
```

```tsx
// frontend/src/features/admin/components/jobs/ScrapingJobsTable.tsx
import { PaginationControls } from '@/features/admin/components/common/PaginationControls'
import { useScrapingJobs } from '@/features/admin/hooks/useAdminJobs'
import { usePageState } from '@/features/admin/hooks/usePageState'

export function ScrapingJobsTable({ status }: { status: string }) {
  const page = usePageState(25)
  const { data } = useScrapingJobs(status, page.limit, page.offset)
  if (!data) {
    return <p className="text-sm text-muted-foreground">Loading scraping jobs…</p>
  }
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-muted-foreground">
            <tr>
              <th className="px-2 py-1.5 font-medium">Book</th>
              <th className="px-2 py-1.5 font-medium">User</th>
              <th className="px-2 py-1.5 font-medium">Status</th>
              <th className="px-2 py-1.5 font-medium">Progress</th>
              <th className="px-2 py-1.5 font-medium">Updated</th>
              <th className="px-2 py-1.5 font-medium">Message</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((job) => (
              <tr key={job.id} className="border-t border-border/60">
                <td className="px-2 py-1.5">{job.book_title ?? job.start_url}</td>
                <td className="px-2 py-1.5 font-mono text-xs">{job.user_id.slice(0, 8)}</td>
                <td className="px-2 py-1.5">{job.status}</td>
                <td className="px-2 py-1.5 tabular-nums">{job.chapters_done} ch</td>
                <td className="px-2 py-1.5 text-muted-foreground">
                  {new Date(job.updated_at).toLocaleString()}
                </td>
                <td className="px-2 py-1.5 text-xs text-muted-foreground">
                  {job.error ?? job.message ?? '—'}
                </td>
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
// frontend/src/features/admin/components/jobs/DownloadJobsTable.tsx
import { PaginationControls } from '@/features/admin/components/common/PaginationControls'
import { useDownloadJobs } from '@/features/admin/hooks/useAdminJobs'
import { usePageState } from '@/features/admin/hooks/usePageState'

export function DownloadJobsTable({ status }: { status: string }) {
  const page = usePageState(25)
  const { data } = useDownloadJobs(status, page.limit, page.offset)
  if (!data) {
    return <p className="text-sm text-muted-foreground">Loading download jobs…</p>
  }
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-muted-foreground">
            <tr>
              <th className="px-2 py-1.5 font-medium">User</th>
              <th className="px-2 py-1.5 font-medium">Chapters</th>
              <th className="px-2 py-1.5 font-medium">Provider</th>
              <th className="px-2 py-1.5 font-medium">Status</th>
              <th className="px-2 py-1.5 font-medium">Progress</th>
              <th className="px-2 py-1.5 font-medium">Created</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((job) => (
              <tr key={job.id} className="border-t border-border/60">
                <td className="px-2 py-1.5 font-mono text-xs">{job.user_id.slice(0, 8)}</td>
                <td className="px-2 py-1.5 tabular-nums">
                  {job.chapter_from}–{job.chapter_to}
                </td>
                <td className="px-2 py-1.5">{job.provider}</td>
                <td className="px-2 py-1.5">{job.error ?? job.status}</td>
                <td className="px-2 py-1.5 tabular-nums">
                  {job.ready_count}/{job.total_count}
                </td>
                <td className="px-2 py-1.5 text-muted-foreground">
                  {new Date(job.created_at).toLocaleString()}
                </td>
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

- [ ] **Step 3: Wire the route and barrel**

Append to `frontend/src/features/admin/index.ts`:

```typescript
export { JobsPage } from './components/jobs/JobsPage'
```

In `frontend/src/app/App.tsx`: extend the `@/features/admin` import with `JobsPage` and change the jobs route to:

```tsx
<Route path="jobs" element={<JobsPage />} />
```

(If this is the last screen to land, `AdminPlaceholder` is now unused in `App.tsx`; deleting it is optional cleanup outside this plan.)

- [ ] **Step 4: Gates + commit**

```bash
cd frontend && npm run lint && npm run build && npm run test && cd ..
printf 'feat: add backoffice jobs monitor screen\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```
