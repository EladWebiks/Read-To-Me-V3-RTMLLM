# Non-LLM Quota Dimensions (Part C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce the non-LLM quota kinds — `audio_chapters` (MP3 generation), `storage_bytes` (retained MP3 bytes, standing), `scrape_chapters`, `epub_imports` — at each domain's job-creation choke point, surface them in the backoffice, and make sure users see friendly 429 messages.

**Architecture:** The kinds already exist in Part B's registry and admin UI — this plan only adds **meters and enforcement**. Each domain service measures its own usage via its own repository and calls `QuotaService.limits_for_user_id` + `enforce` (caller-metered; domain code never imports the orchestrator). `DownloadsService.create` covers the REST route *and* the `create_audio_download` LLM tool; `ScrapingService.create_job` covers REST *and* the HITL scrape tool; `ImportService.start` covers both import entrypoints. Two small migrations: `download_jobs.size_bytes` (filled by the arq worker at completion) and a new durable `epub_imports` log table (imports jobs are in-memory today — this also fixes the golden-rule-7 deviation and gives the meter something to count). `QuotaExceededError` already maps to HTTP 429 with user-facing detail; the tool executor already converts any exception into a failed tool result.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, arq, React 19, react-query, vitest.

**Spec:** `docs/superpowers/specs/2026-07-31-tier-usage-management.md` §3.2 (meters), §3.5 (enforcement points), §4.3.

**Sequencing:** **Strictly after Part B Tasks 1–2 are merged** (quotas module + admin API). Verify: `backend/app/modules/quotas/service.py` exists and `GET /api/admin/membership-quotas` lists all six kinds. Tasks 1–4 here are independent of each other (any order); Task 5 needs 1–4.

## Global Constraints

- Backend gates per task (from `backend/`, **via the Bash tool** — `uv` is not on the PowerShell PATH): `uv run ruff check . --fix && uv run ruff format .`, `uv run mypy .`, `uv run pytest -m "unit or integration"`.
- Frontend gates (from `frontend/`): `npm run lint`, `npm run build`, `npm run test`.
- Integration tests need Postgres/Redis/MinIO and `TEST_DATABASE_URL` pointing at a separate test DB. Apply new migrations to the test DB too (`DATABASE_URL=<TEST_DATABASE_URL value> uv run alembic upgrade head`).
- Commit per task via `/tmp/msg.txt` + `bash scripts/git-commit-clean.sh /tmp/msg.txt`; verify `git log -1 --format=%B`. **Never** add attribution trailers.
- Ruff limits: complexity ≤10, statements ≤20, branches ≤6, args ≤6 — extract `_enforce_quota*` helpers rather than inflating `create` methods. Frontend ESLint: file ≤110, function ≤60, nesting ≤3.
- Module direction: each repository queries **only its own module's tables**; domain services call `quotas.service` (leaf), never orchestration. Enforcement runs **before** any external fetch, book creation, or job insert.
- **Semantics:** `>=` blocks; admins exempt (handled inside `QuotaService.limits_for_user_id`); month = UTC calendar month via `QuotaService.current_month_window`; `storage_bytes` is standing (`resets_at=None`); quota row absent = unlimited (all meters short-circuit via `limits.any_limited(...)` before querying).

---

### Task 1: `audio_chapters` quota at MP3 job creation

**Files:**
- Modify: `backend/app/modules/downloads/repository.py` (meter)
- Modify: `backend/app/modules/downloads/service.py` (enforce in `create`)
- Test: `backend/tests/quotas/test_audio_quota.py`

**Interfaces:**
- Consumes: `QuotaService.limits_for_user_id/current_month_window/enforce`, `QuotaKind.AUDIO_CHAPTERS`, `QuotaLimits` (Part B Task 1).
- Produces (Task 2 extends, Task 5 reuses):
  - `DownloadRepository.chapters_in_period(user_id, *, period_start, period_end) -> int` — `SUM(total_count)` of jobs created in the window (`total_count` is set at creation from the selected range, `service.py:66`)
  - `DownloadsService._enforce_quotas(user_id) -> None` called first in `create` — single choke point for the REST route, `create_single_chapter`, and the `create_audio_download` LLM tool

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/quotas/test_audio_quota.py
"""audio_chapters quota through the real downloads service (needs Postgres+Redis)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.modules.books.schemas import BookCreate
from app.modules.chapters.service import ChapterService
from app.modules.downloads.models import DownloadJob
from app.modules.downloads.schemas import DownloadCreate
from app.modules.downloads.service import DownloadsService
from app.modules.library.service import LibraryService
from app.modules.quotas.exceptions import QuotaExceededError
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
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
        await db.execute(delete(MembershipQuota))
        await db.commit()
        yield db
        await db.rollback()
        await db.execute(delete(MembershipQuota))
        await db.commit()
    await engine.dispose()


async def _user_with_book(session: AsyncSession) -> tuple[UserRead, UUID]:
    user = await UserService(session).ensure_user(
        UserCreate(username=f"aud_{uuid4().hex[:8]}", password="test-pass-123")
    )
    book = await LibraryService(session).add_book(
        user.id, BookCreate(title="Audio Quota Book", author="A", description="d")
    )
    chapters = ChapterService(session)
    for number in range(1, 4):
        await chapters.upsert_by_number(book.id, number, f"Ch {number}", "text " * 50)
    await session.commit()
    return user, book.id


async def _set_audio_quota(session: AsyncSession, limit: float) -> None:
    session.add(
        MembershipQuota(
            membership=Membership.FREE.value,
            quota_kind=QuotaKind.AUDIO_CHAPTERS.value,
            limit_value=limit,
        )
    )
    await session.commit()


async def _seed_prior_job(session: AsyncSession, user_id: UUID, book_id: UUID, n: int) -> None:
    """A this-month job covering n chapters (created_at defaults to now())."""
    session.add(
        DownloadJob(
            user_id=user_id,
            book_id=book_id,
            chapter_from=1,
            chapter_to=n,
            provider="edge",
            voice="v",
            rate="1.0",
            status="complete",
            total_count=n,
        )
    )
    await session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_over_cap_blocks_new_audio_job(session: AsyncSession) -> None:
    user, book_id = await _user_with_book(session)
    await _set_audio_quota(session, 10)
    await _seed_prior_job(session, user.id, book_id, 10)  # 10 >= 10
    with pytest.raises(QuotaExceededError) as excinfo:
        await DownloadsService(session).create(
            user.id, DownloadCreate(book_id=book_id, chapter_from=1, chapter_to=3)
        )
    assert excinfo.value.kind is QuotaKind.AUDIO_CHAPTERS
    assert "quota" in str(excinfo.value).lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_under_cap_creates_job(session: AsyncSession) -> None:
    user, book_id = await _user_with_book(session)
    await _set_audio_quota(session, 10)
    await _seed_prior_job(session, user.id, book_id, 5)  # 5 < 10
    job = await DownloadsService(session).create(
        user.id, DownloadCreate(book_id=book_id, chapter_from=1, chapter_to=2)
    )
    assert job.status == "pending"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_and_unlimited_are_not_metered(session: AsyncSession) -> None:
    # No quota row at all: create succeeds without a meter query.
    user, book_id = await _user_with_book(session)
    job = await DownloadsService(session).create(
        user.id, DownloadCreate(book_id=book_id, chapter_from=1, chapter_to=1)
    )
    assert job.status == "pending"
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `uv run pytest tests/quotas/test_audio_quota.py -v`
Expected: `test_over_cap_blocks_new_audio_job` FAILs (no `QuotaExceededError` raised — job is created).

- [ ] **Step 3: Add the meter**

Append to `DownloadRepository` in `backend/app/modules/downloads/repository.py` (import `func` from sqlalchemy and `datetime` if missing):

```python
    async def chapters_in_period(
        self,
        user_id: UUID,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        """Chapters covered by this user's jobs created in the window.

        total_count is stamped at creation from the selected range, so
        pending/running jobs count immediately (no double-charge on retry —
        retries reuse the job row).
        """
        stmt = select(func.coalesce(func.sum(DownloadJob.total_count), 0)).where(
            DownloadJob.user_id == user_id,
            DownloadJob.created_at >= period_start,
            DownloadJob.created_at < period_end,
        )
        return int((await self._session.execute(stmt)).scalar_one())
```

- [ ] **Step 4: Enforce in `create`**

In `backend/app/modules/downloads/service.py`, add imports:

```python
from datetime import UTC, datetime

from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.service import QuotaLimits, QuotaService
```

Make the first line of `create` (before the range check at `service.py:43`):

```python
        await self._enforce_quotas(user_id)
```

and add the helper (Task 2 extends it with `storage_bytes`):

```python
    async def _enforce_quotas(self, user_id: UUID) -> None:
        """Tier quota gate for new MP3 work (audio_chapters; storage in Task C2)."""
        limits = await QuotaService(self._session).limits_for_user_id(user_id)
        if not limits.any_limited(QuotaKind.AUDIO_CHAPTERS):
            return
        await self._enforce_audio_chapters(user_id, limits)

    async def _enforce_audio_chapters(self, user_id: UUID, limits: QuotaLimits) -> None:
        start, end = QuotaService.current_month_window(datetime.now(UTC))
        used = await self._repo.chapters_in_period(
            user_id, period_start=start, period_end=end
        )
        QuotaService.enforce(
            QuotaKind.AUDIO_CHAPTERS, used, limits, resets_at=end, user_id=user_id
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/quotas/test_audio_quota.py -v`
Expected: PASS (3 tests). Also run `uv run pytest tests/llm/test_audio_download_form.py tests/llm/test_download_confirmation_outcome.py -v` — the tool path must still pass (no quota rows exist there → short-circuit).

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: enforce audio_chapters quota at MP3 job creation\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 2: `storage_bytes` standing quota (size column + worker fill)

**Files:**
- Modify: `backend/app/modules/downloads/models.py` (`size_bytes`)
- Create: `backend/migrations/versions/<generated>_add_download_jobs_size_bytes.py`
- Modify: `backend/app/jobs/tasks.py` (record size at completion)
- Modify: `backend/app/modules/downloads/repository.py` (`stored_bytes`)
- Modify: `backend/app/modules/downloads/service.py` (extend `_enforce_quotas`)
- Test: `backend/tests/quotas/test_storage_quota.py`

**Interfaces:**
- Consumes: Task 1's `_enforce_quotas` helper, `QuotaKind.STORAGE_BYTES`.
- Produces:
  - `DownloadJob.size_bytes: int | None` (BigInteger; NULL for pre-existing rows — meter treats NULL as 0, spec §7)
  - `_total_bytes(combined: bytes, parts: list[bytes]) -> int` in `app/jobs/tasks.py` (combined MP3 + per-chapter part objects — both are stored under the job prefix)
  - `DownloadRepository.stored_bytes(user_id) -> int` — non-expired complete jobs only

- [ ] **Step 1: Model + migration**

In `backend/app/modules/downloads/models.py` add after `object_key` (import `BigInteger`):

```python
    # Bytes stored in MinIO for this job (combined MP3 + chapter parts),
    # recorded at completion. NULL for jobs from before this column existed.
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
```

Run `uv run alembic revision -m "add download_jobs size_bytes"` (verify single head; `down_revision` = Part B's membership_quotas revision or the current head shown by `alembic heads`). Fill:

```python
def upgrade() -> None:
    op.add_column(
        "download_jobs",
        sa.Column("size_bytes", sa.BigInteger(), nullable=True,
                  comment="MinIO bytes for this job; NULL = pre-column job"),
    )


def downgrade() -> None:
    op.drop_column("download_jobs", "size_bytes")
```

Verify reversibility (`upgrade head` / `downgrade -1` / `upgrade head`) and apply to the test DB.

- [ ] **Step 2: Write the failing tests**

```python
# backend/tests/quotas/test_storage_quota.py
"""storage_bytes standing quota: meter + enforcement (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.jobs.tasks import _total_bytes
from app.modules.books.schemas import BookCreate
from app.modules.chapters.service import ChapterService
from app.modules.downloads.models import DownloadJob
from app.modules.downloads.repository import DownloadRepository
from app.modules.downloads.schemas import DownloadCreate
from app.modules.downloads.service import DownloadsService
from app.modules.library.service import LibraryService
from app.modules.quotas.exceptions import QuotaExceededError
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
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
        await db.execute(delete(MembershipQuota))
        await db.commit()
        yield db
        await db.rollback()
        await db.execute(delete(MembershipQuota))
        await db.commit()
    await engine.dispose()


@pytest.mark.unit
def test_total_bytes_counts_combined_and_parts() -> None:
    assert _total_bytes(b"12345", [b"12", b"345"]) == 10


async def _user_with_book(session: AsyncSession) -> tuple[UserRead, UUID]:
    user = await UserService(session).ensure_user(
        UserCreate(username=f"sto_{uuid4().hex[:8]}", password="test-pass-123")
    )
    book = await LibraryService(session).add_book(
        user.id, BookCreate(title="Storage Book", author="A", description="d")
    )
    await ChapterService(session).upsert_by_number(book.id, 1, "Ch 1", "text " * 50)
    await session.commit()
    return user, book.id


def _stored_job(user_id: UUID, book_id: UUID, *, size: int | None, expired: bool) -> DownloadJob:
    delta = timedelta(hours=-1) if expired else timedelta(hours=1)
    return DownloadJob(
        user_id=user_id,
        book_id=book_id,
        chapter_from=1,
        chapter_to=1,
        provider="edge",
        voice="v",
        rate="1.0",
        status="complete",
        total_count=1,
        size_bytes=size,
        expires_at=datetime.now(UTC) + delta,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stored_bytes_ignores_expired_and_null(session: AsyncSession) -> None:
    user, book_id = await _user_with_book(session)
    session.add_all(
        [
            _stored_job(user.id, book_id, size=1000, expired=False),
            _stored_job(user.id, book_id, size=9999, expired=True),
            _stored_job(user.id, book_id, size=None, expired=False),
        ]
    )
    await session.commit()
    assert await DownloadRepository(session).stored_bytes(user.id) == 1000


@pytest.mark.integration
@pytest.mark.asyncio
async def test_standing_cap_blocks_new_job(session: AsyncSession) -> None:
    user, book_id = await _user_with_book(session)
    session.add(_stored_job(user.id, book_id, size=5000, expired=False))
    session.add(
        MembershipQuota(
            membership=Membership.FREE.value,
            quota_kind=QuotaKind.STORAGE_BYTES.value,
            limit_value=5000.0,
        )
    )
    await session.commit()
    with pytest.raises(QuotaExceededError) as excinfo:
        await DownloadsService(session).create(
            user.id, DownloadCreate(book_id=book_id, chapter_from=1, chapter_to=1)
        )
    assert excinfo.value.kind is QuotaKind.STORAGE_BYTES
    assert excinfo.value.resets_at is None  # standing: no monthly reset
```

Run: `uv run pytest tests/quotas/test_storage_quota.py -v` — expected FAIL (`ImportError: _total_bytes`).

- [ ] **Step 3: Record size in the worker**

In `backend/app/jobs/tasks.py`, add the helper and use it in `_process` (after `combined = await concat_mp3(parts)`, before `job.status = "complete"`):

```python
def _total_bytes(combined: bytes, parts: list[bytes]) -> int:
    """MinIO footprint of a finished job: combined MP3 + per-chapter parts."""
    return len(combined) + sum(len(part) for part in parts)
```

```python
        job.size_bytes = _total_bytes(combined, parts)
```

- [ ] **Step 4: Meter + enforcement**

Append to `DownloadRepository` (import `or_` from sqlalchemy):

```python
    async def stored_bytes(self, user_id: UUID) -> int:
        """Currently retained MinIO bytes: complete, non-expired jobs only."""
        now = datetime.now(UTC)
        stmt = select(func.coalesce(func.sum(DownloadJob.size_bytes), 0)).where(
            DownloadJob.user_id == user_id,
            DownloadJob.status == "complete",
            or_(DownloadJob.expires_at.is_(None), DownloadJob.expires_at > now),
        )
        return int((await self._session.execute(stmt)).scalar_one())
```

(add `from datetime import UTC, datetime` to the repository imports if missing). In `DownloadsService._enforce_quotas`, extend to both kinds:

```python
    async def _enforce_quotas(self, user_id: UUID) -> None:
        """Tier quota gate for new MP3 work (monthly chapters + standing storage)."""
        limits = await QuotaService(self._session).limits_for_user_id(user_id)
        if limits.any_limited(QuotaKind.AUDIO_CHAPTERS):
            await self._enforce_audio_chapters(user_id, limits)
        if limits.any_limited(QuotaKind.STORAGE_BYTES):
            stored = await self._repo.stored_bytes(user_id)
            QuotaService.enforce(
                QuotaKind.STORAGE_BYTES, stored, limits, resets_at=None, user_id=user_id
            )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/quotas/test_storage_quota.py tests/quotas/test_audio_quota.py -v`
Expected: PASS (3 + 3 tests).

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add download size tracking and standing storage quota\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 3: `scrape_chapters` quota at scrape-job creation

**Files:**
- Modify: `backend/app/modules/scraping/repository.py` (meter)
- Modify: `backend/app/modules/scraping/service.py` (enforce first in `create_job`)
- Test: `backend/tests/quotas/test_scrape_quota.py`

**Interfaces:**
- Consumes: `QuotaService`, `QuotaKind.SCRAPE_CHAPTERS`.
- Produces: `ScrapingRepository.chapters_in_period(user_id, *, period_start, period_end) -> int` (`SUM(chapters_done)` of the month's jobs); enforcement runs **before** `get_adapter`/network/book creation in `create_job` (`service.py:58`), so an over-cap test needs no network. Mid-job overage is accepted (enforced at creation only; `chapters_done` grows while running — spec §3.5).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/quotas/test_scrape_quota.py
"""scrape_chapters quota at job creation (needs Postgres; no network)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.modules.quotas.exceptions import QuotaExceededError
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
from app.modules.scraping.models import ScrapingJob, ScrapingSource
from app.modules.scraping.repository import ScrapingRepository
from app.modules.scraping.schemas import ScrapeJobCreate
from app.modules.scraping.service import ScrapingService
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(delete(MembershipQuota))
        await db.commit()
        yield db
        await db.rollback()
        await db.execute(delete(MembershipQuota))
        await db.commit()
    await engine.dispose()


async def _user(session: AsyncSession) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(username=f"scr_{uuid4().hex[:8]}", password="test-pass-123")
    )


async def _any_source_id(session: AsyncSession) -> UUID:
    """Sources are seeded at startup; reuse one (or create a throwaway)."""
    row = (await session.execute(select(ScrapingSource).limit(1))).scalar_one_or_none()
    if row is None:
        row = ScrapingSource(name=f"src_{uuid4().hex[:8]}", base_domains=["example.com"])
        session.add(row)
        await session.commit()
    return row.id


async def _seed_scraped(session: AsyncSession, user_id: UUID, chapters: int) -> None:
    session.add(
        ScrapingJob(
            user_id=user_id,
            source_id=await _any_source_id(session),
            start_url="https://novelfull.net/book/x.html",
            mode="range",
            status="complete",
            chapters_done=chapters,
        )
    )
    await session.commit()


async def _set_scrape_quota(session: AsyncSession, limit: float) -> None:
    session.add(
        MembershipQuota(
            membership=Membership.FREE.value,
            quota_kind=QuotaKind.SCRAPE_CHAPTERS.value,
            limit_value=limit,
        )
    )
    await session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_meter_sums_month_chapters(session: AsyncSession) -> None:
    from datetime import UTC, datetime

    from app.modules.quotas.service import QuotaService

    user = await _user(session)
    await _seed_scraped(session, user.id, 120)
    await _seed_scraped(session, user.id, 30)
    start, end = QuotaService.current_month_window(datetime.now(UTC))
    used = await ScrapingRepository(session).chapters_in_period(
        user.id, period_start=start, period_end=end
    )
    assert used == 150


@pytest.mark.integration
@pytest.mark.asyncio
async def test_over_cap_blocks_before_any_network(session: AsyncSession) -> None:
    """Enforcement precedes adapter/network work: no mock needed, no fetch made."""
    user = await _user(session)
    await _set_scrape_quota(session, 100)
    await _seed_scraped(session, user.id, 100)
    with pytest.raises(QuotaExceededError) as excinfo:
        await ScrapingService(session).create_job(
            user.id, ScrapeJobCreate(url="https://novelfull.net/book/x.html")
        )
    assert excinfo.value.kind is QuotaKind.SCRAPE_CHAPTERS
```

(If `ScrapeJobCreate` requires more fields than `url`, check `scraping/schemas.py` and pass its minimal valid form — the assertion is what matters.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/quotas/test_scrape_quota.py -v`
Expected: `test_meter_sums_month_chapters` FAILs with `AttributeError: chapters_in_period`.

- [ ] **Step 3: Implement meter + enforcement**

Append to `ScrapingRepository` in `backend/app/modules/scraping/repository.py` (imports: `func`, `datetime`):

```python
    async def chapters_in_period(
        self,
        user_id: UUID,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        """Chapters fetched by this user's jobs created in the window."""
        stmt = select(func.coalesce(func.sum(ScrapingJob.chapters_done), 0)).where(
            ScrapingJob.user_id == user_id,
            ScrapingJob.created_at >= period_start,
            ScrapingJob.created_at < period_end,
        )
        return int((await self._session.execute(stmt)).scalar_one())
```

In `backend/app/modules/scraping/service.py`, add imports (`from datetime import UTC, datetime`, `from app.modules.quotas.kinds import QuotaKind`, `from app.modules.quotas.service import QuotaService`) and make the first line of `create_job` (before `get_adapter` at `service.py:60`):

```python
        await self._enforce_quota(user_id)
```

with the helper:

```python
    async def _enforce_quota(self, user_id: UUID) -> None:
        """Tier quota gate for new scrape work. Runs before any network fetch.

        Enforced at creation only: a running job may finish past the line
        (bounded by its own chapter range) — accepted, spec §3.5.
        """
        limits = await QuotaService(self._session).limits_for_user_id(user_id)
        if not limits.any_limited(QuotaKind.SCRAPE_CHAPTERS):
            return
        start, end = QuotaService.current_month_window(datetime.now(UTC))
        used = await self._repo.chapters_in_period(
            user_id, period_start=start, period_end=end
        )
        QuotaService.enforce(
            QuotaKind.SCRAPE_CHAPTERS, used, limits, resets_at=end, user_id=user_id
        )
```

- [ ] **Step 4: Run tests; verify the HITL tool path still passes**

Run: `uv run pytest tests/quotas/test_scrape_quota.py tests/llm/test_hitl.py -v`
Expected: PASS — `test_hitl` seeds no quota rows, so the gate short-circuits.

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: enforce scrape_chapters quota at scrape job creation\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 4: `epub_imports` — durable import log + quota

**Files:**
- Create: `backend/app/modules/imports/models.py`
- Create: `backend/app/modules/imports/repository.py`
- Create: `backend/migrations/versions/<generated>_add_epub_imports.py`
- Modify: `backend/app/core/orm.py` (register imports models)
- Modify: `backend/app/modules/imports/jobs.py` (`ImportRequest.record_id`, terminal-status writes)
- Modify: `backend/app/modules/imports/service.py` (session + record creation + enforcement)
- Modify: `backend/app/modules/imports/router.py` (construct `ImportService(session)`)
- Test: `backend/tests/quotas/test_epub_import_quota.py`

**Interfaces:**
- Consumes: `QuotaService`, `QuotaKind.EPUB_IMPORTS`.
- Produces:
  - `EpubImportRecord` (table `epub_imports`: `id` UUID PK, `user_id` FK indexed, `book_id` nullable, `chapter_count` int default 0, `status` String(16) default `"running"`, `created_at`/`updated_at`) — the durable log the in-memory runner was missing (golden rule 7)
  - `EpubImportRepository(session)`: `add(user_id) -> EpubImportRecord`, `set_terminal(record_id, *, status, chapter_count, book_id=None)`, `completed_in_period(user_id, *, period_start, period_end) -> int`
  - `ImportRequest.record_id: UUID | None = None`; `ImportService.__init__(session: AsyncSession)`
  - Meter counts **completed** imports only (failures are usually our bugs, not delivered value — spec §3.5)

- [ ] **Step 1: Model, repository, migration, registration**

```python
# backend/app/modules/imports/models.py
"""SQLAlchemy models for EPUB imports (durable log; progress stays in-memory)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class EpubImportRecord(Base):
    """One EPUB import attempt. Meter for the epub_imports quota + audit."""

    __tablename__ = "epub_imports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    book_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    chapter_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="running", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

```python
# backend/app/modules/imports/repository.py
"""DB access for the imports module's tables only (epub_imports)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.imports.models import EpubImportRecord


class EpubImportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user_id: UUID) -> EpubImportRecord:
        record = EpubImportRecord(user_id=user_id)
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def set_terminal(
        self,
        record_id: UUID,
        *,
        status: str,
        chapter_count: int,
        book_id: UUID | None = None,
    ) -> None:
        record = await self._session.get(EpubImportRecord, record_id)
        if record is None:
            return
        record.status = status
        record.chapter_count = chapter_count
        if book_id is not None:
            record.book_id = book_id
        await self._session.flush()

    async def completed_in_period(
        self,
        user_id: UUID,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        stmt = select(func.count(EpubImportRecord.id)).where(
            EpubImportRecord.user_id == user_id,
            EpubImportRecord.status == "completed",
            EpubImportRecord.created_at >= period_start,
            EpubImportRecord.created_at < period_end,
        )
        return int((await self._session.execute(stmt)).scalar_one())
```

Register in `core/orm.py` (`from app.modules.imports import models as imports_models` + tuple entry). Migration (`uv run alembic revision -m "add epub_imports"`, `down_revision` = current head):

```python
def upgrade() -> None:
    op.create_table(
        "epub_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chapter_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="running"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_epub_imports_user_id"), "epub_imports", ["user_id"])
    op.create_index(op.f("ix_epub_imports_status"), "epub_imports", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_epub_imports_status"), table_name="epub_imports")
    op.drop_index(op.f("ix_epub_imports_user_id"), table_name="epub_imports")
    op.drop_table("epub_imports")
```

Verify reversibility; apply to the test DB.

- [ ] **Step 2: Write the failing tests**

```python
# backend/tests/quotas/test_epub_import_quota.py
"""epub_imports quota + durable record lifecycle (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.modules.imports.exceptions import InvalidEpubUploadError
from app.modules.imports.models import EpubImportRecord
from app.modules.imports.repository import EpubImportRepository
from app.modules.imports.service import ImportService
from app.modules.quotas.exceptions import QuotaExceededError
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
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
        await db.execute(delete(MembershipQuota))
        await db.execute(delete(EpubImportRecord))
        await db.commit()
        yield db
        await db.rollback()
        await db.execute(delete(MembershipQuota))
        await db.execute(delete(EpubImportRecord))
        await db.commit()
    await engine.dispose()


async def _user(session: AsyncSession) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(username=f"epu_{uuid4().hex[:8]}", password="test-pass-123")
    )


async def _seed_completed(session: AsyncSession, user_id: UUID, count: int) -> None:
    repo = EpubImportRepository(session)
    for _ in range(count):
        record = await repo.add(user_id)
        await repo.set_terminal(record.id, status="completed", chapter_count=5)
    await session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_meter_counts_completed_only(session: AsyncSession) -> None:
    user = await _user(session)
    repo = EpubImportRepository(session)
    await _seed_completed(session, user.id, 2)
    failed = await repo.add(user.id)
    await repo.set_terminal(failed.id, status="failed", chapter_count=0)
    await session.commit()
    start, end = QuotaService.current_month_window(datetime.now(UTC))
    assert await repo.completed_in_period(user.id, period_start=start, period_end=end) == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_over_cap_blocks_before_validation(session: AsyncSession) -> None:
    """Quota gate precedes validation: a .txt payload (which _validate_file
    would reject) still gets the QUOTA error — ordering is provable."""
    user = await _user(session)
    session.add(
        MembershipQuota(
            membership=Membership.FREE.value,
            quota_kind=QuotaKind.EPUB_IMPORTS.value,
            limit_value=2.0,
        )
    )
    await session.commit()
    await _seed_completed(session, user.id, 2)
    with pytest.raises(QuotaExceededError):
        await ImportService(session).start(
            user.id,
            [("junk.txt", b"not an epub")],
            title=None,
            author=None,
            starting_chapter=1,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_under_cap_reaches_validation(session: AsyncSession) -> None:
    """With quota headroom, the same .txt payload fails file validation instead
    (extension check in _validate_file, service.py:125)."""
    user = await _user(session)
    session.add(
        MembershipQuota(
            membership=Membership.FREE.value,
            quota_kind=QuotaKind.EPUB_IMPORTS.value,
            limit_value=10.0,
        )
    )
    await session.commit()
    with pytest.raises(InvalidEpubUploadError):
        await ImportService(session).start(
            user.id,
            [("junk.txt", b"not an epub")],
            title=None,
            author=None,
            starting_chapter=1,
        )
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/quotas/test_epub_import_quota.py -v`
Expected: FAIL — `ModuleNotFoundError` for `app.modules.imports.models` / `ImportService()` takes no session.

- [ ] **Step 4: Thread the session + record + enforcement**

In `backend/app/modules/imports/service.py`:

- Give the service a session: `def __init__(self, session: AsyncSession) -> None: self._session = session; self._repo = EpubImportRepository(session)` (imports: `AsyncSession`, `EpubImportRepository`, `QuotaKind`, `QuotaService`, `from datetime import UTC, datetime`).
- In `start`, before `self._validate(...)`:

```python
        await self._enforce_quota(user_id)
```

- After validation, create the durable record and hand its id to the runner:

```python
        record = await self._repo.add(user_id)
        await self._session.commit()
        req = ImportRequest(
            user_id=user_id,
            title=title,
            author=author,
            starting_chapter=starting_chapter,
            record_id=record.id,
        )
```

- Add the helper:

```python
    async def _enforce_quota(self, user_id: UUID) -> None:
        """Tier quota gate for new imports; completed imports count (spec §3.5)."""
        limits = await QuotaService(self._session).limits_for_user_id(user_id)
        if not limits.any_limited(QuotaKind.EPUB_IMPORTS):
            return
        start, end = QuotaService.current_month_window(datetime.now(UTC))
        used = await self._repo.completed_in_period(
            user_id, period_start=start, period_end=end
        )
        QuotaService.enforce(
            QuotaKind.EPUB_IMPORTS, used, limits, resets_at=end, user_id=user_id
        )
```

In `backend/app/modules/imports/router.py`: change the `_imports` dependency to take `session: Annotated[AsyncSession, Depends(get_db)]` and return `ImportService(session)`.

In `backend/app/modules/imports/jobs.py`:

- `ImportRequest` gains `record_id: UUID | None = None`.
- Add a terminal-status writer used by the runner (it already owns a `factory`):

```python
async def _finish_record(
    factory: async_sessionmaker[AsyncSession],
    record_id: UUID | None,
    *,
    status: str,
    chapter_count: int,
    book_id: UUID | None = None,
) -> None:
    """Stamp the durable epub_imports row; progress stays in-memory (v2 parity)."""
    if record_id is None:
        return
    async with factory() as session:
        await EpubImportRepository(session).set_terminal(
            record_id, status=status, chapter_count=chapter_count, book_id=book_id
        )
        await session.commit()
```

- Call it at the three terminal points: in `_run_import`'s `except` block (`status="failed", chapter_count=0`); in `_import_with_session` right after `_mark_completed(...)` (`status="completed", chapter_count=total_imported, book_id=book_id`); and where `_mark_cancelled` is invoked (`status="cancelled"` with the chapters done so far). Thread `req.record_id` / the `factory` to those call sites as needed (they are all inside `_run_import`/`_import_with_session`, which have both).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/quotas/test_epub_import_quota.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add durable epub import log and enforce epub_imports quota\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 5: Backoffice job-usage columns + friendly 429s in the UI

**Files:**
- Modify: `backend/app/modules/downloads/service.py`, `backend/app/modules/scraping/service.py` (tiny per-user-set meter pass-throughs), `backend/app/modules/downloads/repository.py`, `backend/app/modules/scraping/repository.py`, `backend/app/modules/imports/repository.py` (set-variants)
- Modify: `backend/app/modules/admin/schemas.py` + `backend/app/modules/admin/usage_router.py`
- Modify: `frontend/src/features/admin/api/usage.ts` + `frontend/src/features/admin/components/usage/ByUserTable.tsx` (or its extracted `ByUserRow`)
- Test: extend `backend/tests/quotas/test_admin_usage_quota_api.py`
- Verify: downloads / scraper / import creation surfaces render `ApiError.message` on 429

**Interfaces:**
- Consumes: Part B Task 6's `_decorate_rows` composition, the three meters from Tasks 1–4.
- Produces: `GET /api/admin/usage/by-user` items additionally carry `month_audio_chapters: int`, `month_scrape_chapters: int`, `month_epub_imports: int` (current UTC month); the table shows them in one "Jobs (month)" column.

- [ ] **Step 1: Set-variant meters**

Each repository gains a grouped variant of its Task 1/3/4 meter, same filters, `GROUP BY user_id`, returning `dict[UUID, int]` (empty dict for an empty id list). Pattern (downloads shown; scraping sums `chapters_done`, imports counts completed rows):

```python
    async def chapters_for_users(
        self,
        user_ids: list[UUID],
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> dict[UUID, int]:
        """Per-user month chapter totals for the backoffice usage table."""
        if not user_ids:
            return {}
        stmt = (
            select(DownloadJob.user_id, func.coalesce(func.sum(DownloadJob.total_count), 0))
            .where(
                DownloadJob.user_id.in_(user_ids),
                DownloadJob.created_at >= period_start,
                DownloadJob.created_at < period_end,
            )
            .group_by(DownloadJob.user_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return {row[0]: int(row[1]) for row in rows}
```

Expose each through its service (`DownloadsService.month_chapters_for_users(...)`, `ScrapingService.month_chapters_for_users(...)`, and an `ImportService.month_imports_for_users(...)`), one-line pass-throughs to the repo method — the admin router composes services, never repositories.

- [ ] **Step 2: Extend the DTO and composition**

In `backend/app/modules/admin/schemas.py`, add to `AdminUserUsageRead`:

```python
    month_audio_chapters: int = 0
    month_scrape_chapters: int = 0
    month_epub_imports: int = 0
```

In `usage_router._decorate_rows`, fetch the three dicts with the same `month_start`/`month_end` and pass them into `_decorated_row` — that pushes `_decorated_row` past the 6-arg ruff limit, so bundle the lookups first:

```python
@dataclass(frozen=True)
class _RowContext:
    """Per-request lookup tables for decorating by-user rows."""

    names: dict[UUID, str]
    tiers: dict[UUID, Membership]
    month: dict[UUID, UserUsageRead]
    quotas: dict[tuple[str, str], float]
    audio: dict[UUID, int]
    scrape: dict[UUID, int]
    imports: dict[UUID, int]
```

`_decorated_row(row, ctx)` then reads everything from `ctx` (update the Part B version in place; the new fields default to `ctx.audio.get(row.user_id, 0)` etc.).

- [ ] **Step 3: Extend the API test**

In `backend/tests/quotas/test_admin_usage_quota_api.py::_seed`, also add one `DownloadJob` (`total_count=3`), one `ScrapingJob` (`chapters_done=40`, source via the Task 3 `_any_source_id` pattern), and one completed `EpubImportRecord` for the reader; assert in the test:

```python
    assert reader_row["month_audio_chapters"] == 3
    assert reader_row["month_scrape_chapters"] == 40
    assert reader_row["month_epub_imports"] == 1
```

Run: `uv run pytest tests/quotas/test_admin_usage_quota_api.py -v` — FAIL first (KeyError), then PASS after Steps 1–2.

- [ ] **Step 4: Frontend column**

In `frontend/src/features/admin/api/usage.ts`, add to `UserUsage`:

```typescript
  month_audio_chapters: number
  month_scrape_chapters: number
  month_epub_imports: number
```

In the by-user table add one "Jobs (month)" header + cell:

```tsx
                <td className="px-2 py-1.5">
                  {`A:${row.month_audio_chapters} · S:${row.month_scrape_chapters} · I:${row.month_epub_imports}`}
                </td>
```

Extend `UsagePage.test.tsx` mocks with the three fields (0s). If the table file exceeds 110 lines, extract `ByUserRow` (Part B Task 7 may already have).

- [ ] **Step 5: Verify friendly 429s on the three creation surfaces**

Backend detail is already user-facing (`str(QuotaExceededError)` via the 429 handler). Verify each frontend surface shows it:

```bash
grep -rn "useMutation\|onError\|catch" frontend/src/features/downloads frontend/src/features/scraping frontend/src/features/library frontend/src/features/reader --include=*.ts --include=*.tsx | grep -i "download\|scrape\|import" | head -30
```

For each mutation that creates an audio download, scrape job, or EPUB import: confirm its error path renders `error.message` (the shared `ApiError` carries the 429 detail). Where a surface swallows errors or shows a generic string, change it to display `error instanceof ApiError ? error.message : <generic>` — the same pattern the surface already uses for other API failures. This is a verification step: the acceptance criterion is that triggering a 429 (set a tiny quota via the admin screen, then create a job) shows the quota message, not a silent failure.

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
cd ../frontend && npm run test && npm run lint && npm run build && cd ../backend
printf 'feat: surface job quotas in backoffice and friendly 429 messages\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```
