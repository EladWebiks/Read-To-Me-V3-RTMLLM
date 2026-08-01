# Quota Infrastructure + LLM Quotas (Part B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the multi-dimension quota store (keyed `membership_quotas` table + `QuotaKind` registry in a new leaf `quotas` module), then enforce monthly LLM token/cost quotas at chat turn start with a structured error, an admin API, backoffice editing, and usage-vs-quota visibility.

**Architecture:** `modules/quotas/` owns `membership_quotas` (`membership`, `quota_kind`, `limit_value`; unique pair; **row absent = unlimited**, so no seeding) plus the `QuotaKind` enum + `KIND_REGISTRY` metadata (label/unit/window) in code. `QuotaService` resolves `QuotaLimits` for a user (admins exempt in one place) and `enforce(kind, used, limits)` raises a shared `QuotaExceededError` whose message is user-facing copy; the caller supplies the metered value (caller-metered pattern — quotas imports no domain module, so downloads/scraping/imports can call it later without cycles, and domain code never imports the orchestrator). Orchestration checks `llm_tokens`/`llm_cost_usd` in `run` before any provider call, emitting a structured SSE error; `core/exceptions.py` maps the error to HTTP 429 for the REST enforcement points Part C adds.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, pydantic v2, React 19, react-query, vitest.

**Spec:** `docs/superpowers/specs/2026-07-31-tier-usage-management.md` (approved; shared with Parts A and C). Read §3.0 (amendment), §3.2 (kinds), §3.5–§3.6 before starting.

**Sequencing:** **Strictly after Part A Tasks 1–3 are merged** (`membership_policies`, `PolicyService`, `OrchestrationService.run(user: UserRead, ...)`). Verify: `backend/app/modules/orchestration/policy.py` exists and `uv run alembic heads` shows Part A's migration as the single head. Part C depends on Tasks 1–2 here.

## Global Constraints

- Backend gates per task (from `backend/`, **via the Bash tool** — `uv` is not on the PowerShell PATH): `uv run ruff check . --fix && uv run ruff format .`, `uv run mypy .`, `uv run pytest -m "unit or integration"`.
- Frontend gates (from `frontend/`): `npm run lint`, `npm run build`, `npm run test`.
- Integration tests need Postgres/Redis/MinIO and `TEST_DATABASE_URL` pointing at a separate test DB — never the app DB. Apply new migrations to the test DB too (`DATABASE_URL=<TEST_DATABASE_URL value> uv run alembic upgrade head`).
- Commit per task via `/tmp/msg.txt` + `bash scripts/git-commit-clean.sh /tmp/msg.txt`; verify `git log -1 --format=%B`. **Never** add attribution trailers.
- Ruff limits: complexity ≤10, statements ≤20, branches ≤6, args ≤6. Frontend ESLint: file ≤110 lines, function ≤60 lines, nesting ≤3.
- Tests build settings via `tests/factories.py::make_settings`.
- Module direction: `quotas` is a **leaf** — it may import `users` (schemas + service) and its own code, never orchestration/llm/domain modules. Orchestration reads usage via `LlmService` (public service). Quota values are not secrets — log freely.
- **Semantics (repeat where relevant):** quota row absent = unlimited; comparison is `>=`; admins exempt from ALL quota kinds (never from per-turn caps); month window = UTC calendar month (Stripe anchors out of scope); standing kinds have no `resets_at`. No cached counters — documented upgrade path only.

---

### Task 1: `quotas` module foundation (kinds, table, service, 429 mapping)

**Files:**
- Create: `backend/app/modules/quotas/__init__.py` (empty)
- Create: `backend/app/modules/quotas/kinds.py`
- Create: `backend/app/modules/quotas/models.py`
- Create: `backend/app/modules/quotas/exceptions.py`
- Create: `backend/app/modules/quotas/repository.py`
- Create: `backend/app/modules/quotas/service.py`
- Modify: `backend/app/core/orm.py` (register models)
- Modify: `backend/app/core/exceptions.py` (429/404 handlers)
- Create: `backend/migrations/versions/<generated>_add_membership_quotas.py`
- Test: `backend/tests/quotas/__init__.py` (empty), `backend/tests/quotas/test_quota_service.py`

**Interfaces:**
- Consumes: `UserRead` (membership, is_admin), `UserService.get_by_id` (for `limits_for_user_id`).
- Produces (used by Tasks 2–3 and all of Part C):
  - `QuotaKind(StrEnum)`: `LLM_TOKENS`, `LLM_COST_USD`, `AUDIO_CHAPTERS`, `STORAGE_BYTES`, `SCRAPE_CHAPTERS`, `EPUB_IMPORTS`; `KIND_REGISTRY: dict[QuotaKind, KindMeta]` with `label: str`, `unit: str`, `window: Literal["month", "standing"]`
  - `MembershipQuota` ORM model (table `membership_quotas`)
  - `QuotaExceededError(kind, *, limit: float, used: float, resets_at: datetime | None)` with those attributes; `str(exc)` is user-facing copy. `QuotaRuleNotFoundError(membership, kind)` for admin clears.
  - `MembershipQuotaRepository(session)`: `get(membership, kind)`, `list_for_membership(membership)`, `list_all()`, `add(row)`, `save(row)`, `delete(row)`
  - `QuotaLimits` frozen dataclass: `exempt: bool`, `values: Mapping[QuotaKind, float]`, `limit(kind) -> float | None`, `any_limited(*kinds) -> bool`
  - `QuotaService(session)`: `async limits_for(user: UserRead) -> QuotaLimits`, `async limits_for_user_id(user_id: UUID) -> QuotaLimits`, `@staticmethod current_month_window(now) -> tuple[datetime, datetime]`, `@staticmethod enforce(kind, used, limits, *, resets_at, user_id=None) -> None`
  - HTTP: `QuotaExceededError` → 429 `{"detail": str(exc)}`; `QuotaRuleNotFoundError` → 404

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/quotas/test_quota_service.py
"""Quota kinds registry, window math, limits resolution, enforce (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.modules.quotas.exceptions import QuotaExceededError
from app.modules.quotas.kinds import KIND_REGISTRY, QuotaKind
from app.modules.quotas.models import MembershipQuota
from app.modules.quotas.service import QuotaLimits, QuotaService
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserRead
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


def _user(*, is_admin: bool = False) -> UserRead:
    return UserRead(
        id=uuid4(),
        username="quota-test",
        email=None,
        is_admin=is_admin,
        membership=Membership.FREE,
        created_at=datetime.now(UTC),
    )


@pytest.mark.unit
def test_registry_covers_every_kind() -> None:
    assert set(KIND_REGISTRY) == set(QuotaKind)
    for meta in KIND_REGISTRY.values():
        assert meta.window in ("month", "standing")


@pytest.mark.unit
def test_month_window_mid_year_and_december() -> None:
    start, end = QuotaService.current_month_window(datetime(2026, 7, 31, 23, 59, tzinfo=UTC))
    assert (start, end) == (datetime(2026, 7, 1, tzinfo=UTC), datetime(2026, 8, 1, tzinfo=UTC))
    start, end = QuotaService.current_month_window(datetime(2026, 12, 15, tzinfo=UTC))
    assert (start, end) == (datetime(2026, 12, 1, tzinfo=UTC), datetime(2027, 1, 1, tzinfo=UTC))


@pytest.mark.unit
def test_enforce_blocks_at_and_over_never_under() -> None:
    limits = QuotaLimits(exempt=False, values={QuotaKind.LLM_TOKENS: 100.0})
    QuotaService.enforce(QuotaKind.LLM_TOKENS, 99, limits, resets_at=None)  # under: fine
    with pytest.raises(QuotaExceededError) as excinfo:
        QuotaService.enforce(
            QuotaKind.LLM_TOKENS,
            100,
            limits,
            resets_at=datetime(2026, 8, 1, tzinfo=UTC),
        )
    assert excinfo.value.kind is QuotaKind.LLM_TOKENS
    assert excinfo.value.resets_at is not None
    assert "2026-08-01" in str(excinfo.value)


@pytest.mark.unit
def test_enforce_skips_unlimited_and_exempt() -> None:
    QuotaService.enforce(
        QuotaKind.LLM_TOKENS,
        10**12,
        QuotaLimits(exempt=False, values={}),
        resets_at=None,
    )
    QuotaService.enforce(
        QuotaKind.LLM_TOKENS,
        10**12,
        QuotaLimits(exempt=True, values={QuotaKind.LLM_TOKENS: 1.0}),
        resets_at=None,
    )


@pytest.mark.unit
def test_standing_kind_copy_has_no_reset_date() -> None:
    exc = QuotaExceededError(QuotaKind.STORAGE_BYTES, limit=100.0, used=150.0, resets_at=None)
    assert "Resets" not in str(exc)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_limits_for_reads_rows_and_exempts_admins(session: AsyncSession) -> None:
    session.add(
        MembershipQuota(
            membership=Membership.FREE.value,
            quota_kind=QuotaKind.LLM_TOKENS.value,
            limit_value=5000.0,
        )
    )
    await session.commit()
    service = QuotaService(session)

    limits = await service.limits_for(_user())
    assert limits.limit(QuotaKind.LLM_TOKENS) == 5000.0
    assert limits.limit(QuotaKind.LLM_COST_USD) is None  # row absent = unlimited
    assert limits.any_limited(QuotaKind.LLM_TOKENS, QuotaKind.LLM_COST_USD)

    admin = await service.limits_for(_user(is_admin=True))
    assert admin.exempt is True
    assert admin.limit(QuotaKind.LLM_TOKENS) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unknown_kind_rows_are_skipped(session: AsyncSession) -> None:
    """A row for a since-removed kind must not break resolution (fail-open)."""
    session.add(
        MembershipQuota(
            membership=Membership.FREE.value, quota_kind="retired_kind", limit_value=1.0
        )
    )
    await session.commit()
    limits = await QuotaService(session).limits_for(_user())
    assert limits.values == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `uv run pytest tests/quotas/test_quota_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.modules.quotas'`

- [ ] **Step 3: Implement kinds, model, exceptions**

```python
# backend/app/modules/quotas/kinds.py
"""Quota kind registry — the enum lives in code; limits live in membership_quotas.

Adding a dimension = one enum value + one KIND_REGISTRY entry (+ a meter and
an enforcement call in the owning domain module). No migration, no API/UI
change — the admin surface is registry-driven.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class QuotaKind(StrEnum):
    """A meterable usage dimension."""

    LLM_TOKENS = "llm_tokens"
    LLM_COST_USD = "llm_cost_usd"
    AUDIO_CHAPTERS = "audio_chapters"
    STORAGE_BYTES = "storage_bytes"
    SCRAPE_CHAPTERS = "scrape_chapters"
    EPUB_IMPORTS = "epub_imports"


@dataclass(frozen=True, slots=True)
class KindMeta:
    """Display + windowing metadata; 'standing' kinds compare a level, no reset."""

    label: str
    unit: str
    window: Literal["month", "standing"]


KIND_REGISTRY: dict[QuotaKind, KindMeta] = {
    QuotaKind.LLM_TOKENS: KindMeta("AI tokens", "tokens", "month"),
    QuotaKind.LLM_COST_USD: KindMeta("AI spend", "USD", "month"),
    QuotaKind.AUDIO_CHAPTERS: KindMeta("Audio chapters", "chapters", "month"),
    QuotaKind.STORAGE_BYTES: KindMeta("Download storage", "bytes", "standing"),
    QuotaKind.SCRAPE_CHAPTERS: KindMeta("Scraped chapters", "chapters", "month"),
    QuotaKind.EPUB_IMPORTS: KindMeta("EPUB imports", "imports", "month"),
}
```

```python
# backend/app/modules/quotas/models.py
"""SQLAlchemy models for per-tier usage quotas."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MembershipQuota(Base):
    """One quota limit for one (membership, kind). Row absent = unlimited.

    Sparse by design: no seeding, no NULL limits. limit_value is float64 —
    exact for integer counts up to 2^53 (tokens/chapters/bytes all fit).
    """

    __tablename__ = "membership_quotas"
    __table_args__ = (
        UniqueConstraint("membership", "quota_kind", name="uq_membership_quotas_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    membership: Mapped[str] = mapped_column(String(32), index=True)
    quota_kind: Mapped[str] = mapped_column(String(32))
    limit_value: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

```python
# backend/app/modules/quotas/exceptions.py
"""Typed quota errors. str(exc) is USER-FACING copy (429 detail / SSE detail)."""

from __future__ import annotations

from datetime import datetime

from app.modules.quotas.kinds import KIND_REGISTRY, QuotaKind


class QuotaExceededError(Exception):
    """A usage quota is at/over its limit; the requested work is refused."""

    def __init__(
        self,
        kind: QuotaKind,
        *,
        limit: float,
        used: float,
        resets_at: datetime | None,
    ) -> None:
        self.kind = kind
        self.limit = limit
        self.used = used
        self.resets_at = resets_at
        super().__init__(_user_copy(kind, limit, used, resets_at))


class QuotaRuleNotFoundError(Exception):
    """Admin tried to clear a quota rule that does not exist."""

    def __init__(self, membership: str, kind: str) -> None:
        super().__init__(f"no quota rule for {membership}/{kind}")


def _user_copy(
    kind: QuotaKind, limit: float, used: float, resets_at: datetime | None
) -> str:
    meta = KIND_REGISTRY[kind]
    amounts = f"{used:g}/{limit:g} {meta.unit}"
    if resets_at is not None:
        return (
            f"Monthly {meta.label} quota reached ({amounts}). "
            f"Resets {resets_at.date().isoformat()}."
        )
    return f"{meta.label} quota reached ({amounts}). Free up space or upgrade."
```

- [ ] **Step 4: Implement repository + service**

```python
# backend/app/modules/quotas/repository.py
"""DB access for the quotas module's tables only (membership_quotas)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.quotas.models import MembershipQuota


class MembershipQuotaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, membership: str, quota_kind: str) -> MembershipQuota | None:
        stmt = select(MembershipQuota).where(
            MembershipQuota.membership == membership,
            MembershipQuota.quota_kind == quota_kind,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_membership(self, membership: str) -> list[MembershipQuota]:
        stmt = select(MembershipQuota).where(MembershipQuota.membership == membership)
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_all(self) -> list[MembershipQuota]:
        stmt = select(MembershipQuota).order_by(
            MembershipQuota.membership, MembershipQuota.quota_kind
        )
        return list((await self._session.execute(stmt)).scalars().all())

    def add(self, row: MembershipQuota) -> None:
        self._session.add(row)

    async def save(self, row: MembershipQuota) -> MembershipQuota:
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def delete(self, row: MembershipQuota) -> None:
        await self._session.delete(row)
        await self._session.flush()
```

```python
# backend/app/modules/quotas/service.py
"""Quota limits resolution and enforcement (caller-metered).

This module is a LEAF: it imports users (identity) and its own code only.
Callers (orchestration, downloads, scraping, imports) measure their own
usage via their own repositories and hand the number to enforce() — that is
what lets domain services enforce quotas without importing the orchestrator.
Admins are exempt from ALL quota kinds here, in one place (spec §3.4);
nobody is exempt from per-turn caps (those live in orchestration).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.quotas.exceptions import QuotaExceededError
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.repository import MembershipQuotaRepository
from app.modules.users.schemas import UserRead
from app.modules.users.service import UserService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class QuotaLimits:
    """Resolved limits for one user. Missing kind = unlimited."""

    exempt: bool
    values: Mapping[QuotaKind, float]

    def limit(self, kind: QuotaKind) -> float | None:
        return None if self.exempt else self.values.get(kind)

    def any_limited(self, *kinds: QuotaKind) -> bool:
        return any(self.limit(kind) is not None for kind in kinds)


class QuotaService:
    """Resolve per-tier quota limits and compare metered usage against them."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = MembershipQuotaRepository(session)

    async def limits_for(self, user: UserRead) -> QuotaLimits:
        """Limits for a user object (orchestration path). Admins exempt."""
        if user.is_admin:
            return QuotaLimits(exempt=True, values={})
        rows = await self._repo.list_for_membership(user.membership.value)
        values: dict[QuotaKind, float] = {}
        for row in rows:
            try:
                values[QuotaKind(row.quota_kind)] = row.limit_value
            except ValueError:
                logger.warning(
                    "ignoring unknown quota kind row", extra={"kind": row.quota_kind}
                )
        return QuotaLimits(exempt=False, values=values)

    async def limits_for_user_id(self, user_id: UUID) -> QuotaLimits:
        """Limits for a bare user id (domain-service path: they carry no UserRead)."""
        user = await UserService(self._session).get_by_id(user_id)
        return await self.limits_for(user)

    @staticmethod
    def current_month_window(now: datetime) -> tuple[datetime, datetime]:
        """[first-of-month, first-of-next-month) in UTC.

        Calendar months only; Stripe billing anchors are out of scope (§3.6).
        """
        moment = now.astimezone(UTC)
        start = datetime(moment.year, moment.month, 1, tzinfo=UTC)
        if moment.month == 12:
            return start, datetime(moment.year + 1, 1, 1, tzinfo=UTC)
        return start, datetime(moment.year, moment.month + 1, 1, tzinfo=UTC)

    @staticmethod
    def enforce(
        kind: QuotaKind,
        used: float,
        limits: QuotaLimits,
        *,
        resets_at: datetime | None,
        user_id: UUID | None = None,
    ) -> None:
        """Raise QuotaExceededError when used >= limit. No-op if unlimited/exempt."""
        limit = limits.limit(kind)
        if limit is None or used < limit:
            return
        logger.info(
            "quota exceeded",
            extra={
                "user_id": str(user_id) if user_id else None,
                "kind": kind.value,
                "used": used,
                "limit": limit,
                "resets_at": resets_at.isoformat() if resets_at else None,
            },
        )
        raise QuotaExceededError(kind, limit=limit, used=used, resets_at=resets_at)
```

- [ ] **Step 5: Register models, HTTP handlers, migration**

In `backend/app/core/orm.py::import_all_models`: add `from app.modules.quotas import models as quotas_models` and `quotas_models,` to the tuple.

In `backend/app/core/exceptions.py`: add a `_register_quota_handlers(app)` (call it from `register_exception_handlers`), importing from `app.modules.quotas.exceptions`:

```python
def _register_quota_handlers(app: FastAPI) -> None:
    @app.exception_handler(QuotaExceededError)
    async def _quota_exceeded(
        _request: Request,
        exc: QuotaExceededError,
    ) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    @app.exception_handler(QuotaRuleNotFoundError)
    async def _quota_rule_missing(
        _request: Request,
        _exc: QuotaRuleNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Quota rule not found"})
```

Migration: `uv run alembic revision -m "add membership_quotas"` (verify single head; `down_revision` must be Part A's membership_policies revision). Fill:

```python
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.create_table(
        "membership_quotas",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership", sa.String(length=32), nullable=False),
        sa.Column("quota_kind", sa.String(length=32), nullable=False),
        sa.Column("limit_value", sa.Float(), nullable=False,
                  comment="Row absent = unlimited; there are no NULL limits"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("membership", "quota_kind", name="uq_membership_quotas_pair"),
    )
    op.create_index(
        op.f("ix_membership_quotas_membership"), "membership_quotas", ["membership"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_membership_quotas_membership"), table_name="membership_quotas")
    op.drop_table("membership_quotas")
```

Then: `uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`, plus the same `upgrade head` against the test DB.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/quotas/test_quota_service.py -v`
Expected: PASS (7 tests)

- [ ] **Step 7: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add quotas module with keyed membership_quotas and kind registry\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 2: Admin API for quota rules

**Files:**
- Create: `backend/app/modules/quotas/schemas.py`
- Modify: `backend/app/modules/quotas/service.py` (admin methods)
- Create: `backend/app/modules/quotas/admin_router.py`
- Modify: `backend/app/main.py` (register router)
- Test: `backend/tests/quotas/test_membership_quota_api.py`

**Interfaces:**
- Consumes: Task 1's repository/service/exceptions, `require_admin`.
- Produces (used by Tasks 5–6 and Part C's screens):
  - `GET /api/admin/membership-quotas` → `{"kinds": [{kind,label,unit,window}...], "quotas": [{membership, quota_kind, limit_value, updated_at}...]}` — kinds come from the registry, so new kinds appear with zero frontend changes
  - `PUT /api/admin/membership-quotas/{membership}/{kind}` body `{"limit_value": > 0}` → upsert
  - `DELETE /api/admin/membership-quotas/{membership}/{kind}` → 204 (row gone = unlimited); 404 if absent
  - Typed path params (`Membership`, `QuotaKind`) → 422 on unknown tier/kind
  - `QuotaService.list_quotas()`, `set_quota(membership, kind, limit_value, *, actor_id)`, `clear_quota(membership, kind, *, actor_id)`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/quotas/test_membership_quota_api.py
"""Admin membership-quotas API: authz + upsert/clear (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from uuid import UUID

import pytest
from app.core.config import get_settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
from app.modules.users.models import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.dbcleanup import clear_users

_HOST = "test.local"
BASE = "/api/admin/membership-quotas"


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
    async with session_factory() as session:
        await session.execute(delete(MembershipQuota))
        await session.commit()
    async with engine.begin() as conn:
        await clear_users(conn)
    app.dependency_overrides[get_db] = _make_db_override(session_factory)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=f"http://{_HOST}") as http:
        yield http
    app.dependency_overrides.clear()
    async with session_factory() as session:
        await session.execute(delete(MembershipQuota))
        await session.commit()
    async with engine.begin() as conn:
        await clear_users(conn)
    await engine.dispose()


async def _create_admin(username: str) -> UUID:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=None,
            google_sub=f"{username}-sub",
            is_admin=True,
        )
        session.add(user)
        await session.commit()
        user_id = user.id
    await engine.dispose()
    return user_id


@pytest.fixture
async def admin_client(client: AsyncClient) -> AsyncClient:
    user_id = await _create_admin("quota-admin")
    token = create_access_token(
        user_id=user_id, username="quota-admin", settings=get_settings()
    )
    client.cookies.set(COOKIE_NAME, token, domain=_HOST, path="/")
    return client


@pytest.mark.integration
async def test_anonymous_gets_401(client: AsyncClient) -> None:
    assert (await client.get(BASE)).status_code == 401


@pytest.mark.integration
async def test_list_serves_registry_and_rows(admin_client: AsyncClient) -> None:
    response = await admin_client.get(BASE)
    assert response.status_code == 200
    body = response.json()
    assert {k["kind"] for k in body["kinds"]} == {k.value for k in QuotaKind}
    assert body["quotas"] == []  # sparse: nothing configured = all unlimited


@pytest.mark.integration
async def test_put_upserts_and_delete_clears(admin_client: AsyncClient) -> None:
    put = await admin_client.put(
        f"{BASE}/free/llm_tokens", json={"limit_value": 500000}
    )
    assert put.status_code == 200
    assert put.json()["limit_value"] == 500000

    replaced = await admin_client.put(
        f"{BASE}/free/llm_tokens", json={"limit_value": 250000}
    )
    assert replaced.json()["limit_value"] == 250000
    listed = await admin_client.get(BASE)
    assert len(listed.json()["quotas"]) == 1

    assert (await admin_client.delete(f"{BASE}/free/llm_tokens")).status_code == 204
    assert (await admin_client.delete(f"{BASE}/free/llm_tokens")).status_code == 404


@pytest.mark.integration
async def test_validation_rejects_bad_inputs(admin_client: AsyncClient) -> None:
    assert (
        await admin_client.put(f"{BASE}/free/llm_tokens", json={"limit_value": 0})
    ).status_code == 422
    assert (
        await admin_client.put(f"{BASE}/free/not_a_kind", json={"limit_value": 5})
    ).status_code == 422
    assert (
        await admin_client.put(f"{BASE}/platinum/llm_tokens", json={"limit_value": 5})
    ).status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/quotas/test_membership_quota_api.py -v`
Expected: FAIL — 404 (routes missing).

- [ ] **Step 3: Schemas + admin service methods + router**

```python
# backend/app/modules/quotas/schemas.py
"""Pydantic DTOs for the membership-quotas admin API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.quotas.kinds import QuotaKind
from app.modules.users.membership import Membership


class QuotaKindInfo(BaseModel):
    """One registry entry, served so the frontend never hardcodes kinds."""

    kind: QuotaKind
    label: str
    unit: str
    window: Literal["month", "standing"]


class MembershipQuotaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    membership: Membership
    quota_kind: QuotaKind
    limit_value: float
    updated_at: datetime


class MembershipQuotasResponse(BaseModel):
    kinds: list[QuotaKindInfo]
    quotas: list[MembershipQuotaRead]


class QuotaLimitWrite(BaseModel):
    limit_value: float = Field(gt=0)
```

Append to `QuotaService` in `service.py` (imports: `from app.modules.quotas.exceptions import QuotaExceededError, QuotaRuleNotFoundError`, `from app.modules.quotas.models import MembershipQuota`, `from app.modules.users.membership import Membership`):

```python
    async def list_quotas(self) -> list[MembershipQuota]:
        """All configured quota rules (sparse: absent pair = unlimited)."""
        return await self._repo.list_all()

    async def set_quota(
        self,
        membership: Membership,
        kind: QuotaKind,
        limit_value: float,
        *,
        actor_id: UUID,
    ) -> MembershipQuota:
        row = await self._repo.get(membership.value, kind.value)
        if row is None:
            row = MembershipQuota(
                membership=membership.value, quota_kind=kind.value, limit_value=limit_value
            )
            self._repo.add(row)
        else:
            row.limit_value = limit_value
        saved = await self._repo.save(row)
        logger.info(
            "membership quota set",
            extra={
                "membership": membership.value,
                "kind": kind.value,
                "limit": limit_value,
                "actor": str(actor_id),
            },
        )
        return saved

    async def clear_quota(
        self, membership: Membership, kind: QuotaKind, *, actor_id: UUID
    ) -> None:
        row = await self._repo.get(membership.value, kind.value)
        if row is None:
            raise QuotaRuleNotFoundError(membership.value, kind.value)
        await self._repo.delete(row)
        logger.info(
            "membership quota cleared",
            extra={"membership": membership.value, "kind": kind.value, "actor": str(actor_id)},
        )
```

```python
# backend/app/modules/quotas/admin_router.py
"""Admin CRUD for quota rules. Set/clear pattern mirrors runtime_config."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_admin
from app.modules.quotas.kinds import KIND_REGISTRY, QuotaKind
from app.modules.quotas.schemas import (
    MembershipQuotaRead,
    MembershipQuotasResponse,
    QuotaKindInfo,
    QuotaLimitWrite,
)
from app.modules.quotas.service import QuotaService
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/admin/membership-quotas", tags=["admin"])


def _service(session: Annotated[AsyncSession, Depends(get_db)]) -> QuotaService:
    return QuotaService(session)


@router.get("")
async def list_quotas(
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[QuotaService, Depends(_service)],
) -> MembershipQuotasResponse:
    """Kind registry + every configured rule (absent pair = unlimited)."""
    rows = await service.list_quotas()
    return MembershipQuotasResponse(
        kinds=[
            QuotaKindInfo(kind=kind, label=m.label, unit=m.unit, window=m.window)
            for kind, m in KIND_REGISTRY.items()
        ],
        quotas=[MembershipQuotaRead.model_validate(row) for row in rows],
    )


@router.put("/{membership}/{kind}")
async def put_quota(
    membership: Membership,
    kind: QuotaKind,
    body: QuotaLimitWrite,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[QuotaService, Depends(_service)],
) -> MembershipQuotaRead:
    """Set or replace one quota rule."""
    row = await service.set_quota(membership, kind, body.limit_value, actor_id=admin.id)
    return MembershipQuotaRead.model_validate(row)


@router.delete("/{membership}/{kind}", status_code=204)
async def delete_quota(
    membership: Membership,
    kind: QuotaKind,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[QuotaService, Depends(_service)],
) -> None:
    """Remove one rule; that (membership, kind) becomes unlimited again."""
    await service.clear_quota(membership, kind, actor_id=admin.id)
```

In `backend/app/main.py`: `from app.modules.quotas.admin_router import router as quotas_admin_router` + `app.include_router(quotas_admin_router, prefix=api_prefix)` next to the membership policies router.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/quotas/test_membership_quota_api.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add admin API for membership quota rules\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 3: LLM quota enforcement at chat turn start

**Files:**
- Modify: `backend/app/modules/orchestration/service.py` (`run` only — resume never re-checks: same turn, frozen policy)
- Test: `backend/tests/orchestration/test_monthly_quota_enforcement.py`

**Interfaces:**
- Consumes: `QuotaService` (`limits_for`, `current_month_window`, `enforce`), `QuotaKind.LLM_TOKENS`/`LLM_COST_USD`, `QuotaExceededError`, `LlmService.usage_summary` (already `self._llm`), `PolicyService.resolve` (Part A).
- Produces: SSE error `{"code": "quota_exceeded", "kind": "<quota kind>", "detail": "<user copy>", "resets_at": "<ISO>"}` before any provider call; stream ends after it (no `done`). Task 4's frontend depends on this shape.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/orchestration/test_monthly_quota_enforcement.py
"""Turn-start LLM quota enforcement through the real chat pipeline (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.core.config import Settings, get_settings
from app.modules.llm.chat_service import ChatService
from app.modules.llm.models import LlmExecution
from app.modules.llm.types import ToolCallingRequest, ToolCallingResponse, Usage
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.seed import seed_membership_policies
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
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
        await db.execute(delete(MembershipQuota))
        await db.execute(delete(MembershipPolicy))
        await db.commit()
        await seed_membership_policies(db)
        yield db
        await db.rollback()
        await db.execute(delete(MembershipQuota))
        await db.execute(delete(MembershipPolicy))
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


async def _user(session: AsyncSession, *, is_admin: bool = False) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(
            username=f"quo_{uuid4().hex[:8]}", password="test-pass-123", is_admin=is_admin
        )
    )


async def _seed_usage(
    session: AsyncSession, user_id: UUID, *, tokens_in: int, tokens_out: int, cost: float
) -> None:
    session.add(
        LlmExecution(
            user_id=user_id,
            task="chat_tools",
            provider="gemini",
            model="gemini-3.5-flash-lite",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            latency_ms=10,
            status="ok",
        )
    )
    await session.commit()


async def _set_quota(session: AsyncSession, kind: QuotaKind, limit: float | None) -> None:
    await session.execute(
        delete(MembershipQuota).where(
            MembershipQuota.membership == Membership.FREE.value,
            MembershipQuota.quota_kind == kind.value,
        )
    )
    if limit is not None:
        session.add(
            MembershipQuota(
                membership=Membership.FREE.value, quota_kind=kind.value, limit_value=limit
            )
        )
    await session.commit()


def _text_llm(counter: dict[str, int]) -> Any:
    async def _fake(req: ToolCallingRequest, **_kwargs: Any) -> ToolCallingResponse:
        del req
        counter["calls"] += 1
        return ToolCallingResponse(
            text="Hello!",
            tool_calls=[],
            usage=Usage(5, 5),
            model="gemini-3.5-flash-lite",
            provider="gemini",
        )

    return _fake


async def _run_turn(
    session: AsyncSession,
    user: UserRead,
    counter: dict[str, int],
    monkeypatch: pytest.MonkeyPatch,
) -> list[Any]:
    service = ChatService(session, _settings())
    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_text_llm(counter)))
    return [e async for e in service.stream_chat(user, "hi", None)]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_over_cap_blocks_before_any_provider_call(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _set_quota(session, QuotaKind.LLM_TOKENS, 100)
    user = await _user(session)
    await _seed_usage(session, user.id, tokens_in=60, tokens_out=50, cost=0.0)  # 110 >= 100
    counter = {"calls": 0}
    events = await _run_turn(session, user, counter, monkeypatch)
    error = next(e for e in events if e.event == "error")
    assert error.data["code"] == "quota_exceeded"
    assert error.data["kind"] == "llm_tokens"
    assert "resets_at" in error.data
    assert counter["calls"] == 0  # BEFORE any provider call
    assert not [e for e in events if e.event == "done"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_near_cap_still_runs(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _set_quota(session, QuotaKind.LLM_TOKENS, 200)
    user = await _user(session)
    await _seed_usage(session, user.id, tokens_in=60, tokens_out=50, cost=0.0)  # 110 < 200
    counter = {"calls": 0}
    events = await _run_turn(session, user, counter, monkeypatch)
    assert events[-1].event == "done"
    assert counter["calls"] == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cost_cap_blocks(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _set_quota(session, QuotaKind.LLM_COST_USD, 1.0)
    user = await _user(session)
    await _seed_usage(session, user.id, tokens_in=1, tokens_out=1, cost=2.5)
    counter = {"calls": 0}
    events = await _run_turn(session, user, counter, monkeypatch)
    error = next(e for e in events if e.event == "error")
    assert error.data["code"] == "quota_exceeded"
    assert error.data["kind"] == "llm_cost_usd"
    assert counter["calls"] == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_is_exempt_from_quota(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _set_quota(session, QuotaKind.LLM_TOKENS, 10)
    user = await _user(session, is_admin=True)
    await _seed_usage(session, user.id, tokens_in=100, tokens_out=100, cost=0.0)
    counter = {"calls": 0}
    events = await _run_turn(session, user, counter, monkeypatch)
    assert events[-1].event == "done"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_raising_or_removing_the_rule_unblocks_immediately(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Limits are read fresh per turn: no cache, no restart.

    (Only one Membership value exists today, so a 'tier upgrade' is simulated
    by removing the tier's rule — the freshness property is identical.)
    """
    await _set_quota(session, QuotaKind.LLM_TOKENS, 100)
    user = await _user(session)
    await _seed_usage(session, user.id, tokens_in=60, tokens_out=50, cost=0.0)
    counter = {"calls": 0}
    blocked = await _run_turn(session, user, counter, monkeypatch)
    assert next(e for e in blocked if e.event == "error").data["code"] == "quota_exceeded"

    await _set_quota(session, QuotaKind.LLM_TOKENS, None)  # row gone = unlimited
    events = await _run_turn(session, user, counter, monkeypatch)
    assert events[-1].event == "done"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/orchestration/test_monthly_quota_enforcement.py -v`
Expected: FAIL — no `error` event with `code == "quota_exceeded"` (turn runs normally).

- [ ] **Step 3: Wire the check into `run`**

In `backend/app/modules/orchestration/service.py`, add imports:

```python
from datetime import UTC, datetime

from app.modules.quotas.exceptions import QuotaExceededError
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.service import QuotaService
```

At the top of `run`, right after `policy = await PolicyService(...).resolve(user)` (Part A Task 3):

```python
        try:
            await self._check_llm_quota(user)
        except QuotaExceededError as exc:
            yield _quota_error_event(exc)
            return
```

Add the method (near `_make_ctx`) and module helper (near `_fail_tool`):

```python
    async def _check_llm_quota(self, user: UserRead) -> None:
        """Reject the turn BEFORE any provider call when a monthly LLM quota is hit.

        Sits before conversation-context build on purpose: context building can
        itself trigger a summarization provider call. Resume-confirm does not
        re-check — it is the same turn (spec §3.5).
        """
        quotas = QuotaService(self._session)
        limits = await quotas.limits_for(user)
        if not limits.any_limited(QuotaKind.LLM_TOKENS, QuotaKind.LLM_COST_USD):
            return
        start, end = QuotaService.current_month_window(datetime.now(UTC))
        summary = await self._llm.usage_summary(user.id, period_start=start, period_end=end)
        tokens = summary.tokens_in + summary.tokens_out
        QuotaService.enforce(
            QuotaKind.LLM_TOKENS, tokens, limits, resets_at=end, user_id=user.id
        )
        QuotaService.enforce(
            QuotaKind.LLM_COST_USD, summary.total_cost, limits, resets_at=end, user_id=user.id
        )
```

```python
def _quota_error_event(exc: QuotaExceededError) -> ChatSseEvent:
    """Structured SSE error the frontend maps to user copy (spec §6)."""
    return ChatSseEvent(
        "error",
        {
            "code": "quota_exceeded",
            "kind": exc.kind.value,
            "detail": str(exc),
            "resets_at": exc.resets_at.isoformat() if exc.resets_at else None,
        },
    )
```

The user's message was already persisted by `ChatService._prepare_conversation` — intentional: history keeps the message; only the assistant turn is refused.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/orchestration/test_monthly_quota_enforcement.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: enforce monthly LLM quotas at chat turn start\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 4: Chat UI renders the quota error

**Files:**
- Modify: `frontend/src/features/assistant/api/chatTypes.ts` (`ChatStreamHandlers.onError` signature)
- Modify: `frontend/src/features/assistant/api/sseDispatch.ts` (pass `code`/`resets_at` through)
- Create: `frontend/src/features/assistant/logic/errorCopy.ts`
- Create: `frontend/src/features/assistant/logic/errorCopy.test.ts`
- Modify: `frontend/src/features/assistant/hooks/streamHandlers.ts` (map code → copy)

**Interfaces:**
- Consumes: SSE `error` event `{code?, kind?, detail, resets_at?}` (Task 3).
- Produces: `onError: (detail: string, code?: string, resetsAt?: string) => void`; `chatErrorMessage(detail, code?, resetsAt?) -> string`. Existing `onError` producers passing only `detail` stay valid (new params optional).

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/src/features/assistant/logic/errorCopy.test.ts
import { describe, expect, it } from 'vitest'
import { chatErrorMessage } from './errorCopy'

describe('chatErrorMessage', () => {
  it('passes ordinary errors through', () => {
    expect(chatErrorMessage('something broke')).toBe('something broke')
    expect(chatErrorMessage('boom', 'budget_exceeded')).toBe('boom')
  })

  it('maps quota_exceeded to friendly copy with the rollover date', () => {
    const message = chatErrorMessage(
      'Monthly AI tokens quota reached (110/100 tokens). Resets 2026-08-01.',
      'quota_exceeded',
      '2026-08-01T00:00:00+00:00',
    )
    expect(message).toContain('monthly AI limit')
    expect(message).toContain('2026')
  })

  it('falls back to "next month" for a missing/invalid date', () => {
    expect(chatErrorMessage('x', 'quota_exceeded')).toContain('next month')
    expect(chatErrorMessage('x', 'quota_exceeded', 'not-a-date')).toContain('next month')
  })
})
```

Run (from `frontend/`): `npm run test -- errorCopy` — expected FAIL (module not found).

- [ ] **Step 2: Implement `errorCopy.ts`**

```typescript
// frontend/src/features/assistant/logic/errorCopy.ts
/** Maps structured chat SSE errors to user-facing copy (spec §6). */

export function chatErrorMessage(
  detail: string,
  code?: string,
  resetsAt?: string,
): string {
  if (code === 'quota_exceeded') {
    return `You've reached your monthly AI limit. Upgrade your plan or try again after ${rolloverLabel(resetsAt)}.`
  }
  return detail
}

function rolloverLabel(resetsAt?: string): string {
  if (!resetsAt) return 'next month'
  const date = new Date(resetsAt)
  if (Number.isNaN(date.getTime())) return 'next month'
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}
```

Run: `npm run test -- errorCopy` — expected PASS.

- [ ] **Step 3: Thread code/resets_at through the SSE layer**

In `frontend/src/features/assistant/api/chatTypes.ts`:

```typescript
  onError: (detail: string, code?: string, resetsAt?: string) => void
```

In `frontend/src/features/assistant/api/sseDispatch.ts`, replace the error fallback branch:

```typescript
  if (!handled && event === 'error') {
    handlers.onError(
      String(data.detail ?? 'Chat error'),
      typeof data.code === 'string' ? data.code : undefined,
      typeof data.resets_at === 'string' ? data.resets_at : undefined,
    )
  }
```

In `frontend/src/features/assistant/hooks/streamHandlers.ts`, import `chatErrorMessage` from `../logic/errorCopy`:

```typescript
    onError: (detail, code, resetsAt) => {
      setLiveStatus(null)
      setError(chatErrorMessage(detail, code, resetsAt))
    },
```

Then `grep -rn "onError(" frontend/src/features/assistant` — other producers (network-failure paths) passing only `detail` remain type-correct; leave them unchanged.

- [ ] **Step 4: Frontend gates + commit**

```bash
npm run test
npm run lint
npm run build
printf 'feat: render monthly quota errors with friendly copy in chat\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 5: Backoffice — quota editing on the Memberships screen

**Files:**
- Create: `frontend/src/features/admin/api/membershipQuotas.ts`
- Create: `frontend/src/features/admin/hooks/useMembershipQuotas.ts`
- Create: `frontend/src/features/admin/components/policies/QuotaSection.tsx`
- Create: `frontend/src/features/admin/components/policies/QuotaSection.test.tsx`
- Modify: `frontend/src/features/admin/components/policies/PoliciesPage.tsx` (fetch quotas, render section per card)
- Modify: `frontend/src/features/admin/components/policies/PolicyCard.tsx` (accept `children` and render them under the caps grid)

**Interfaces:**
- Consumes: `GET/PUT/DELETE /api/admin/membership-quotas...` (Task 2), `parsePolicyInput` (Part A Task 6).
- Produces: registry-driven quota inputs per tier card — blank = unlimited (DELETE), number = PUT. New kinds registered in Part C appear with **zero** frontend changes.

- [ ] **Step 1: API client + hook**

```typescript
// frontend/src/features/admin/api/membershipQuotas.ts
import { apiDelete, apiGet, apiPut } from '@/shared/lib/api'

/** Mirrors quotas/schemas.py. */
export type QuotaKindInfo = {
  kind: string
  label: string
  unit: string
  window: 'month' | 'standing'
}

export type MembershipQuotaRow = {
  membership: string
  quota_kind: string
  limit_value: number
  updated_at: string
}

export type MembershipQuotasResponse = {
  kinds: QuotaKindInfo[]
  quotas: MembershipQuotaRow[]
}

export function fetchMembershipQuotas(): Promise<MembershipQuotasResponse> {
  return apiGet('/api/admin/membership-quotas')
}

export function putMembershipQuota(
  membership: string,
  kind: string,
  limitValue: number,
): Promise<MembershipQuotaRow> {
  return apiPut(
    `/api/admin/membership-quotas/${encodeURIComponent(membership)}/${encodeURIComponent(kind)}`,
    { limit_value: limitValue },
  )
}

export function deleteMembershipQuota(membership: string, kind: string): Promise<void> {
  return apiDelete(
    `/api/admin/membership-quotas/${encodeURIComponent(membership)}/${encodeURIComponent(kind)}`,
  )
}
```

```typescript
// frontend/src/features/admin/hooks/useMembershipQuotas.ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteMembershipQuota,
  fetchMembershipQuotas,
  putMembershipQuota,
} from '@/features/admin/api/membershipQuotas'

export const membershipQuotasKey = ['admin', 'membership-quotas'] as const

export function useMembershipQuotas() {
  return useQuery({ queryKey: membershipQuotasKey, queryFn: fetchMembershipQuotas })
}

export type QuotaChange = { membership: string; kind: string; limit: number | null }

export function useSaveQuota() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ membership, kind, limit }: QuotaChange) =>
      limit === null
        ? deleteMembershipQuota(membership, kind)
        : putMembershipQuota(membership, kind, limit).then(() => undefined),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: membershipQuotasKey }),
  })
}
```

- [ ] **Step 2: Write the failing component test**

```tsx
// frontend/src/features/admin/components/policies/QuotaSection.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { QuotaSection } from './QuotaSection'
import {
  deleteMembershipQuota,
  putMembershipQuota,
} from '@/features/admin/api/membershipQuotas'

vi.mock('@/features/admin/api/membershipQuotas', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  putMembershipQuota: vi.fn(),
  deleteMembershipQuota: vi.fn(),
}))

const KINDS = [
  { kind: 'llm_tokens', label: 'AI tokens', unit: 'tokens', window: 'month' as const },
  {
    kind: 'storage_bytes',
    label: 'Download storage',
    unit: 'bytes',
    window: 'standing' as const,
  },
]

const ROWS = [
  {
    membership: 'free',
    quota_kind: 'llm_tokens',
    limit_value: 500000,
    updated_at: '2026-07-31T00:00:00Z',
  },
]

function renderSection() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <QuotaSection membership="free" kinds={KINDS} rows={ROWS} />
    </QueryClientProvider>,
  )
}

describe('QuotaSection', () => {
  it('renders unlimited placeholder for kinds without a rule', () => {
    renderSection()
    expect(screen.getByDisplayValue('500000')).toBeTruthy()
    expect(screen.getAllByPlaceholderText('unlimited').length).toBe(1)
  })

  it('PUTs changed values and DELETEs blanked ones on save', async () => {
    vi.mocked(putMembershipQuota).mockResolvedValue(ROWS[0])
    vi.mocked(deleteMembershipQuota).mockResolvedValue(undefined)
    renderSection()
    fireEvent.change(screen.getByPlaceholderText('unlimited'), {
      target: { value: '1000000' },
    })
    fireEvent.change(screen.getByDisplayValue('500000'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save quotas' }))
    await waitFor(() => {
      expect(vi.mocked(putMembershipQuota)).toHaveBeenCalledWith(
        'free',
        'storage_bytes',
        1000000,
      )
      expect(vi.mocked(deleteMembershipQuota)).toHaveBeenCalledWith('free', 'llm_tokens')
    })
  })
})
```

Run: `npm run test -- QuotaSection` — expected FAIL (module not found).

- [ ] **Step 3: Implement `QuotaSection` and wire the page**

```tsx
// frontend/src/features/admin/components/policies/QuotaSection.tsx
import { useState } from 'react'
import type {
  MembershipQuotaRow,
  QuotaKindInfo,
} from '@/features/admin/api/membershipQuotas'
import { useSaveQuota } from '@/features/admin/hooks/useMembershipQuotas'
import { parsePolicyInput } from '@/features/admin/logic/policyFields'

type Props = { membership: string; kinds: QuotaKindInfo[]; rows: MembershipQuotaRow[] }

function initialDrafts(kinds: QuotaKindInfo[], rows: MembershipQuotaRow[]) {
  const byKind = new Map(rows.map((r) => [r.quota_kind, r.limit_value]))
  return Object.fromEntries(
    kinds.map((k) => [k.kind, byKind.has(k.kind) ? String(byKind.get(k.kind)) : '']),
  )
}

export function QuotaSection({ membership, kinds, rows }: Props) {
  const [drafts, setDrafts] = useState(() => initialDrafts(kinds, rows))
  const save = useSaveQuota()
  const current = new Map(rows.map((r) => [r.quota_kind, r.limit_value]))

  const onSave = () => {
    for (const meta of kinds) {
      const parsed = parsePolicyInput(drafts[meta.kind] ?? '')
      if (parsed === undefined) return
      if (parsed !== (current.get(meta.kind) ?? null)) {
        save.mutate({ membership, kind: meta.kind, limit: parsed })
      }
    }
  }

  return (
    <div className="mt-3 border-t border-border/60 pt-3">
      <p className="mb-2 text-sm font-medium">Quotas (blank = unlimited)</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {kinds.map((meta) => (
          <label key={meta.kind} className="flex flex-col gap-0.5 text-sm">
            <span className="text-muted-foreground">
              {meta.label} ({meta.unit}
              {meta.window === 'month' ? ' / month' : ', standing'})
            </span>
            <input
              className="rounded-md border border-border bg-background px-2 py-1 tabular-nums"
              inputMode="decimal"
              value={drafts[meta.kind] ?? ''}
              placeholder="unlimited"
              onChange={(event) =>
                setDrafts((prev) => ({ ...prev, [meta.kind]: event.target.value }))
              }
            />
          </label>
        ))}
      </div>
      <button
        type="button"
        className="mt-3 rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
        disabled={save.isPending}
        onClick={onSave}
      >
        {save.isPending ? 'Saving…' : 'Save quotas'}
      </button>
    </div>
  )
}
```

In `PolicyCard.tsx`: add `children?: ReactNode` to the props and render `{children}` after the invalid-message/save-button block (import `type { ReactNode } from 'react'`). In `PoliciesPage.tsx`: call `useMembershipQuotas()` alongside the policies query and render inside each card:

```tsx
        {data.policies.map((policy) => (
          <PolicyCard key={policy.membership} policy={policy} inherited={data.inherited}>
            {quotas.data ? (
              <QuotaSection
                membership={policy.membership}
                kinds={quotas.data.kinds}
                rows={quotas.data.quotas.filter((q) => q.membership === policy.membership)}
              />
            ) : null}
          </PolicyCard>
        ))}
```

Update the page's intro copy: replace "(Monthly quotas get their own section here in Part B.)" with "Quotas: blank = unlimited." If any file crosses the 110-line ESLint cap, split further (e.g. extract the quota input row) — never disable the rule.

- [ ] **Step 4: Frontend gates + commit**

```bash
npm run test
npm run lint
npm run build
printf 'feat: add quota editing to backoffice memberships screen\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 6: Usage API — per-user month usage vs LLM quota

**Files:**
- Modify: `backend/app/modules/llm/repository.py` (`usage_for_users`)
- Modify: `backend/app/modules/llm/service.py` (`usage_for_users_admin`)
- Modify: `backend/app/modules/users/repository.py` + `backend/app/modules/users/service.py` (`memberships_for_ids`)
- Modify: `backend/app/modules/admin/schemas.py` (`AdminUserUsageRead` columns)
- Modify: `backend/app/modules/admin/usage_router.py` (compose)
- Test: `backend/tests/quotas/test_admin_usage_quota_api.py`

**Interfaces:**
- Consumes: `QuotaService.list_quotas()` (Task 2), `QuotaService.current_month_window`, existing `usage_by_user_admin`, `usernames_for_ids`.
- Produces: `GET /api/admin/usage/by-user` items gain `membership: str | null`, `month_tokens: int`, `month_cost: float` (current UTC calendar month regardless of selected period), `llm_tokens_limit: float | null`, `llm_cost_limit: float | null` (null = unlimited). Task 7 and Part C's screen work depend on these names.
  - `LlmRepository.usage_for_users(user_ids, *, period_start, period_end) -> dict[UUID, UsageTotals]`
  - `LlmService.usage_for_users_admin(user_ids, *, period_start, period_end) -> dict[UUID, UserUsageRead]`
  - `UserService.memberships_for_ids(user_ids) -> dict[UUID, Membership]`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/quotas/test_admin_usage_quota_api.py
"""By-user usage rows carry membership + month usage + LLM quota (needs Postgres)."""

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
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota
from app.modules.users.membership import Membership
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
        await session.execute(delete(LlmExecution))
        await session.execute(delete(MembershipQuota))
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
    """Admin + a reader with usage this month + a free-tier token quota rule."""
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        admin = User(
            username="usage-admin",
            email="usage-admin@example.com",
            password_hash=None,
            google_sub="usage-admin-sub",
            is_admin=True,
        )
        reader = User(
            username="usage-reader",
            email="usage-reader@example.com",
            password_hash=None,
            google_sub="usage-reader-sub",
            is_admin=False,
        )
        session.add_all([admin, reader])
        await session.flush()
        session.add(
            LlmExecution(
                user_id=reader.id,
                task="chat_tools",
                provider="gemini",
                model="m",
                tokens_in=600,
                tokens_out=400,
                cost=0.25,
                latency_ms=10,
                status="ok",
            )
        )
        session.add(
            MembershipQuota(
                membership=Membership.FREE.value,
                quota_kind=QuotaKind.LLM_TOKENS.value,
                limit_value=5000.0,
            )
        )
        await session.commit()
        admin_id = admin.id
    await engine.dispose()
    return admin_id


@pytest.mark.integration
async def test_by_user_rows_include_membership_month_and_quota(
    client: AsyncClient,
) -> None:
    admin_id = await _seed()
    token = create_access_token(
        user_id=admin_id, username="usage-admin", settings=get_settings()
    )
    client.cookies.set(COOKIE_NAME, token, domain=_HOST, path="/")

    now = datetime.now(UTC)
    query = f"?from={now.year}-01-01T00:00:00Z&to={now.year + 1}-01-01T00:00:00Z"
    response = await client.get(BASE + query)
    assert response.status_code == 200
    rows = response.json()["items"]
    reader_row = next(r for r in rows if r["username"] == "usage-reader")
    assert reader_row["membership"] == "free"
    assert reader_row["month_tokens"] == 1000
    assert reader_row["month_cost"] == pytest.approx(0.25)
    assert reader_row["llm_tokens_limit"] == 5000.0
    assert reader_row["llm_cost_limit"] is None  # no rule = unlimited
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/quotas/test_admin_usage_quota_api.py -v`
Expected: FAIL — `KeyError: 'membership'` (fields absent).

- [ ] **Step 3: Repository + service methods**

Append to `LlmRepository` in `backend/app/modules/llm/repository.py` (near the other usage aggregates):

```python
    async def usage_for_users(
        self,
        user_ids: list[uuid.UUID],
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> dict[uuid.UUID, UsageTotals]:
        """Per-user aggregates for a fixed id set (backoffice quota column)."""
        if not user_ids:
            return {}
        stmt = (
            select(LlmExecution.user_id, *self._usage_sums())
            .where(
                LlmExecution.user_id.in_(user_ids),
                self._in_period(period_start, period_end),
            )
            .group_by(LlmExecution.user_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return {
            row[0]: UsageTotals(int(row[1]), int(row[2]), float(row[3]), int(row[4]))
            for row in rows
        }
```

Append to `LlmService` in `backend/app/modules/llm/service.py` (near `usage_by_user_admin`):

```python
    async def usage_for_users_admin(
        self, user_ids: list[UUID], *, period_start: datetime, period_end: datetime
    ) -> dict[UUID, UserUsageRead]:
        """Backoffice: per-user totals for a fixed id set (quota column)."""
        totals = await self._repo.usage_for_users(
            user_ids, period_start=period_start, period_end=period_end
        )
        return {uid: UserUsageRead(user_id=uid, **asdict(t)) for uid, t in totals.items()}
```

Append to `UserRepository` in `backend/app/modules/users/repository.py` (mirror `usernames_for_ids`'s style; add `from app.modules.users.membership import Membership` if missing):

```python
    async def memberships_for_ids(self, user_ids: list[UUID]) -> dict[UUID, Membership]:
        """ids -> membership tier, soft-deleted included (attribution)."""
        if not user_ids:
            return {}
        stmt = select(User.id, User.membership).where(User.id.in_(user_ids))
        rows = (await self._session.execute(stmt)).all()
        return {row[0]: Membership(row[1]) for row in rows}
```

Append to `UserService`:

```python
    async def memberships_for_ids(self, user_ids: list[UUID]) -> dict[UUID, Membership]:
        """Backoffice attribution: ids → membership tiers."""
        return await self._repo.memberships_for_ids(user_ids)
```

- [ ] **Step 4: Extend the DTO and compose in the router**

In `backend/app/modules/admin/schemas.py`:

```python
class AdminUserUsageRead(UserUsageRead):
    """Per-user usage row + identity/quota columns resolved by the admin router.

    month_* cover the CURRENT UTC calendar month regardless of the selected
    period. *_limit fields: None = unlimited (no membership_quotas rule).
    """

    username: str | None = None
    membership: str | None = None
    month_tokens: int = 0
    month_cost: float = 0.0
    llm_tokens_limit: float | None = None
    llm_cost_limit: float | None = None
```

Rewrite `usage_by_user` in `backend/app/modules/admin/usage_router.py` (add imports: `from datetime import UTC, datetime`, `from uuid import UUID`, `from app.modules.llm.schemas import UserUsageRead`, `from app.modules.quotas.kinds import QuotaKind`, `from app.modules.quotas.service import QuotaService`, `from app.modules.users.membership import Membership`):

```python
@router.get("/by-user")
async def usage_by_user(
    period: Annotated[PeriodParams, Depends()],
    page: Annotated[PageParams, Depends()],
    _admin: Annotated[UserRead, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[LlmService, Depends(_llm)],
) -> Page[AdminUserUsageRead]:
    """Per-user usage rows + membership, current-month usage, and LLM quota."""
    rows, total = await service.usage_by_user_admin(
        period_start=period.period_start,
        period_end=period.period_end,
        limit=page.limit,
        offset=page.offset,
    )
    items = await _decorate_rows(session, service, rows)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


async def _decorate_rows(
    session: AsyncSession,
    service: LlmService,
    rows: list[UserUsageRead],
) -> list[AdminUserUsageRead]:
    """Join usernames, tiers, current-month usage, and LLM quota rules."""
    users = UserService(session)
    ids = [row.user_id for row in rows]
    names = await users.usernames_for_ids(ids)
    tiers = await users.memberships_for_ids(ids)
    month_start, month_end = QuotaService.current_month_window(datetime.now(UTC))
    month = await service.usage_for_users_admin(
        ids, period_start=month_start, period_end=month_end
    )
    quotas: dict[tuple[str, str], float] = {
        (q.membership, q.quota_kind): q.limit_value
        for q in await QuotaService(session).list_quotas()
    }
    return [_decorated_row(row, names, tiers, month, quotas) for row in rows]


def _decorated_row(
    row: UserUsageRead,
    names: dict[UUID, str],
    tiers: dict[UUID, Membership],
    month: dict[UUID, UserUsageRead],
    quotas: dict[tuple[str, str], float],
) -> AdminUserUsageRead:
    tier = tiers.get(row.user_id)
    tier_value = tier.value if tier is not None else None
    month_row = month.get(row.user_id)
    return AdminUserUsageRead(
        username=names.get(row.user_id),
        membership=tier_value,
        month_tokens=(month_row.tokens_in + month_row.tokens_out) if month_row else 0,
        month_cost=month_row.total_cost if month_row else 0.0,
        llm_tokens_limit=quotas.get((tier_value or "", QuotaKind.LLM_TOKENS.value)),
        llm_cost_limit=quotas.get((tier_value or "", QuotaKind.LLM_COST_USD.value)),
        **row.model_dump(),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/quotas/test_admin_usage_quota_api.py -v`
Expected: PASS (1 test)

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add membership, month usage, and LLM quota to admin by-user usage API\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 7: Usage screen shows current-month usage vs LLM quota

**Files:**
- Modify: `frontend/src/features/admin/api/usage.ts` (`UserUsage` type)
- Modify: `frontend/src/features/admin/components/usage/ByUserTable.tsx` (columns)
- Modify: `frontend/src/features/admin/components/usage/UsagePage.test.tsx` (extend mocks if they cover the by-user fetch)

**Interfaces:**
- Consumes: Task 6's response fields (`membership`, `month_tokens`, `month_cost`, `llm_tokens_limit`, `llm_cost_limit`).
- Produces: "This month" and "Quota" columns on the By-user table (null limit renders "—" = unlimited). Part C appends its job-dimension columns to the same table.

- [ ] **Step 1: Extend the type**

In `frontend/src/features/admin/api/usage.ts`:

```typescript
export type UserUsage = UsageBreakdown & {
  user_id: string
  username: string | null
  membership: string | null
  month_tokens: number
  month_cost: number
  llm_tokens_limit: number | null
  llm_cost_limit: number | null
}
```

- [ ] **Step 2: Add the columns**

In `frontend/src/features/admin/components/usage/ByUserTable.tsx`, add a module-level helper above the component (import `type { UserUsage } from '@/features/admin/api/usage'`):

```typescript
function quotaLabel(row: UserUsage): string {
  const tokens =
    row.llm_tokens_limit === null ? '—' : row.llm_tokens_limit.toLocaleString()
  const cost = row.llm_cost_limit === null ? '—' : `$${row.llm_cost_limit.toFixed(2)}`
  return `${tokens} tok · ${cost}`
}
```

Add two `<th>` entries after "Cost":

```tsx
              <th className="px-2 py-1.5 font-medium">This month</th>
              <th className="px-2 py-1.5 font-medium">Quota</th>
```

and matching cells after the Cost cell:

```tsx
                <td className="px-2 py-1.5">
                  {row.month_tokens.toLocaleString()} tok · ${row.month_cost.toFixed(4)}
                </td>
                <td className="px-2 py-1.5">{quotaLabel(row)}</td>
```

If the file crosses the 110-line ESLint cap, extract the `<tr>` body into a `ByUserRow` component file — do not disable the rule.

- [ ] **Step 3: Update tests and run gates**

Check `frontend/src/features/admin/components/usage/UsagePage.test.tsx`: if its mocks include by-user rows, extend each mock row with the five new fields (`membership: 'free'`, `month_tokens: 0`, `month_cost: 0`, `llm_tokens_limit: null`, `llm_cost_limit: null`) so TypeScript compiles; assertions stay as-is.

```bash
npm run test
npm run lint
npm run build
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
printf 'feat: show current-month usage vs LLM quota on admin usage screen\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```
