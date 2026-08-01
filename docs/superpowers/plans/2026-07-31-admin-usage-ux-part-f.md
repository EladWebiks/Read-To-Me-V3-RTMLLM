# Admin Usage UX (Part F) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface quota rejections on the admin usage screen, convert the by-user month/quota columns to bounded hybrid reads, add per-user quota overrides (the only per-user lever pre-Stripe), and make the users-screen tier dropdown registry-driven.

**Architecture:** Rejection aggregates come from the usage module's own tables (rolled `rejected_*` metrics + today's raw `quota_rejections`) via new `UsageReadService` period helpers, composed into the existing admin usage endpoints. The B6/C5 `_decorate_rows` month scans switch to `rolled_user_table` + today-tail set-variants (the D6 transformation applied to the decorate step). Overrides are a quotas-owned sparse table `user_quota_overrides` merged inside `QuotaService.limits_for` (admin exempt → user override → tier row → unlimited), so every enforcement point and `/api/me/usage` inherit them with zero changes; admin CRUD follows the membership-quotas set/clear pattern and the UI is a per-row dialog on the Users screen. The hardcoded `MEMBERSHIPS` const is replaced by tiers served from Part A's membership-policies endpoint.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, pydantic v2, React 19, react-query, vitest.

**Spec:** `docs/superpowers/specs/2026-07-31-quota-usage-ux-design.md` (approved). Read §3.5 before starting.

**Sequencing — PREREQUISITES ARE PLANS, NOT CODE (verified 2026-07-31: none of Parts A–D is implemented).** Per-task dependencies differ: Tasks 1–2 need **Part D** merged (rejection recording + rollup); Task 3 needs **Part D Task 6 + Part C Task 5** (the decorate step it converts); Tasks 4–6 need only **Part B** (quotas module); Task 7 needs **Part A Tasks 5–6** (membership-policies API/screen). Part E is NOT a prerequisite (either may land first). Each task's Step 0 verifies its own prerequisites; if a merged A–D name diverged from its plan, reconcile to the merged name and note it.

## Global Constraints

- Backend gates per task (from `backend/`, **via the Bash tool** — `uv` is not on the PowerShell PATH): `uv run ruff check . --fix && uv run ruff format .`, `uv run mypy .`, `uv run pytest -m "unit or integration"`.
- Frontend gates (from `frontend/`): `npm run lint`, `npm run build`, `npm run test`.
- Integration tests need Postgres/Redis/MinIO and `TEST_DATABASE_URL` pointing at a separate test DB — never the app DB. Apply new migrations to the test DB too (`DATABASE_URL=<TEST_DATABASE_URL value> uv run alembic upgrade head`).
- Commit per task via `/tmp/msg.txt` + `bash scripts/git-commit-clean.sh /tmp/msg.txt`; verify `git log -1 --format=%B`. **Never** add attribution trailers.
- Ruff limits: complexity ≤10, statements ≤20, branches ≤6, args ≤6. Frontend ESLint: file ≤110 lines, function ≤60 lines, nesting ≤3.
- Tests build settings via `tests/factories.py::make_settings`.
- Module direction: the admin aggregation router composes **services** only; `quotas` stays a leaf (imports `users`, never domain/orchestration modules); `user_quota_overrides` is a quotas-owned table.
- Semantics (spec, locked): resolution is admin exempt → user override → tier row → unlimited (specificity-wins; looser and tighter overrides both allowed); rejection aggregates are hybrid (rolled `rejected_*` + today raw) over the **selected period**; response shapes for existing endpoints stay backward-compatible (new fields only).

---

### Task 1: Rejection aggregates in the admin usage API

**Files:**
- Modify: `backend/app/modules/usage/repository.py` (raw rejection counters)
- Modify: `backend/app/modules/usage/read_service.py` (hybrid period helpers)
- Modify: `backend/app/modules/admin/schemas.py` (`AdminUsageOverview`, `AdminUserUsageRead`)
- Modify: `backend/app/modules/admin/usage_router.py` (compose)
- Test: `backend/tests/usage/test_admin_rejections_api.py`

**Interfaces:**
- Consumes (planned by Part D; Step 0 verifies): `QuotaRejection` model, `REJECTION_METRICS: dict[QuotaKind, UsageMetric]`, `UsageRepository.rolled_totals(metrics, *, start_day, end_day)`, `rolled_user_table(*, start_day, end_day)`, `UsageReadService.hybrid_split(now)`; C5's `_RowContext` + `_decorate_rows` in `admin/usage_router.py`.
- Produces (used by Task 2):
  - `UsageRepository.rejection_counts(*, start: datetime, end: datetime) -> dict[str, int]` (by kind) and `rejection_counts_by_user(*, start: datetime, end: datetime) -> dict[UUID, int]`
  - `UsageReadService.period_rejections(*, period_start, period_end, now) -> tuple[int, dict[str, int]]` and `period_rejections_by_user(*, period_start, period_end, now) -> dict[UUID, int]` — hybrid: rolled days `[start_day, min(end_day, today))` + raw tail `[max(period_start, today_start), period_end)` (same range split as D6)
  - `GET /api/admin/usage/summary` gains `rejections: int` + `rejections_by_kind: dict[str, int]`; `/by-user` items gain `period_rejections: int`

- [ ] **Step 0: Verify prerequisites**

```bash
uv run python -c "from app.modules.usage.models import QuotaRejection; from app.modules.usage.kinds import REJECTION_METRICS; from app.modules.usage.read_service import UsageReadService; print('ok')"
grep -n "_RowContext\|_decorate_rows" backend/app/modules/admin/usage_router.py
```

Expected: `ok` + both symbols. If missing, **STOP — Part D / C5 not merged.**

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/usage/test_admin_rejections_api.py
"""Admin usage endpoints expose hybrid rejection counts (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from app.core.config import get_settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.quotas.kinds import QuotaKind
from app.modules.usage.kinds import REJECTION_METRICS, UsageFact
from app.modules.usage.models import QuotaRejection, UsageDaily
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
        for model in (UsageDaily, QuotaRejection):
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


async def _seed() -> tuple[UUID, UUID]:
    """Admin + a reader with 2 rolled rejections (yesterday) + 1 raw (today)."""
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        admin = User(
            username="rej-admin", email="rej-admin@example.com", password_hash=None,
            google_sub="rej-admin-sub", is_admin=True,
        )
        reader = User(
            username="rej-reader", email="rej-reader@example.com", password_hash=None,
            google_sub="rej-reader-sub", is_admin=False,
        )
        session.add_all([admin, reader])
        await session.flush()
        yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
        await UsageRepository(session).replace_day(
            yesterday,
            [UsageFact(reader.id, REJECTION_METRICS[QuotaKind.LLM_TOKENS], 2.0)],
        )
        session.add(
            QuotaRejection(user_id=reader.id, quota_kind="audio_chapters", source="api")
        )
        await session.commit()
        ids = (admin.id, reader.id)
    await engine.dispose()
    return ids


def _login(client: AsyncClient, user_id: UUID, username: str) -> None:
    token = create_access_token(user_id=user_id, username=username, settings=get_settings())
    client.cookies.set(COOKIE_NAME, token, domain=_HOST, path="/")


def _period() -> str:
    now = datetime.now(UTC)
    start = (now - timedelta(days=3)).strftime("%Y-%m-%dT00:00:00Z")
    end = (now + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
    return f"?from={start}&to={end}"


@pytest.mark.integration
async def test_summary_and_by_user_carry_hybrid_rejections(client: AsyncClient) -> None:
    admin_id, reader_id = await _seed()
    _login(client, admin_id, "rej-admin")

    summary = (await client.get("/api/admin/usage/summary" + _period())).json()
    assert summary["rejections"] == 3  # 2 rolled + 1 raw today
    assert summary["rejections_by_kind"]["llm_tokens"] == 2
    assert summary["rejections_by_kind"]["audio_chapters"] == 1

    by_user = (await client.get("/api/admin/usage/by-user" + _period())).json()
    reader_row = next(
        r for r in by_user["items"] if r["user_id"] == str(reader_id)
    )
    assert reader_row["period_rejections"] == 3
```

**Note:** if the reader has no `llm_executions` rows, the by-user page may not include them — seed one zero-ish `LlmExecution` for the reader if the merged D6 by-user composition only lists LLM-active users, and add a comment. (Check the merged behavior; the assertion target is the column value, not the listing rule.)

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/usage/test_admin_rejections_api.py -v`
Expected: FAIL — `KeyError: 'rejections'`.

- [ ] **Step 3: Repository counters**

Append to `UsageRepository` (imports: `func`, `QuotaRejection` already in the module):

```python
    async def rejection_counts(
        self, *, start: datetime, end: datetime
    ) -> dict[str, int]:
        """Raw quota_rejections per kind for [start, end) — the today-tail."""
        stmt = (
            select(QuotaRejection.quota_kind, func.count())
            .where(QuotaRejection.created_at >= start, QuotaRejection.created_at < end)
            .group_by(QuotaRejection.quota_kind)
        )
        rows = (await self._session.execute(stmt)).all()
        return {str(row[0]): int(row[1]) for row in rows}

    async def rejection_counts_by_user(
        self, *, start: datetime, end: datetime
    ) -> dict[UUID, int]:
        """Raw quota_rejections per user for [start, end) — the today-tail."""
        stmt = (
            select(QuotaRejection.user_id, func.count())
            .where(QuotaRejection.created_at >= start, QuotaRejection.created_at < end)
            .group_by(QuotaRejection.user_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return {row[0]: int(row[1]) for row in rows}
```

- [ ] **Step 4: Hybrid period helpers on `UsageReadService`**

```python
    async def period_rejections(
        self, *, period_start: datetime, period_end: datetime, now: datetime
    ) -> tuple[int, dict[str, int]]:
        """Hybrid rejection counts for an arbitrary [from, to) period.

        Rolled rejected_* rows cover [start_day, min(end_day, today));
        raw quota_rejections cover [max(period_start, today_start), period_end).
        Same range split as the D6 admin aggregates.
        """
        today, today_start = self.hybrid_split(now)
        by_kind: dict[str, int] = {}
        rolled_end = min(period_end.date(), today)
        if period_start.date() < rolled_end:
            metric_to_kind = {m: k for k, m in REJECTION_METRICS.items()}
            totals = await self._repo.rolled_totals(
                tuple(REJECTION_METRICS.values()),
                start_day=period_start.date(),
                end_day=rolled_end,
            )
            for metric, amount in totals.items():
                by_kind[metric_to_kind[metric].value] = int(amount)
        raw_start = max(period_start, today_start)
        if raw_start < period_end:
            for kind, count in (
                await self._repo.rejection_counts(start=raw_start, end=period_end)
            ).items():
                by_kind[kind] = by_kind.get(kind, 0) + count
        return sum(by_kind.values()), by_kind

    async def period_rejections_by_user(
        self, *, period_start: datetime, period_end: datetime, now: datetime
    ) -> dict[UUID, int]:
        """Per-user hybrid rejection totals for an arbitrary [from, to) period."""
        today, today_start = self.hybrid_split(now)
        result: dict[UUID, int] = {}
        rolled_end = min(period_end.date(), today)
        if period_start.date() < rolled_end:
            rejection_metrics = set(REJECTION_METRICS.values())
            table = await self._repo.rolled_user_table(
                start_day=period_start.date(), end_day=rolled_end
            )
            for user_id, metrics in table.items():
                amount = sum(v for m, v in metrics.items() if m in rejection_metrics)
                if amount:
                    result[user_id] = int(amount)
        raw_start = max(period_start, today_start)
        if raw_start < period_end:
            for user_id, count in (
                await self._repo.rejection_counts_by_user(start=raw_start, end=period_end)
            ).items():
                result[user_id] = result.get(user_id, 0) + count
        return result
```

(Match `rolled_totals`/`rolled_user_table` signatures to the merged D Task 1 code; add the `REJECTION_METRICS` import.)

- [ ] **Step 5: Compose into the admin endpoints**

In `backend/app/modules/admin/schemas.py`: `AdminUsageOverview` gains `rejections: int = 0` and `rejections_by_kind: dict[str, int] = {}`; `AdminUserUsageRead` gains `period_rejections: int = 0`.

In `backend/app/modules/admin/usage_router.py`: the summary handler calls `UsageReadService(session).period_rejections(period_start=..., period_end=..., now=datetime.now(UTC))` and fills the two fields; `_decorate_rows` (C5's `_RowContext`) gains a `rejections: dict[UUID, int]` lookup filled from `period_rejections_by_user` **with the selected period** (thread `period` into `_decorate_rows` — it already receives the request-scoped values; keep the dataclass-bundle pattern to respect the 6-arg limit) and `_decorated_row` sets `period_rejections=ctx.rejections.get(row.user_id, 0)`.

- [ ] **Step 6: Run the test to verify it passes, then gates + commit**

```bash
uv run pytest tests/usage/test_admin_rejections_api.py -v
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: expose hybrid quota-rejection counts in admin usage API\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 2: Rejections on the usage screen

**Files:**
- Modify: `frontend/src/features/admin/api/usage.ts` (types)
- Modify: `frontend/src/features/admin/components/usage/UsageSummaryTiles.tsx` (tile + breakdown)
- Modify: `frontend/src/features/admin/components/usage/ByUserTable.tsx` (or its extracted `ByUserRow`) (column)
- Modify: `frontend/src/features/admin/components/usage/UsagePage.test.tsx` (mocks)

**Interfaces:**
- Consumes: Task 1's fields (`rejections`, `rejections_by_kind`, `period_rejections`); existing `StatTile` and `BreakdownTable` components.
- Produces: a "Rejections" stat tile, a "Rejections by kind" list, and a per-user "Rejections" column.

- [ ] **Step 1: Extend the types**

In `frontend/src/features/admin/api/usage.ts`:

```typescript
export type UsageOverview = UsageBreakdown & {
  period_start: string
  period_end: string
  by_model: ModelBreakdown[]
  by_task: TaskBreakdown[]
  rejections: number
  rejections_by_kind: Record<string, number>
}
```

(Keep the existing shape; only the two fields are new.) Add `period_rejections: number` to `UserUsage`.

- [ ] **Step 2: Render tile + breakdown + column**

In `UsageSummaryTiles.tsx`: add `<StatTile label="Rejections" value={data.rejections.toLocaleString()} />` to the tile grid, and below the two existing breakdown tables render the kinds list (reuse the muted table styling; `BreakdownTable` expects token columns, so a rejections list is a simple two-column table):

```tsx
{Object.keys(data.rejections_by_kind).length > 0 && (
  <div className="rounded-xl border p-3">
    <h3 className="mb-2 text-sm font-medium">Rejections by kind</h3>
    <table className="w-full text-sm">
      <tbody>
        {Object.entries(data.rejections_by_kind).map(([kind, count]) => (
          <tr key={kind}>
            <td className="py-1 text-muted-foreground">{kind}</td>
            <td className="py-1 text-right">{count.toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
)}
```

In the by-user table: header `<th className="px-2 py-1.5 font-medium">Rejections</th>` after the C5 "Jobs (month)" column and cell `<td className="px-2 py-1.5">{row.period_rejections.toLocaleString()}</td>`. If the file crosses 110 lines, extract `ByUserRow` (C5 may already have).

- [ ] **Step 3: Update mocks, gates, commit**

Extend every mocked overview/row in `UsagePage.test.tsx` with `rejections: 0`, `rejections_by_kind: {}`, `period_rejections: 0`; add one assertion that a non-zero mocked `rejections` renders in the tile.

```bash
npm run test
npm run lint
npm run build
printf 'feat: show quota rejections on admin usage screen\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 3: Hybrid month/quota columns in `_decorate_rows`

**Files:**
- Modify: `backend/app/modules/admin/usage_router.py` (`_decorate_rows` month lookups)
- Test: `backend/tests/usage/test_admin_month_columns_hybrid.py`

**Interfaces:**
- Consumes (Step 0 verifies): `UsageReadService.rolled_user_table(*, start_day, end_day)` + `hybrid_split` (D1), `KIND_METRICS` (D1), the B6/C5 today-capable set-variants — `LlmService.usage_for_users_admin(user_ids, *, period_start, period_end)`, `DownloadService.month_chapters_for_users(...)`, `ScrapingService.month_chapters_for_users(...)`, `ImportService.month_imports_for_users(...)` — and C5's `_RowContext`.
- Produces: identical `AdminUserUsageRead` month fields (`month_tokens`, `month_cost`, `month_audio_chapters`, `month_scrape_chapters`, `month_epub_imports`) computed as rolled closed month days + today tails. **Response shape unchanged.**

- [ ] **Step 0: Verify prerequisites**

```bash
grep -n "month_chapters_for_users\|month_imports_for_users\|usage_for_users_admin" backend/app/modules/downloads/service.py backend/app/modules/scraping/service.py backend/app/modules/imports/service.py backend/app/modules/llm/service.py
grep -n "rolled_user_table\|KIND_METRICS" backend/app/modules/usage/read_service.py backend/app/modules/usage/kinds.py
```

Expected: all present (use merged names if C5/D shipped variants).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/usage/test_admin_month_columns_hybrid.py
"""By-user month columns count rolled closed days with no raw rows (needs Postgres).

Equivalence proof (spec §7.7): raw-only seeding keeps today's values identical;
rolled-only seeding (no raw rows for the closed day) MUST now appear too —
the raw-scan implementation would return 0 for it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from uuid import UUID

import pytest
from app.core.config import get_settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.llm.models import LlmExecution
from app.modules.quotas.service import QuotaService
from app.modules.usage.kinds import UsageFact, UsageMetric
from app.modules.usage.models import UsageDaily
from app.modules.usage.repository import UsageRepository
from app.modules.users.models import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.dbcleanup import clear_users

_HOST = "test.local"
BASE = "/api/admin/usage/by-user"


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
        for model in (UsageDaily, LlmExecution):
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
    """Admin + reader: rolled tokens on the month's first day + raw tokens today."""
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        admin = User(
            username="mc-admin", email="mc-admin@example.com", password_hash=None,
            google_sub="mc-admin-sub", is_admin=True,
        )
        reader = User(
            username="mc-reader", email="mc-reader@example.com", password_hash=None,
            google_sub="mc-reader-sub", is_admin=False,
        )
        session.add_all([admin, reader])
        await session.flush()
        now = datetime.now(UTC)
        month_start, _ = QuotaService.current_month_window(now)
        if month_start.date() != now.date():
            await UsageRepository(session).replace_day(
                month_start.date(),
                [
                    UsageFact(reader.id, UsageMetric.LLM_TOKENS_IN, 300.0),
                    UsageFact(reader.id, UsageMetric.AUDIO_CHAPTERS, 7.0),
                ],
            )
        session.add(
            LlmExecution(
                user_id=reader.id, task="chat_tools", provider="gemini", model="m",
                tokens_in=100, tokens_out=0, cost=0.5, latency_ms=10, status="ok",
            )
        )
        await session.commit()
        admin_id = admin.id
    await engine.dispose()
    return admin_id


@pytest.mark.integration
async def test_month_columns_are_hybrid(client: AsyncClient) -> None:
    admin_id = await _seed()
    token = create_access_token(user_id=admin_id, username="mc-admin", settings=get_settings())
    client.cookies.set(COOKIE_NAME, token, domain=_HOST, path="/")

    now = datetime.now(UTC)
    on_day_one = QuotaService.current_month_window(now)[0].date() == now.date()
    query = f"?from={now.year}-01-01T00:00:00Z&to={now.year + 1}-01-01T00:00:00Z"
    rows = (await client.get(BASE + query)).json()["items"]
    reader_row = next(r for r in rows if r["username"] == "mc-reader")
    assert reader_row["month_tokens"] == (100 if on_day_one else 400)  # rolled 300 + today 100
    assert reader_row["month_audio_chapters"] == (0 if on_day_one else 7)  # rolled-only
    assert reader_row["month_cost"] == pytest.approx(0.5)  # today-tail only
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/usage/test_admin_month_columns_hybrid.py -v`
Expected: FAIL — `month_tokens == 100` / `month_audio_chapters == 0` (raw scans ignore rolled rows).

- [ ] **Step 3: Convert the decorate lookups**

In `usage_router.py`, replace the full-month lookups in `_decorate_rows` with a rolled+tail composition (keep the `_RowContext` bundle; extract a helper so `_decorate_rows` stays within statement limits):

```python
async def _month_lookups(
    session: AsyncSession, service: LlmService, ids: list[UUID]
) -> _MonthLookups:
    """Hybrid month values: rolled closed days + today tails (spec §3.5)."""
    now = datetime.now(UTC)
    month_start, month_end = QuotaService.current_month_window(now)
    today, today_start = UsageReadService.hybrid_split(now)
    rolled: dict[UUID, dict[UsageMetric, float]] = {}
    if month_start.date() < today:
        table = await UsageReadService(session).rolled_user_table(
            start_day=month_start.date(), end_day=today
        )
        rolled = {uid: metrics for uid, metrics in table.items() if uid in set(ids)}
    tail_llm = await service.usage_for_users_admin(
        ids, period_start=today_start, period_end=month_end
    )
    audio = await DownloadService(session).month_chapters_for_users(
        ids, period_start=today_start, period_end=month_end
    )
    scrape = await ScrapingService(session).month_chapters_for_users(
        ids, period_start=today_start, period_end=month_end
    )
    imports = await ImportService(session).month_imports_for_users(
        ids, period_start=today_start, period_end=month_end
    )
    return _MonthLookups(rolled=rolled, tail_llm=tail_llm, audio=audio,
                         scrape=scrape, imports=imports)
```

with a frozen dataclass `_MonthLookups(rolled, tail_llm, audio, scrape, imports)` and per-row math:

```python
def _month_tokens(lk: _MonthLookups, uid: UUID) -> int:
    metrics = lk.rolled.get(uid, {})
    rolled = metrics.get(UsageMetric.LLM_TOKENS_IN, 0.0) + metrics.get(
        UsageMetric.LLM_TOKENS_OUT, 0.0
    )
    tail = lk.tail_llm.get(uid)
    return int(rolled) + ((tail.tokens_in + tail.tokens_out) if tail else 0)


def _month_metric(lk: _MonthLookups, uid: UUID, metric: UsageMetric,
                  tail: dict[UUID, int]) -> int:
    return int(lk.rolled.get(uid, {}).get(metric, 0.0)) + tail.get(uid, 0)
```

`month_cost` = rolled `LLM_COST_USD` + `tail.total_cost`; `month_audio_chapters` = `_month_metric(..., UsageMetric.AUDIO_CHAPTERS, lk.audio)`; scrape/imports likewise. Wire these into `_RowContext`/`_decorated_row` in place of the old dicts. The set-variant tails keep their existing month semantics — only the window shrinks to `[today_start, month_end)`.

- [ ] **Step 4: Run the new test AND the B6/C5 suite**

Run: `uv run pytest tests/usage/test_admin_month_columns_hybrid.py tests/quotas/test_admin_usage_quota_api.py -v`
Expected: ALL PASS (B6/C5's raw seeds are created "now" = today, served by the tail — outcomes unchanged).

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: hybrid month columns on admin by-user usage\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 4: `user_quota_overrides` table + resolution

**Files:**
- Modify: `backend/app/modules/quotas/models.py` (`UserQuotaOverride`)
- Modify: `backend/app/modules/quotas/repository.py` (override accessors)
- Modify: `backend/app/modules/quotas/service.py` (`limits_for` merge)
- Create: `backend/migrations/versions/<generated>_add_user_quota_overrides.py`
- Test: `backend/tests/quotas/test_user_quota_overrides.py`

**Interfaces:**
- Consumes: Part B Task 1's `MembershipQuota`, `QuotaLimits`, `QuotaService.limits_for`/`limits_for_user_id`, `QuotaKind`.
- Produces (used by Tasks 5–6; inherited automatically by every enforcement point and `/api/me/usage`):
  - `UserQuotaOverride` ORM model (table `user_quota_overrides`: `id` UUID PK, `user_id` FK NOT NULL indexed, `quota_kind` String(32), `limit_value` Float, `created_at`/`updated_at`, unique `(user_id, quota_kind)`)
  - Repository: `list_overrides_for_user(user_id) -> list[UserQuotaOverride]`, `get_override(user_id, quota_kind) -> UserQuotaOverride | None`, `add(row)`, `save(row)`, `delete(row)` (reusing the existing add/save/delete)
  - Resolution: **admin exempt → user override row → tier row → unlimited**

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/quotas/test_user_quota_overrides.py
"""Override resolution: user row beats tier row, looser or tighter (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota, UserQuotaOverride
from app.modules.quotas.service import QuotaService
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        for model in (UserQuotaOverride, MembershipQuota):
            await db.execute(delete(model))
        await db.commit()
        yield db
        await db.rollback()
        for model in (UserQuotaOverride, MembershipQuota):
            await db.execute(delete(model))
        await db.commit()
    await engine.dispose()


async def _user(session: AsyncSession, *, is_admin: bool = False) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(
            username=f"ovr_{uuid4().hex[:8]}", password="test-pass-123", is_admin=is_admin
        )
    )


async def _tier_quota(session: AsyncSession, kind: QuotaKind, limit: float) -> None:
    session.add(
        MembershipQuota(
            membership=Membership.FREE.value, quota_kind=kind.value, limit_value=limit
        )
    )
    await session.commit()


async def _override(
    session: AsyncSession, user_id: UUID, kind: str, limit: float
) -> None:
    session.add(UserQuotaOverride(user_id=user_id, quota_kind=kind, limit_value=limit))
    await session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_override_beats_tier_looser_and_tighter(session: AsyncSession) -> None:
    await _tier_quota(session, QuotaKind.LLM_TOKENS, 1000.0)
    await _tier_quota(session, QuotaKind.AUDIO_CHAPTERS, 50.0)
    user = await _user(session)
    await _override(session, user.id, QuotaKind.LLM_TOKENS.value, 9000.0)  # looser
    await _override(session, user.id, QuotaKind.AUDIO_CHAPTERS.value, 5.0)  # tighter

    limits = await QuotaService(session).limits_for(user)
    assert limits.limit(QuotaKind.LLM_TOKENS) == 9000.0
    assert limits.limit(QuotaKind.AUDIO_CHAPTERS) == 5.0
    assert limits.limit(QuotaKind.SCRAPE_CHAPTERS) is None  # neither row = unlimited


@pytest.mark.integration
@pytest.mark.asyncio
async def test_absent_override_falls_back_to_tier(session: AsyncSession) -> None:
    await _tier_quota(session, QuotaKind.LLM_TOKENS, 1000.0)
    user = await _user(session)
    limits = await QuotaService(session).limits_for(user)
    assert limits.limit(QuotaKind.LLM_TOKENS) == 1000.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_stays_exempt_despite_override(session: AsyncSession) -> None:
    user = await _user(session, is_admin=True)
    await _override(session, user.id, QuotaKind.LLM_TOKENS.value, 1.0)
    limits = await QuotaService(session).limits_for(user)
    assert limits.exempt is True
    assert limits.limit(QuotaKind.LLM_TOKENS) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unknown_kind_override_rows_are_skipped(session: AsyncSession) -> None:
    user = await _user(session)
    await _override(session, user.id, "retired_kind", 1.0)
    limits = await QuotaService(session).limits_for(user)
    assert limits.values == {}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_limits_for_user_id_sees_overrides(session: AsyncSession) -> None:
    user = await _user(session)
    await _override(session, user.id, QuotaKind.EPUB_IMPORTS.value, 2.0)
    limits = await QuotaService(session).limits_for_user_id(user.id)
    assert limits.limit(QuotaKind.EPUB_IMPORTS) == 2.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enforcement_honors_override_without_restart(session: AsyncSession) -> None:
    """Spec §7.5: a blocking tier limit is lifted by an override on the very
    next attempt — limits are read fresh per check (no cache, no restart).
    Uses the real downloads choke point (the D-Task-5 fixture pattern)."""
    from app.modules.books.schemas import BookCreate
    from app.modules.chapters.service import ChapterService
    from app.modules.downloads.schemas import DownloadCreate
    from app.modules.downloads.service import DownloadService
    from app.modules.library.service import LibraryService
    from app.modules.quotas.exceptions import QuotaExceededError

    user = await _user(session)
    book = await LibraryService(session).add_book(
        user.id, BookCreate(title="Override", author="A", description="d")
    )
    await ChapterService(session).upsert_by_number(book.id, 1, "Ch 1", "text " * 50)
    await session.commit()
    await _tier_quota(session, QuotaKind.AUDIO_CHAPTERS, 0.5)  # blocks the 1st chapter

    body = DownloadCreate(book_id=book.id, chapter_from=1, chapter_to=1)
    with pytest.raises(QuotaExceededError):
        await DownloadService(session).create(user.id, body)

    await _override(session, user.id, QuotaKind.AUDIO_CHAPTERS.value, 100.0)
    job = await DownloadService(session).create(user.id, body)  # next attempt passes
    assert job is not None
```

(Also delete any `download_jobs` rows this test creates in the fixture teardown if the merged suite's cleanup does not already cover them.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/quotas/test_user_quota_overrides.py -v`
Expected: FAIL — `ImportError: cannot import name 'UserQuotaOverride'`.

- [ ] **Step 3: Model + migration**

Append to `backend/app/modules/quotas/models.py` (imports: `ForeignKey`):

```python
class UserQuotaOverride(Base):
    """One per-user quota override. Row absent = the user's tier limit applies.

    Sparse like membership_quotas; specificity-wins like the per-turn chain
    (spec 2026-07-31-quota-usage-ux §3.5): admin exempt > user override >
    tier row > unlimited. Looser AND tighter overrides are both legal.
    """

    __tablename__ = "user_quota_overrides"
    __table_args__ = (
        UniqueConstraint("user_id", "quota_kind", name="uq_user_quota_overrides_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    quota_kind: Mapped[str] = mapped_column(String(32))
    limit_value: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

Migration: `uv run alembic revision -m "add user_quota_overrides"` (verify `uv run alembic heads` shows one head; `down_revision` = the current head). Fill:

```python
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.create_table(
        "user_quota_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quota_kind", sa.String(length=32), nullable=False),
        sa.Column("limit_value", sa.Float(), nullable=False,
                  comment="Row absent = tier limit applies"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("user_id", "quota_kind", name="uq_user_quota_overrides_pair"),
    )
    op.create_index(
        op.f("ix_user_quota_overrides_user_id"), "user_quota_overrides", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_quota_overrides_user_id"), table_name="user_quota_overrides")
    op.drop_table("user_quota_overrides")
```

Apply + reversibility check + test DB:

```bash
uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
DATABASE_URL=<your TEST_DATABASE_URL value> uv run alembic upgrade head
```

Register nothing new in `core/orm.py` — `quotas.models` is already imported (Part B Task 1).

- [ ] **Step 4: Repository + resolution merge**

Append to `MembershipQuotaRepository`:

```python
    async def list_overrides_for_user(self, user_id: UUID) -> list[UserQuotaOverride]:
        stmt = select(UserQuotaOverride).where(UserQuotaOverride.user_id == user_id)
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_override(self, user_id: UUID, quota_kind: str) -> UserQuotaOverride | None:
        stmt = select(UserQuotaOverride).where(
            UserQuotaOverride.user_id == user_id,
            UserQuotaOverride.quota_kind == quota_kind,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
```

In `QuotaService.limits_for`, merge overrides after the tier rows (override wins). Extract the shared "rows → values dict, skip unknown kinds" loop Part B wrote into a module helper so both call sites reuse it and the method stays within statement limits:

```python
def _values_from_rows(
    rows: Sequence[MembershipQuota] | Sequence[UserQuotaOverride],
) -> dict[QuotaKind, float]:
    """Keyed rows -> limits, skipping unknown kinds (fail-open, warned)."""
    values: dict[QuotaKind, float] = {}
    for row in rows:
        try:
            values[QuotaKind(row.quota_kind)] = row.limit_value
        except ValueError:
            logger.warning("ignoring unknown quota kind row", extra={"kind": row.quota_kind})
    return values
```

```python
    async def limits_for(self, user: UserRead) -> QuotaLimits:
        """Admin exempt > user override > tier row > unlimited (spec §3.5)."""
        if user.is_admin:
            return QuotaLimits(exempt=True, values={})
        values = _values_from_rows(await self._repo.list_for_membership(user.membership.value))
        values |= _values_from_rows(await self._repo.list_overrides_for_user(user.id))
        return QuotaLimits(exempt=False, values=values)
```

- [ ] **Step 5: Run tests, then the full quota suites**

Run: `uv run pytest tests/quotas/ tests/orchestration/test_monthly_quota_enforcement.py -v`
Expected: PASS — new tests green, every Part B/C quota test unchanged (no override rows seeded there).

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add per-user quota overrides above tier limits\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 5: Admin API for user quota overrides

**Files:**
- Modify: `backend/app/modules/quotas/schemas.py` (override DTOs)
- Modify: `backend/app/modules/quotas/service.py` (admin methods)
- Modify: `backend/app/modules/quotas/admin_router.py` (second router)
- Modify: `backend/app/main.py` (register)
- Test: `backend/tests/quotas/test_user_quota_api.py`

**Interfaces:**
- Consumes: Task 4's repository/model; `UserService.get_by_id` (raises `UserNotFoundError` → existing 404 mapping); `require_admin`; `KIND_REGISTRY`; `QuotaService.list_quotas` (tier rows, Part B Task 2).
- Produces (used by Task 6):
  - `GET /api/admin/users/{user_id}/quotas` → `{"membership": str, "kinds": [QuotaKindInfo...], "tier_limits": {"<kind>": float, ...}, "overrides": [{"quota_kind", "limit_value", "updated_at"}...]}` (`tier_limits` sparse — absent kind = unlimited at tier)
  - `PUT /api/admin/users/{user_id}/quotas/{kind}` body `{"limit_value": > 0}` → upsert; `DELETE …/{kind}` → 204, 404 if absent; unknown kind → 422; unknown user → 404
  - `QuotaService.user_quotas(user_id)`, `set_user_quota(user_id, kind, limit_value, *, actor_id)`, `clear_user_quota(user_id, kind, *, actor_id)`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/quotas/test_user_quota_api.py
"""Admin per-user quota override API (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota, UserQuotaOverride
from app.modules.users.membership import Membership
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
        for model in (UserQuotaOverride, MembershipQuota):
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


async def _seed_users() -> tuple[UUID, UUID]:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        admin = User(
            username="uq-admin", email="uq-admin@example.com", password_hash=None,
            google_sub="uq-admin-sub", is_admin=True,
        )
        reader = User(
            username="uq-reader", email="uq-reader@example.com", password_hash=None,
            google_sub="uq-reader-sub", is_admin=False,
        )
        session.add_all([admin, reader])
        await session.flush()
        session.add(
            MembershipQuota(
                membership=Membership.FREE.value,
                quota_kind=QuotaKind.LLM_TOKENS.value,
                limit_value=1000.0,
            )
        )
        await session.commit()
        ids = (admin.id, reader.id)
    await engine.dispose()
    return ids


@pytest.fixture
async def ctx(client: AsyncClient) -> tuple[AsyncClient, UUID]:
    admin_id, reader_id = await _seed_users()
    token = create_access_token(user_id=admin_id, username="uq-admin", settings=get_settings())
    client.cookies.set(COOKIE_NAME, token, domain=_HOST, path="/")
    return client, reader_id


@pytest.mark.integration
async def test_anonymous_gets_401(client: AsyncClient) -> None:
    assert (await client.get(f"/api/admin/users/{uuid4()}/quotas")).status_code == 401


@pytest.mark.integration
async def test_get_serves_registry_tier_limits_and_overrides(
    ctx: tuple[AsyncClient, UUID],
) -> None:
    client, reader_id = ctx
    body = (await client.get(f"/api/admin/users/{reader_id}/quotas")).json()
    assert body["membership"] == "free"
    assert {k["kind"] for k in body["kinds"]} == {k.value for k in QuotaKind}
    assert body["tier_limits"] == {"llm_tokens": 1000.0}  # sparse
    assert body["overrides"] == []


@pytest.mark.integration
async def test_put_upserts_and_delete_clears(ctx: tuple[AsyncClient, UUID]) -> None:
    client, reader_id = ctx
    base = f"/api/admin/users/{reader_id}/quotas"
    put = await client.put(f"{base}/llm_tokens", json={"limit_value": 9000})
    assert put.status_code == 200
    assert put.json()["limit_value"] == 9000

    replaced = await client.put(f"{base}/llm_tokens", json={"limit_value": 50})
    assert replaced.json()["limit_value"] == 50
    assert len((await client.get(base)).json()["overrides"]) == 1

    assert (await client.delete(f"{base}/llm_tokens")).status_code == 204
    assert (await client.delete(f"{base}/llm_tokens")).status_code == 404


@pytest.mark.integration
async def test_validation_and_unknown_user(ctx: tuple[AsyncClient, UUID]) -> None:
    client, reader_id = ctx
    base = f"/api/admin/users/{reader_id}/quotas"
    assert (await client.put(f"{base}/llm_tokens", json={"limit_value": 0})).status_code == 422
    assert (await client.put(f"{base}/not_a_kind", json={"limit_value": 5})).status_code == 422
    assert (
        await client.get(f"/api/admin/users/{uuid4()}/quotas")
    ).status_code == 404  # UserNotFoundError mapping
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/quotas/test_user_quota_api.py -v`
Expected: FAIL — 404 on the GET route for an existing user (routes missing) / assertion mismatch.

- [ ] **Step 3: Schemas + service methods + router**

Append to `backend/app/modules/quotas/schemas.py`:

```python
class UserQuotaOverrideRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    quota_kind: QuotaKind
    limit_value: float
    updated_at: datetime


class UserQuotasResponse(BaseModel):
    """Registry + the user's tier limits (sparse) + their override rows."""

    membership: Membership
    kinds: list[QuotaKindInfo]
    tier_limits: dict[str, float]
    overrides: list[UserQuotaOverrideRead]
```

Append to `QuotaService` (import `UserQuotaOverride`; `UserService` is already imported for `limits_for_user_id`):

```python
    async def user_quotas(self, user_id: UUID) -> tuple[Membership, dict[str, float], list[UserQuotaOverride]]:
        """(membership, sparse tier limits, override rows) for the admin dialog."""
        user = await UserService(self._session).get_by_id(user_id)  # 404s unknown ids
        tier_rows = await self._repo.list_for_membership(user.membership.value)
        tier_limits = {row.quota_kind: row.limit_value for row in tier_rows}
        overrides = await self._repo.list_overrides_for_user(user_id)
        return user.membership, tier_limits, overrides

    async def set_user_quota(
        self, user_id: UUID, kind: QuotaKind, limit_value: float, *, actor_id: UUID
    ) -> UserQuotaOverride:
        await UserService(self._session).get_by_id(user_id)
        row = await self._repo.get_override(user_id, kind.value)
        if row is None:
            row = UserQuotaOverride(
                user_id=user_id, quota_kind=kind.value, limit_value=limit_value
            )
            self._repo.add(row)
        else:
            row.limit_value = limit_value
        saved = await self._repo.save(row)
        logger.info(
            "user quota override set",
            extra={"user_id": str(user_id), "kind": kind.value,
                   "limit": limit_value, "actor": str(actor_id)},
        )
        return saved

    async def clear_user_quota(
        self, user_id: UUID, kind: QuotaKind, *, actor_id: UUID
    ) -> None:
        row = await self._repo.get_override(user_id, kind.value)
        if row is None:
            raise QuotaRuleNotFoundError(str(user_id), kind.value)
        await self._repo.delete(row)
        logger.info(
            "user quota override cleared",
            extra={"user_id": str(user_id), "kind": kind.value, "actor": str(actor_id)},
        )
```

Append a second router in `backend/app/modules/quotas/admin_router.py`:

```python
user_router = APIRouter(prefix="/admin/users", tags=["admin"])


@user_router.get("/{user_id}/quotas")
async def get_user_quotas(
    user_id: UUID,
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[QuotaService, Depends(_service)],
) -> UserQuotasResponse:
    """Registry + tier limits + this user's override rows."""
    membership, tier_limits, overrides = await service.user_quotas(user_id)
    return UserQuotasResponse(
        membership=membership,
        kinds=[
            QuotaKindInfo(kind=kind, label=m.label, unit=m.unit, window=m.window)
            for kind, m in KIND_REGISTRY.items()
        ],
        tier_limits=tier_limits,
        overrides=[UserQuotaOverrideRead.model_validate(row) for row in overrides],
    )


@user_router.put("/{user_id}/quotas/{kind}")
async def put_user_quota(
    user_id: UUID,
    kind: QuotaKind,
    body: QuotaLimitWrite,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[QuotaService, Depends(_service)],
) -> UserQuotaOverrideRead:
    row = await service.set_user_quota(user_id, kind, body.limit_value, actor_id=admin.id)
    return UserQuotaOverrideRead.model_validate(row)


@user_router.delete("/{user_id}/quotas/{kind}", status_code=204)
async def delete_user_quota(
    user_id: UUID,
    kind: QuotaKind,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[QuotaService, Depends(_service)],
) -> None:
    await service.clear_user_quota(user_id, kind, actor_id=admin.id)
```

In `backend/app/main.py`: `from app.modules.quotas.admin_router import user_router as user_quotas_router` + `app.include_router(user_quotas_router, prefix=api_prefix)`. Confirm `UserNotFoundError` already maps to 404 in `core/exceptions.py` (it does for the users module — the service raise reuses it).

- [ ] **Step 4: Run tests, gates, commit**

```bash
uv run pytest tests/quotas/test_user_quota_api.py -v
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: admin API for per-user quota overrides\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 6: Users-screen quota override dialog

**Files:**
- Create: `frontend/src/features/admin/api/userQuotas.ts`
- Create: `frontend/src/features/admin/hooks/useUserQuotas.ts`
- Create: `frontend/src/features/admin/components/users/UserQuotasDialog.tsx`
- Create: `frontend/src/features/admin/components/users/UserQuotasDialog.test.tsx`
- Modify: `frontend/src/features/admin/components/users/UserRow.tsx` ("Quotas" button)

**Interfaces:**
- Consumes: Task 5's endpoints; `Dialog*` from `@/shared/ui`; the `Page`/query-key conventions (`['admin', 'users', userId, 'quotas']`).
- Produces: a per-row "Quotas" button opening a registry-driven dialog; blank input = tier default (placeholder shows the tier limit or "Unlimited"), number = override.

- [ ] **Step 1: API client + hook**

```typescript
// frontend/src/features/admin/api/userQuotas.ts
import { apiDelete, apiGet, apiPut } from '@/shared/lib/api'
import type { QuotaKindInfo } from './membershipQuotas'

export type UserQuotaOverride = {
  quota_kind: string
  limit_value: number
  updated_at: string
}

export type UserQuotas = {
  membership: string
  kinds: QuotaKindInfo[]
  tier_limits: Record<string, number>
  overrides: UserQuotaOverride[]
}

export function fetchUserQuotas(userId: string): Promise<UserQuotas> {
  return apiGet(`/api/admin/users/${userId}/quotas`)
}

export function putUserQuota(
  userId: string,
  kind: string,
  limitValue: number,
): Promise<UserQuotaOverride> {
  return apiPut(`/api/admin/users/${userId}/quotas/${kind}`, { limit_value: limitValue })
}

export function deleteUserQuota(userId: string, kind: string): Promise<void> {
  return apiDelete(`/api/admin/users/${userId}/quotas/${kind}`)
}
```

(`QuotaKindInfo` comes from Part B Task 5's `membershipQuotas.ts`; if its merged name differs, import the merged one.)

```typescript
// frontend/src/features/admin/hooks/useUserQuotas.ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteUserQuota, fetchUserQuotas, putUserQuota } from '../api/userQuotas'

export const userQuotasKey = (userId: string) => ['admin', 'users', userId, 'quotas'] as const

export function useUserQuotas(userId: string, enabled: boolean) {
  return useQuery({
    queryKey: userQuotasKey(userId),
    queryFn: () => fetchUserQuotas(userId),
    enabled,
  })
}

export function useSetUserQuota(userId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ kind, limit }: { kind: string; limit: number | null }) =>
      limit === null ? deleteUserQuota(userId, kind) : putUserQuota(userId, kind, limit),
    onSettled: () => client.invalidateQueries({ queryKey: userQuotasKey(userId) }),
  })
}
```

- [ ] **Step 2: Write the failing dialog test**

```tsx
// frontend/src/features/admin/components/users/UserQuotasDialog.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import * as api from '../../api/userQuotas'
import { UserQuotasDialog } from './UserQuotasDialog'

vi.mock('../../api/userQuotas', async (importOriginal) => ({
  ...(await importOriginal<typeof api>()),
  fetchUserQuotas: vi.fn(async () => ({
    membership: 'free',
    kinds: [
      { kind: 'llm_tokens', label: 'AI tokens', unit: 'tokens', window: 'month' },
      { kind: 'audio_chapters', label: 'Audio chapters', unit: 'chapters', window: 'month' },
    ],
    tier_limits: { llm_tokens: 1000 },
    overrides: [{ quota_kind: 'audio_chapters', limit_value: 5, updated_at: '' }],
  })),
  putUserQuota: vi.fn(async () => ({ quota_kind: 'llm_tokens', limit_value: 9000, updated_at: '' })),
  deleteUserQuota: vi.fn(async () => undefined),
}))

function renderDialog() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <UserQuotasDialog userId="u1" username="reader" open onOpenChange={() => {}} />
    </QueryClientProvider>,
  )
}

describe('UserQuotasDialog', () => {
  it('renders registry kinds with tier placeholders and override values', async () => {
    renderDialog()
    const tokens = await screen.findByLabelText(/AI tokens/)
    expect(tokens).toHaveAttribute('placeholder', '1,000 (tier)')
    const audio = screen.getByLabelText(/Audio chapters/)
    expect(audio).toHaveValue('5')
  })

  it('saves a number as PUT and blank as DELETE on blur', async () => {
    renderDialog()
    const tokens = await screen.findByLabelText(/AI tokens/)
    fireEvent.change(tokens, { target: { value: '9000' } })
    fireEvent.blur(tokens)
    expect(api.putUserQuota).toHaveBeenCalledWith('u1', 'llm_tokens', 9000)

    const audio = screen.getByLabelText(/Audio chapters/)
    fireEvent.change(audio, { target: { value: '' } })
    fireEvent.blur(audio)
    expect(api.deleteUserQuota).toHaveBeenCalledWith('u1', 'audio_chapters')
  })
})
```

Run: `npm run test -- UserQuotasDialog` — expected FAIL (module not found).

- [ ] **Step 3: Implement the dialog + row button**

```tsx
// frontend/src/features/admin/components/users/UserQuotasDialog.tsx
import { Dialog, DialogContent, DialogHeader, DialogTitle, Input, Label } from '@/shared/ui'
import { useSetUserQuota, useUserQuotas } from '../../hooks/useUserQuotas'

type Props = {
  userId: string
  username: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

/** Registry-driven per-user overrides. Blank = tier default; number = override. */
export function UserQuotasDialog({ userId, username, open, onOpenChange }: Props) {
  const { data } = useUserQuotas(userId, open)
  const save = useSetUserQuota(userId)
  const overrideOf = (kind: string) =>
    data?.overrides.find((o) => o.quota_kind === kind)?.limit_value
  const onBlur = (kind: string, raw: string, hadOverride: boolean) => {
    const trimmed = raw.trim()
    if (trimmed === '') {
      if (hadOverride) save.mutate({ kind, limit: null })
      return
    }
    const value = Number(trimmed)
    if (Number.isFinite(value) && value > 0) save.mutate({ kind, limit: value })
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Quota overrides — {username}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          {data?.kinds.map((kind) => (
            <div key={kind.kind} className="space-y-1">
              <Label htmlFor={`quota-${kind.kind}`}>{kind.label}</Label>
              <Input
                id={`quota-${kind.kind}`}
                inputMode="decimal"
                defaultValue={overrideOf(kind.kind) ?? ''}
                placeholder={
                  kind.kind in (data?.tier_limits ?? {})
                    ? `${data!.tier_limits[kind.kind].toLocaleString('en-US')} (tier)`
                    : 'Unlimited (tier)'
                }
                onBlur={(e) =>
                  onBlur(kind.kind, e.target.value, overrideOf(kind.kind) !== undefined)
                }
              />
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
```

(Adjust `Dialog*` subcomponent names to the merged `shared/ui/dialog.tsx` exports; if the file crosses 110 lines, extract a `QuotaOverrideField` component.) In `UserRow.tsx`: add local `const [quotasOpen, setQuotasOpen] = useState(false)`, a small "Quotas" `Button` (variant matching the row's existing controls) that sets it true, and render `<UserQuotasDialog userId={user.id} username={user.username} open={quotasOpen} onOpenChange={setQuotasOpen} />`.

- [ ] **Step 4: Run tests, gates, commit**

```bash
npm run test
npm run lint
npm run build
printf 'feat: per-user quota override dialog on admin users screen\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 7: Registry-driven tier dropdown

**Files:**
- Modify: `frontend/src/features/admin/api/users.ts` (delete `MEMBERSHIPS`)
- Modify: `frontend/src/features/admin/components/users/UserRow.tsx` (options from served tiers)
- Modify: `frontend/src/features/admin/components/users/UsersPage.tsx` (fetch tiers once, pass down)
- Modify: the users-screen test file that mocks the API (extend mocks)

**Interfaces:**
- Consumes: Part A Task 5's `GET /api/admin/membership-policies` → `{"policies": [{membership, ...}], "inherited": {...}}` and whatever client/hook Part A Task 6 shipped for it (Step 0 finds it).
- Produces: the membership `<select>` options rendered from the served policies list; `MEMBERSHIPS` const **deleted** (grep-clean).

- [ ] **Step 0: Find Part A's client for the policies endpoint**

```bash
grep -rn "membership-policies" frontend/src/features/admin
```

Expected: an api file + hook from Part A Task 6 (e.g. `api/policies.ts` with `fetchMembershipPolicies` and a `useMembershipPolicies`-style hook). Reuse them. If only the api function exists, add the hook alongside the existing admin hook conventions:

```typescript
// frontend/src/features/admin/hooks/useMembershipList.ts (only if no hook exists)
import { useQuery } from '@tanstack/react-query'
import { fetchMembershipPolicies } from '../api/policies'

export function useMembershipList(): string[] {
  const { data } = useQuery({
    queryKey: ['admin', 'membership-policies'],
    queryFn: fetchMembershipPolicies,
    staleTime: 60_000,
  })
  return data?.policies.map((p) => p.membership) ?? []
}
```

- [ ] **Step 1: Swap the dropdown source**

In `UsersPage.tsx`: `const memberships = useMembershipList()` and pass `memberships` down to each `UserRow`. In `UserRow.tsx`, replace the `MEMBERSHIPS.map(...)` options with `memberships.map(...)`; while the list is empty (loading), render the user's current membership as the only option so the select never goes blank:

```tsx
{(memberships.length > 0 ? memberships : [user.membership]).map((tier) => (
  <option key={tier} value={tier}>
    {tier}
  </option>
))}
```

Delete `MEMBERSHIPS` from `api/users.ts`, then verify nothing references it:

```bash
grep -rn "MEMBERSHIPS" frontend/src
```

Expected: no hits.

- [ ] **Step 2: Update tests**

In the users-screen test file: mock the policies fetch (two tiers, e.g. `['free', 'plus']`) and assert both render as options; keep existing membership-patch assertions working (extend mocks, not assertions).

- [ ] **Step 3: Gates + commit**

```bash
npm run test
npm run lint
npm run build
printf 'feat: drive membership dropdown from served policies registry\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```
