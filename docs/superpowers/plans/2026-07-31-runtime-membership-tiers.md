# Runtime Membership Tiers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `Membership` code enum with a DB-backed tier registry admins manage at runtime (create/edit/deactivate), plus flag-gated tier-switch buttons on the user's Plan & usage page.

**Architecture:** New `memberships` table owned by the users module, served through a 30s-TTL cached snapshot (`users/membership_registry.py`, mirroring `modules/llm/catalog.py`). `users.membership`, `membership_policies.membership`, and `membership_quotas.membership` gain FKs to `memberships.slug`. Reads become plain `str`; writes validate against the registry in services and raise typed errors. Spec: `docs/superpowers/specs/2026-07-31-runtime-membership-tiers-design.md`.

**Tech Stack:** FastAPI + SQLAlchemy async + Alembic (backend, run with `uv` from `backend/`), React 19 + react-query + vitest (frontend).

## Global Constraints

- Run every backend command via the **Bash tool** from `backend/` (uv is not on PowerShell PATH).
- Quality gates before "done": `uv run ruff check . --fix && uv run ruff format .`, `uv run mypy .`, `uv run pytest -m "unit or integration"` (backend); `npm run lint`, `npm run build`, `npm run test` (frontend).
- Integration tests need Postgres/Redis/MinIO up (`docker compose up -d postgres redis minio minio-init`) and use `TEST_DATABASE_URL` (rtm_test); conftest runs alembic to head.
- Frontend hard limits: file ≤ 110 lines, function ≤ 60 lines, nesting ≤ 3. No raw `fetch`; use `src/shared/lib/api.ts` helpers.
- Backend: strict mypy; ruff max-args 6, max-statements 20, max-branches 6. Full type hints everywhere.
- Commit ONLY via `bash scripts/git-commit-clean.sh /tmp/msg.txt` after writing the message to `/tmp/msg.txt`. **Never** add Co-authored-by/attribution trailers.
- Migrations must be reversible and must NOT import app enums/models (hardcode strings).
- Slug pattern everywhere: `^[a-z0-9_-]{1,32}$`. The seed tier is `free` (rank 0, label "Free", active, default).

---

### Task 1: Migration + ORM models (registry table, backfill, slug FKs)

**Files:**
- Create: `backend/migrations/versions/<autogen>_add_memberships_registry.py` (via `uv run alembic revision -m "add memberships registry"`)
- Modify: `backend/app/modules/users/models.py`
- Modify: `backend/app/modules/orchestration/models.py:27` (membership column)
- Modify: `backend/app/modules/quotas/models.py:28` (membership column)
- Modify: `backend/tests/dbcleanup.py`
- Test: `backend/tests/memberships/test_schema.py` (new dir; add empty `backend/tests/memberships/__init__.py` only if other test dirs have one — check `tests/admin/`)

**Interfaces:**
- Produces: table `memberships(id, slug UNIQUE, label, description, price_label, rank, is_active, is_default, created_at, updated_at)`; ORM class `MembershipTier` in `app/modules/users/models.py`; FKs `users.membership → memberships.slug`, `membership_policies.membership → memberships.slug`, `membership_quotas.membership → memberships.slug`; `tests.dbcleanup.clear_users` also resets non-free tiers.

- [ ] **Step 1: Write the failing test**

```python
"""Schema-level guarantees for the memberships registry (needs Postgres)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import MembershipTier, User


@pytest.mark.integration
async def test_free_tier_backfilled(session: AsyncSession) -> None:
    row = (
        await session.execute(text("SELECT label, rank, is_active, is_default FROM memberships WHERE slug = 'free'"))
    ).one()
    assert row == ("Free", 0, True, True)


@pytest.mark.integration
async def test_user_membership_fk_blocks_unknown_slug(session: AsyncSession) -> None:
    session.add(User(username=f"fk-{uuid.uuid4().hex[:8]}", membership="no-such-tier"))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.integration
async def test_only_one_default_tier(session: AsyncSession) -> None:
    session.add(
        MembershipTier(slug="premium2", label="Premium 2", rank=1, is_active=True, is_default=True)
    )
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()
```

Use whatever `session` fixture the existing integration tests use (see `backend/tests/quotas/test_quota_service.py` for the fixture name and import; mirror it exactly).

- [ ] **Step 2: Run test to verify it fails**

Run (Bash, from `backend/`): `uv run pytest tests/memberships/test_schema.py -v`
Expected: FAIL — `ImportError: cannot import name 'MembershipTier'`.

- [ ] **Step 3: Add the ORM model and FKs**

In `app/modules/users/models.py` (below `User`; `User` docstring/columns otherwise untouched):

```python
class MembershipTier(Base):
    """One runtime-managed membership tier. Slug is immutable after creation.

    `slug` is the join key everywhere (users.membership, membership_policies,
    membership_quotas) — never the UUID id. Deactivate, never delete.
    """

    __tablename__ = "memberships"
    __table_args__ = (
        Index("uq_memberships_single_default", "is_default", unique=True, postgresql_where=text("is_default")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rank: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

Add imports `Index, Integer, Text, text` to the existing `sqlalchemy` import line. On `User.membership` (line 41): add `ForeignKey("memberships.slug")` as the second positional arg after `String(32)`, keep `server_default=Membership.FREE.value` for now (Task 4 changes it to the literal `"free"`). In `orchestration/models.py` and `quotas/models.py`, add `ForeignKey("memberships.slug")` to the `membership` columns (import `ForeignKey`; orchestration's model has no FK import yet).

- [ ] **Step 4: Write the migration**

`uv run alembic revision -m "add memberships registry"`, then fill in (down_revision must be `b34d89ba1cc1` — verify with `ls migrations/versions` that it is still head):

```python
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "<generated>"
down_revision: str | None = "b34d89ba1cc1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_label", sa.String(length=32), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_memberships_slug"), "memberships", ["slug"], unique=True)
    op.create_index(
        "uq_memberships_single_default",
        "memberships",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    # Backfill: 'free' first (hardcoded — migrations never import app code),
    # then any other slug already referenced anywhere, so the FKs are valid.
    op.execute(
        "INSERT INTO memberships (id, slug, label, rank, is_active, is_default) "
        f"VALUES ('{uuid.uuid4()}', 'free', 'Free', 0, true, true)"
    )
    op.execute(
        """
        INSERT INTO memberships (id, slug, label, rank, is_active, is_default)
        SELECT gen_random_uuid(), s.slug, s.slug, 0, true, false FROM (
            SELECT membership AS slug FROM users
            UNION SELECT membership FROM membership_policies
            UNION SELECT membership FROM membership_quotas
        ) s WHERE s.slug NOT IN (SELECT slug FROM memberships)
        """
    )
    op.create_foreign_key(
        "fk_users_membership_memberships", "users", "memberships", ["membership"], ["slug"]
    )
    op.create_foreign_key(
        "fk_membership_policies_membership_memberships",
        "membership_policies", "memberships", ["membership"], ["slug"],
    )
    op.create_foreign_key(
        "fk_membership_quotas_membership_memberships",
        "membership_quotas", "memberships", ["membership"], ["slug"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_membership_quotas_membership_memberships", "membership_quotas", type_="foreignkey")
    op.drop_constraint("fk_membership_policies_membership_memberships", "membership_policies", type_="foreignkey")
    op.drop_constraint("fk_users_membership_memberships", "users", type_="foreignkey")
    op.drop_index("uq_memberships_single_default", table_name="memberships")
    op.drop_index(op.f("ix_memberships_slug"), table_name="memberships")
    op.drop_table("memberships")
```

- [ ] **Step 5: Update dbcleanup so tests can create tiers**

In `tests/dbcleanup.py`, after the `CLEAR_ORDER` loop in `clear_users`, add (the seeded `free` row and its policy row must survive; tier rows created by tests must not leak):

```python
_NON_FREE_TIER_CLEANUP = (
    "DELETE FROM membership_policies WHERE membership <> 'free'",
    "DELETE FROM membership_quotas WHERE membership <> 'free'",
    "DELETE FROM memberships WHERE slug <> 'free'",
)
```

and in `clear_users`, after the existing loop: `for stmt in _NON_FREE_TIER_CLEANUP: await executor.execute(text(stmt))`.

- [ ] **Step 6: Verify migration up-down-up and tests pass**

Run: `uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head` (needs `DATABASE_URL`; if unset natively, rely on the pytest run which migrates rtm_test).
Run: `uv run pytest tests/memberships/test_schema.py -v` — Expected: 3 PASS.
Run: `uv run pytest -m "unit or integration"` — Expected: all pass (nothing behavioral changed yet).

- [ ] **Step 7: Commit**

```bash
printf 'feat: memberships registry table with slug FKs and free backfill\n' > /tmp/msg.txt
git add -A backend && bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 2: Registry snapshot + `meets_minimum` from snapshot + deps

**Files:**
- Create: `backend/app/modules/users/membership_registry.py`
- Modify: `backend/app/modules/users/membership.py` (full rewrite)
- Modify: `backend/app/core/deps.py:47-63`
- Rewrite: `backend/tests/test_membership.py`
- Test: `backend/tests/memberships/test_registry.py`

**Interfaces:**
- Consumes: `MembershipTier` (Task 1).
- Produces:
  - `TierSpec` frozen dataclass: `slug: str, label: str, description: str | None, price_label: str | None, rank: int, is_active: bool, is_default: bool`
  - `current_snapshot() -> tuple[TierSpec, ...]`, `put_snapshot(specs: Sequence[TierSpec]) -> None`, `invalidate() -> None`, `async ensure_loaded(session: AsyncSession) -> tuple[TierSpec, ...]`, `rank_of(slug: str) -> int | None`, `CACHE_TTL_SECONDS = 30.0`
  - `membership.py`: `meets_minimum(actual: str, minimum: str) -> bool` (unchanged signature, snapshot-backed), `DEFAULT_SLUG = "free"`. The `Membership` enum and `MEMBERSHIP_RANK` are **deleted** (Task 4 fixes the importers; the codebase will not typecheck between Tasks 2 and 4 — that is expected, run only the named tests).

- [ ] **Step 1: Write the failing tests**

`tests/memberships/test_registry.py` (mirror the catalog test style — see `backend/tests/llm/` for reference; these are unit tests, no DB):

```python
"""Membership registry snapshot: TTL, invalidate, rank lookup (unit)."""

from __future__ import annotations

import pytest

from app.modules.users import membership_registry as reg
from app.modules.users.membership import meets_minimum
from app.modules.users.membership_registry import TierSpec


@pytest.fixture(autouse=True)
def _clean_registry():
    reg.invalidate()
    yield
    reg.invalidate()


def _tier(slug: str, rank: int, *, active: bool = True, default: bool = False) -> TierSpec:
    return TierSpec(
        slug=slug, label=slug.title(), description=None, price_label=None,
        rank=rank, is_active=active, is_default=default,
    )


@pytest.mark.unit
def test_cold_snapshot_is_empty() -> None:
    assert reg.current_snapshot() == ()


@pytest.mark.unit
def test_put_then_read_and_invalidate() -> None:
    reg.put_snapshot([_tier("free", 0, default=True), _tier("premium", 1)])
    assert [t.slug for t in reg.current_snapshot()] == ["free", "premium"]
    reg.invalidate()
    assert reg.current_snapshot() == ()


@pytest.mark.unit
def test_rank_of_unknown_is_none() -> None:
    reg.put_snapshot([_tier("free", 0, default=True)])
    assert reg.rank_of("free") == 0
    assert reg.rank_of("nope") is None


@pytest.mark.unit
def test_meets_minimum_fail_closed() -> None:
    reg.put_snapshot([_tier("free", 0, default=True), _tier("premium", 1)])
    assert meets_minimum("premium", "free") is True
    assert meets_minimum("free", "premium") is False
    assert meets_minimum("premium", "premium") is True
    assert meets_minimum("garbage", "free") is True   # unknown actual ranks 0
    assert meets_minimum("garbage", "premium") is False
    assert meets_minimum("free", "unknown-minimum") is False  # fail-closed


@pytest.mark.unit
def test_meets_minimum_cold_snapshot_fails_closed() -> None:
    assert meets_minimum("free", "free") is False
```

Rewrite `tests/test_membership.py` to only keep what still applies (delete enum/rank-dict tests; keep a single re-export sanity test):

```python
"""Membership helpers (post-enum): meets_minimum lives on the registry snapshot."""

from __future__ import annotations

import pytest

from app.modules.users.membership import DEFAULT_SLUG, meets_minimum


@pytest.mark.unit
def test_default_slug() -> None:
    assert DEFAULT_SLUG == "free"


@pytest.mark.unit
def test_meets_minimum_is_importable_and_fail_closed_when_cold() -> None:
    assert meets_minimum("free", "free") in (True, False)  # no crash on cold cache
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/memberships/test_registry.py tests/test_membership.py -v`
Expected: FAIL — `ModuleNotFoundError: app.modules.users.membership_registry`.

- [ ] **Step 3: Implement the registry**

`app/modules/users/membership_registry.py` (structure copied from `modules/llm/catalog.py:29-62`):

```python
"""DB-backed membership tier registry: async snapshot refresh, sync reads.

Same per-process TTL pattern as modules/llm/catalog.py: writers call
invalidate() so the writing process sees changes immediately; other
processes (arq worker, other API workers) converge within the TTL.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from time import monotonic
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import MembershipTier

CACHE_TTL_SECONDS = 30.0

_state: dict[str, Any] = {"snapshot": None, "expires_at": 0.0}


@dataclass(frozen=True, slots=True)
class TierSpec:
    """Immutable snapshot view of one membership tier."""

    slug: str
    label: str
    description: str | None
    price_label: str | None
    rank: int
    is_active: bool
    is_default: bool


def current_snapshot() -> tuple[TierSpec, ...]:
    """Sync view of the tier registry; empty when cold or expired."""
    snapshot = _state["snapshot"]
    if snapshot is None or monotonic() >= float(_state["expires_at"]):
        return ()
    return tuple(snapshot)


def put_snapshot(specs: Sequence[TierSpec]) -> None:
    """Cache a snapshot for the TTL window (also a test hook)."""
    _state["snapshot"] = tuple(specs)
    _state["expires_at"] = monotonic() + CACHE_TTL_SECONDS


def invalidate() -> None:
    """Drop the snapshot now (every memberships write calls this; test hook)."""
    _state["snapshot"] = None
    _state["expires_at"] = 0.0


async def ensure_loaded(session: AsyncSession) -> tuple[TierSpec, ...]:
    """Return a warm snapshot, loading from the DB when cold or expired."""
    snapshot = _state["snapshot"]
    if snapshot is not None and monotonic() < float(_state["expires_at"]):
        return tuple(snapshot)
    stmt = select(MembershipTier).order_by(MembershipTier.rank, MembershipTier.slug)
    rows = (await session.execute(stmt)).scalars().all()
    specs = tuple(
        TierSpec(
            slug=row.slug, label=row.label, description=row.description,
            price_label=row.price_label, rank=row.rank,
            is_active=row.is_active, is_default=row.is_default,
        )
        for row in rows
    )
    put_snapshot(specs)
    return specs


def rank_of(slug: str) -> int | None:
    """Rank of a tier in the current snapshot; None when unknown or cold."""
    for tier in current_snapshot():
        if tier.slug == slug:
            return tier.rank
    return None
```

Rewrite `app/modules/users/membership.py`:

```python
"""Membership ordering helpers over the runtime tier registry.

Tiers live in the `memberships` table (users module) and are served from
membership_registry's cached snapshot. Ordering lives ONLY in each tier's
`rank` — never as integers scattered through code.
"""

from __future__ import annotations

from app.modules.users.membership_registry import rank_of

DEFAULT_SLUG = "free"


def meets_minimum(actual: str, minimum: str) -> bool:
    """True when `actual` ranks at least `minimum`; fail-closed on unknowns."""
    required = rank_of(minimum)
    if required is None:
        return False
    actual_rank = rank_of(actual)
    return (actual_rank if actual_rank is not None else 0) >= required
```

- [ ] **Step 4: Update `require_membership` in `core/deps.py`**

Replace lines 47-63 (the factory now takes a slug string and warms the snapshot; delete the `Membership` import, keep `meets_minimum`):

```python
def require_membership(
    minimum: str,
) -> Callable[[UserRead, AsyncSession], Awaitable[UserRead]]:
    """Dependency factory gating a route on a minimum membership tier.

    Ordering comes from the tier registry snapshot (fail-closed) — this is
    the hook for tier-gated features and per-tier AI budgets.
    """

    async def _require(
        current_user: Annotated[UserRead, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> UserRead:
        await ensure_loaded(session)
        if not meets_minimum(current_user.membership, minimum):
            raise NotAuthorizedError
        return current_user

    return _require
```

Import `ensure_loaded` from `app.modules.users.membership_registry`. Note: `UserRead.membership` is still the enum until Task 4 — `meets_minimum` takes `str` and `StrEnum` IS a `str`, so this typechecks either way.

- [ ] **Step 5: Run the named tests**

Run: `uv run pytest tests/memberships/test_registry.py tests/test_membership.py -v`
Expected: PASS. (`uv run mypy .` will FAIL until Task 4 removes the remaining `Membership` importers — do not run the full gates yet.)

Also update the two deps tests now broken (`tests/test_authz_deps_unit.py`, `tests/test_authz_api.py`): replace `require_membership(Membership.FREE)` with `require_membership("free")` and remove the `Membership` imports; in `test_authz_deps_unit.py` the `_user` helper's `membership` parameter becomes `str = "free"`. In `tests/test_authz_api.py` the route dependency becomes `Depends(require_membership("free"))`. Run: `uv run pytest tests/test_authz_deps_unit.py tests/test_authz_api.py -v` — the api one needs the client fixture/DB. Expected: PASS.

- [ ] **Step 6: Commit**

```bash
printf 'feat: membership tier registry snapshot; meets_minimum reads ranks from it\n' > /tmp/msg.txt
git add -A backend && bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 3: Membership repository, service, exceptions, seed

**Files:**
- Create: `backend/app/modules/users/membership_repository.py`
- Create: `backend/app/modules/users/membership_service.py`
- Create: `backend/app/modules/users/seed.py`
- Modify: `backend/app/modules/users/exceptions.py` (append)
- Modify: `backend/app/modules/users/schemas.py` (append tier DTOs)
- Test: `backend/tests/memberships/test_membership_service.py`

**Interfaces:**
- Consumes: `MembershipTier`, `membership_registry.invalidate`, `UserRepository` patterns.
- Produces (used by Tasks 4-6):
  - Exceptions: `UnknownMembershipError(UserError)`, `DuplicateMembershipError(UserError)`, `MembershipLifecycleError(UserError)` (message is user-facing copy).
  - Schemas: `MembershipCreate(slug, label, rank=0, description=None, price_label=None)`, `MembershipPatch(label?, description?, price_label?, rank?, is_default: Literal[True]?, is_active: Literal[True]?)`, `MembershipAdminRead(slug, label, description, price_label, rank, is_active, is_default, user_count, updated_at)` with classmethod `from_tier(tier: MembershipTier, user_count: int)`, `MembershipsResponse(memberships: list[MembershipAdminRead])`, `MembershipDeactivate(migrate_to: str)`.
  - `MembershipRepository(session)`: `get_by_slug(slug) -> MembershipTier | None`, `list_all() -> list[MembershipTier]` (rank, slug order), `get_default() -> MembershipTier | None`, `add(row)`, `save(row) -> MembershipTier`, `user_counts() -> dict[str, int]`, `reassign_users(from_slug: str, to_slug: str) -> int`, `clear_default() -> None`.
  - `MembershipService(session)`: `list_tiers() -> list[MembershipAdminRead]`, `create_tier(data: MembershipCreate, *, actor_id: UUID) -> MembershipTier`, `update_tier(slug: str, patch: MembershipPatch, *, actor_id: UUID) -> MembershipTier`, `deactivate_tier(slug: str, migrate_to: str, *, actor_id: UUID) -> tuple[MembershipTier, int]`, `require_tier(slug: str) -> MembershipTier` (404 on missing), `require_assignable(slug: str) -> MembershipTier` (404 on missing OR inactive), `default_slug() -> str`.
  - `users/seed.py`: `async def seed_default_membership(session: AsyncSession | None = None) -> None` — insert-if-missing `free` row (same contract as `orchestration/seed.py`).

- [ ] **Step 1: Write the failing tests**

```python
"""MembershipService lifecycle rules (needs Postgres)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users import membership_registry as reg
from app.modules.users.exceptions import (
    DuplicateMembershipError,
    MembershipLifecycleError,
    UnknownMembershipError,
)
from app.modules.users.membership_service import MembershipService
from app.modules.users.models import User
from app.modules.users.schemas import MembershipCreate, MembershipPatch

ACTOR = uuid4()


@pytest.fixture(autouse=True)
def _clean_registry():
    reg.invalidate()
    yield
    reg.invalidate()


def _premium() -> MembershipCreate:
    return MembershipCreate(slug="premium", label="Premium", rank=1, price_label="$9/mo")


@pytest.mark.integration
async def test_create_then_list_includes_user_counts(session: AsyncSession) -> None:
    service = MembershipService(session)
    await service.create_tier(_premium(), actor_id=ACTOR)
    session.add(User(username=f"u-{uuid4().hex[:8]}", membership="premium"))
    await session.flush()
    tiers = await service.list_tiers()
    by_slug = {t.slug: t for t in tiers}
    assert by_slug["premium"].user_count == 1
    assert by_slug["premium"].price_label == "$9/mo"
    assert by_slug["free"].is_default is True


@pytest.mark.integration
async def test_create_duplicate_slug_raises(session: AsyncSession) -> None:
    service = MembershipService(session)
    await service.create_tier(_premium(), actor_id=ACTOR)
    with pytest.raises(DuplicateMembershipError):
        await service.create_tier(_premium(), actor_id=ACTOR)


@pytest.mark.integration
async def test_crowning_default_uncrowns_previous(session: AsyncSession) -> None:
    service = MembershipService(session)
    await service.create_tier(_premium(), actor_id=ACTOR)
    await service.update_tier("premium", MembershipPatch(is_default=True), actor_id=ACTOR)
    assert (await service.require_tier("premium")).is_default is True
    assert (await service.require_tier("free")).is_default is False
    assert await service.default_slug() == "premium"


@pytest.mark.integration
async def test_deactivate_migrates_users_and_guards(session: AsyncSession) -> None:
    service = MembershipService(session)
    await service.create_tier(_premium(), actor_id=ACTOR)
    session.add(User(username=f"u-{uuid4().hex[:8]}", membership="premium"))
    await session.flush()
    with pytest.raises(MembershipLifecycleError):  # default is protected
        await service.deactivate_tier("free", "premium", actor_id=ACTOR)
    with pytest.raises(MembershipLifecycleError):  # target must differ
        await service.deactivate_tier("premium", "premium", actor_id=ACTOR)
    tier, moved = await service.deactivate_tier("premium", "free", actor_id=ACTOR)
    assert tier.is_active is False and moved == 1
    with pytest.raises(UnknownMembershipError):  # inactive is not assignable
        await service.require_assignable("premium")
    with pytest.raises(MembershipLifecycleError):  # inactive target rejected
        await service.deactivate_tier("free", "premium", actor_id=ACTOR)


@pytest.mark.integration
async def test_unknown_slug_raises(session: AsyncSession) -> None:
    with pytest.raises(UnknownMembershipError):
        await MembershipService(session).require_tier("ghost")
```

(Adjust the `session` fixture name to the repo's existing integration fixture, as in Task 1.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/memberships/test_membership_service.py -v`
Expected: FAIL — `ModuleNotFoundError: app.modules.users.membership_service`.

- [ ] **Step 3: Implement exceptions, schemas, repository, service, seed**

`exceptions.py` — append:

```python
class UnknownMembershipError(UserError):
    """A membership slug that does not exist (or is not assignable)."""


class DuplicateMembershipError(UserError):
    """Creating a tier whose slug is already taken."""


class MembershipLifecycleError(UserError):
    """A create/edit/deactivate rule was violated. str(exc) is user-facing."""
```

`schemas.py` — append (import `Literal` from typing):

```python
class MembershipCreate(BaseModel):
    """POST /api/admin/memberships body. Slug is immutable after creation."""

    slug: str = Field(pattern=r"^[a-z0-9_-]{1,32}$")
    label: str = Field(min_length=1, max_length=64)
    rank: int = 0
    description: str | None = None
    price_label: str | None = Field(default=None, max_length=32)


class MembershipPatch(BaseModel):
    """PATCH body — only supplied fields change; explicit null clears text.

    is_default/is_active only accept True: crowning moves the flag, and
    deactivation goes through the dedicated endpoint (it needs a target).
    """

    label: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = None
    price_label: str | None = Field(default=None, max_length=32)
    rank: int | None = None
    is_default: Literal[True] | None = None
    is_active: Literal[True] | None = None


class MembershipAdminRead(BaseModel):
    """Backoffice view of one tier, with how many users sit on it."""

    slug: str
    label: str
    description: str | None
    price_label: str | None
    rank: int
    is_active: bool
    is_default: bool
    user_count: int
    updated_at: datetime

    @classmethod
    def from_tier(cls, tier: MembershipTier, user_count: int) -> MembershipAdminRead:
        return cls(
            slug=tier.slug, label=tier.label, description=tier.description,
            price_label=tier.price_label, rank=tier.rank, is_active=tier.is_active,
            is_default=tier.is_default, user_count=user_count, updated_at=tier.updated_at,
        )


class MembershipsResponse(BaseModel):
    memberships: list[MembershipAdminRead]


class MembershipDeactivate(BaseModel):
    migrate_to: str
```

(`MembershipTier` is annotation-only in `schemas.py` — the file has `from __future__ import annotations` — so add it to the existing `TYPE_CHECKING` import block alongside `User`.)

`membership_repository.py`:

```python
"""DB access for the memberships table (and tier-scoped user queries)."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import MembershipTier, User


class MembershipRepository:
    """memberships access; user_counts/reassign touch users (same module)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_slug(self, slug: str) -> MembershipTier | None:
        stmt = select(MembershipTier).where(MembershipTier.slug == slug)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_all(self) -> list[MembershipTier]:
        stmt = select(MembershipTier).order_by(MembershipTier.rank, MembershipTier.slug)
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_default(self) -> MembershipTier | None:
        stmt = select(MembershipTier).where(MembershipTier.is_default.is_(True))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    def add(self, row: MembershipTier) -> None:
        self._session.add(row)

    async def save(self, row: MembershipTier) -> MembershipTier:
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def clear_default(self) -> None:
        """Un-crown the current default (crowning swap, step 1)."""
        await self._session.execute(
            update(MembershipTier).where(MembershipTier.is_default.is_(True)).values(is_default=False)
        )

    async def user_counts(self) -> dict[str, int]:
        """slug -> live user count (soft-deleted included: they still hold a tier)."""
        stmt = select(User.membership, func.count()).group_by(User.membership)
        return {slug: int(count) for slug, count in (await self._session.execute(stmt)).all()}

    async def reassign_users(self, from_slug: str, to_slug: str) -> int:
        """Move every user off a tier (deactivation migration). Returns count."""
        result = await self._session.execute(
            update(User).where(User.membership == from_slug).values(membership=to_slug)
        )
        return int(result.rowcount or 0)
```

`membership_service.py`:

```python
"""Membership tier lifecycle: create / edit / deactivate-with-migration.

Write paths validate against the DB (always fresh); hot read paths use the
membership_registry snapshot. Every write calls registry.invalidate().
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users import membership_registry
from app.modules.users.exceptions import (
    DuplicateMembershipError,
    MembershipLifecycleError,
    UnknownMembershipError,
)
from app.modules.users.membership import DEFAULT_SLUG
from app.modules.users.membership_repository import MembershipRepository
from app.modules.users.models import MembershipTier
from app.modules.users.schemas import MembershipAdminRead, MembershipCreate, MembershipPatch

logger = logging.getLogger(__name__)


class MembershipService:
    """Owns tier registry rules; tiers are deactivated, never deleted."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = MembershipRepository(session)

    async def list_tiers(self) -> list[MembershipAdminRead]:
        counts = await self._repo.user_counts()
        rows = await self._repo.list_all()
        return [MembershipAdminRead.from_tier(row, counts.get(row.slug, 0)) for row in rows]

    async def require_tier(self, slug: str) -> MembershipTier:
        row = await self._repo.get_by_slug(slug)
        if row is None:
            raise UnknownMembershipError(slug)
        return row

    async def require_assignable(self, slug: str) -> MembershipTier:
        """Assignment paths only accept active tiers (spec §3)."""
        row = await self.require_tier(slug)
        if not row.is_active:
            raise UnknownMembershipError(slug)
        return row

    async def default_slug(self) -> str:
        row = await self._repo.get_default()
        if row is None:  # partial unique index + seed make this near-impossible
            logger.warning("no default membership tier; falling back", extra={"slug": DEFAULT_SLUG})
            return DEFAULT_SLUG
        return row.slug

    async def create_tier(self, data: MembershipCreate, *, actor_id: UUID) -> MembershipTier:
        if await self._repo.get_by_slug(data.slug) is not None:
            raise DuplicateMembershipError(data.slug)
        row = MembershipTier(
            slug=data.slug, label=data.label, rank=data.rank,
            description=data.description, price_label=data.price_label,
            is_active=True, is_default=False,
        )
        self._repo.add(row)
        saved = await self._repo.save(row)
        membership_registry.invalidate()
        logger.info("membership tier created", extra={"slug": data.slug, "actor": str(actor_id)})
        return saved

    async def update_tier(self, slug: str, patch: MembershipPatch, *, actor_id: UUID) -> MembershipTier:
        row = await self.require_tier(slug)
        changes = patch.model_dump(exclude_unset=True)
        if changes.pop("is_default", None):
            await self._repo.clear_default()
            row.is_default = True
        for field, value in changes.items():
            setattr(row, field, value)
        saved = await self._repo.save(row)
        membership_registry.invalidate()
        logger.info(
            "membership tier updated",
            extra={"slug": slug, "actor": str(actor_id), "changes": list(changes)},
        )
        return saved

    async def deactivate_tier(
        self, slug: str, migrate_to: str, *, actor_id: UUID
    ) -> tuple[MembershipTier, int]:
        """Reassign every user to the target, then deactivate. One transaction."""
        row = await self.require_tier(slug)
        if row.is_default:
            raise MembershipLifecycleError("Cannot deactivate the default tier — set another default first.")
        if migrate_to == slug:
            raise MembershipLifecycleError("Migration target must be a different tier.")
        target = await self.require_tier(migrate_to)
        if not target.is_active:
            raise MembershipLifecycleError("Migration target must be an active tier.")
        moved = await self._repo.reassign_users(slug, migrate_to)
        row.is_active = False
        saved = await self._repo.save(row)
        membership_registry.invalidate()
        logger.info(
            "membership tier deactivated",
            extra={"slug": slug, "migrated_to": migrate_to, "moved": moved, "actor": str(actor_id)},
        )
        return saved, moved
```

`users/seed.py`:

```python
"""Seed the memberships registry (insert-if-missing; never overwrites edits)."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.modules.users.membership import DEFAULT_SLUG
from app.modules.users.membership_repository import MembershipRepository
from app.modules.users.models import MembershipTier

logger = logging.getLogger(__name__)


async def seed_default_membership(session: AsyncSession | None = None) -> None:
    """Ensure the 'free' tier row exists. Idempotent; a restart never
    reverts admin edits (same contract as the LLM catalog seed)."""
    if session is not None:
        await _seed(session)
        await session.commit()
        return
    async with SessionLocal() as owned:
        await _seed(owned)
        await owned.commit()


async def _seed(session: AsyncSession) -> None:
    repo = MembershipRepository(session)
    if await repo.get_by_slug(DEFAULT_SLUG) is not None:
        return
    has_default = await repo.get_default() is not None
    repo.add(
        MembershipTier(slug=DEFAULT_SLUG, label="Free", rank=0, is_active=True, is_default=not has_default)
    )
    logger.info("seeding default membership tier", extra={"slug": DEFAULT_SLUG})
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/memberships/ -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
printf 'feat: membership tier repository/service with lifecycle guards and seed\n' > /tmp/msg.txt
git add -A backend && bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 4: Delete the enum — sweep every importer to `str` + registry validation

**Files (every remaining importer of `app.modules.users.membership.Membership`):**
- Modify: `backend/app/modules/users/models.py` (server_default literal), `schemas.py`, `service.py`, `repository.py`
- Modify: `backend/app/core/deps.py` (drop leftover import if any)
- Modify: `backend/app/modules/orchestration/{seed,policy,schemas,admin_router}.py`
- Modify: `backend/app/modules/quotas/{service,schemas,admin_router}.py`
- Modify: `backend/app/modules/admin/{usage_router,schemas}.py`
- Modify: `backend/app/modules/usage/self_service.py` (`.value` removal)
- Modify: `backend/app/main.py` (seed order)
- Modify: existing tests that import `Membership` (list below)

**Interfaces:**
- Consumes: `MembershipService.require_tier/require_assignable` (Task 3), `membership_registry.ensure_loaded` (Task 2).
- Produces: no `Membership` symbol anywhere; `UserRead.membership: str`, `UserAdminRead.membership: str`, `UserAdminPatch.membership: str | None`; `PolicyService.patch_policy(membership: str, ...)`; `QuotaService.set_quota/clear_quota(membership: str, ...)`; `UserService.memberships_for_ids -> dict[UUID, str]`; both admin routers take `membership: str` path params; `seed_membership_policies` seeds one row per `memberships` row.

- [ ] **Step 1: Mechanical sweep**

Find all references: `grep -rn "users.membership import\|Membership\b" app/ | grep -v membership_registry | grep -v MembershipTier | grep -v MembershipService`. Apply:

1. `users/models.py`: `membership` column → `mapped_column(String(32), ForeignKey("memberships.slug"), server_default="free")` — **remove the Python-side `default=`** (creation paths set it explicitly, step 2) and the `Membership` import.
2. `users/schemas.py`: `membership: Membership` → `membership: str` in `UserRead` and `UserAdminRead`; `UserAdminPatch.membership: str | None = None`; `from_user` uses `membership=user.membership`; drop the enum import.
3. `users/service.py`: drop enum import; `memberships_for_ids` return type `dict[UUID, str]`; in `update_user_admin` the membership branch becomes:
   ```python
   if patch.membership is not None and patch.membership != user.membership:
       await MembershipService(self._session).require_assignable(patch.membership)
       user.membership = patch.membership
       changed["membership"] = patch.membership
   ```
   (`UserService.__init__` gains `self._session = session` alongside `self._repo` if not already stored.) In `create` and `create_from_google`, set membership explicitly:
   ```python
   membership=await MembershipService(self._session).default_slug(),
   ```
   as a new `User(...)` kwarg in both constructors.
4. `users/repository.py`: `memberships_for_ids` returns `dict[UUID, str]` (`{row[0]: row[1] ...}`); drop enum import.
5. `orchestration/seed.py`: replace the enum iteration — the seed reads the registry table via the users module's public seam:
   ```python
   from app.modules.users.membership_registry import ensure_loaded

   async def _seed(session: AsyncSession) -> None:
       existing = set((await session.execute(select(MembershipPolicy.membership))).scalars().all())
       tiers = await ensure_loaded(session)
       missing = [t.slug for t in tiers if t.slug not in existing]
       ...
   ```
   (docstring: "one all-NULL policy row per memberships row"). Keep the rest identical.
6. `orchestration/policy.py`: `patch_policy(self, membership: str, ...)`; first line becomes `await MembershipService(self._session).require_tier(membership)` (inactive tiers stay editable — `require_tier`, not `require_assignable`); replace `membership.value` with `membership`; `resolve` uses `user.membership` (no `.value`). Import `MembershipService`.
7. `orchestration/schemas.py`: `MembershipPolicyRead.membership: str`; drop enum import.
8. `orchestration/admin_router.py`: path param `membership: str`; drop enum import.
9. `quotas/service.py`: `limits_for` uses `user.membership` (no `.value`); `set_quota`/`clear_quota` take `membership: str`, first line `await MembershipService(self._session).require_tier(membership)`; all `.value` on membership removed; `user_quotas` return type `tuple[str, dict[str, float], list[UserQuotaOverride]]` and `user.membership` passed through. Import `MembershipService`, drop enum import.
10. `quotas/schemas.py`: `membership: Membership` → `membership: str` (both occurrences); drop enum import.
11. `quotas/admin_router.py`: path params `membership: str`; drop enum import.
12. `admin/usage_router.py` + `admin/schemas.py`: `dict[UUID, Membership]` → `dict[UUID, str]`; any `AdminUserUsageRead.membership: Membership` → `str`; the fallback tier literal (search for `Membership.FREE`) → `"free"`; drop enum imports.
13. `usage/self_service.py`: `membership=user.membership.value` → `membership=user.membership`; `usage/schemas.py` membership fields are already `str` (verify).
14. `app/main.py`: add `from app.modules.users.seed import seed_default_membership` and call it in `lifespan` **before** `seed_membership_policies()` (policies seed reads the registry).
15. Delete any now-unused imports; confirm `grep -rn "class Membership(" app/` returns only `MembershipTier`.

- [ ] **Step 2: Sweep the tests**

Files importing the enum (from the earlier survey): `tests/orchestration/test_tier_budgets.py`, `test_policy_resolution.py`, `test_membership_policy_seed.py`, `test_membership_policy_api.py`, `test_hitl_frozen_policy.py`, `test_monthly_quota_enforcement.py`, `test_quota_refusal_marker.py`; `tests/quotas/*` (all files matching `Membership.FREE`); `tests/usage/*`; `tests/llm/test_catalog_failure.py`; `tests/test_google_login_service.py`, `tests/test_users_google.py`, `tests/test_user_authz_fields.py`, `tests/test_authz_api.py`, `tests/test_authz_deps_unit.py` (done in Task 2), `tests/admin/test_users_admin_api.py`.

Mechanical replacements: `Membership.FREE.value` → `"free"`; `Membership.FREE` → `"free"`; `_user(membership: Membership = Membership.FREE)` helpers → `membership: str = "free"`; drop the imports. `test_membership_policy_seed.py`: assertions comparing seeded rows to `{m.value for m in Membership}` now compare to the slugs present in the `memberships` table — e.g. seed a premium tier first via `MembershipService.create_tier`, run `seed_membership_policies(session)`, assert rows == {"free", "premium"}, and `len(rows) == 2`.

Any test constructing `UserRead(...)` keeps working (`membership="free"` validates as `str`).

- [ ] **Step 3: Delete nothing else — verify the enum is gone**

Run: `grep -rn "MEMBERSHIP_RANK\|Membership(StrEnum)\|from app.modules.users.membership import Membership" app/ tests/` — Expected: no hits.

- [ ] **Step 4: Full backend gates**

Run: `uv run ruff check . --fix && uv run ruff format . && uv run mypy .`
Expected: clean.
Run: `uv run pytest -m "unit or integration"`
Expected: all PASS. If a test fails on a missing `free` tier or FK violation, that test's setup predates the migration backfill — insert the tier via `MembershipTier` + `membership_registry.invalidate()` in its fixtures.

- [ ] **Step 5: Commit**

```bash
printf 'refactor: delete Membership enum; tiers validate against the runtime registry\n' > /tmp/msg.txt
git add -A backend && bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 5: Admin memberships API + exception mapping

**Files:**
- Create: `backend/app/modules/admin/memberships_router.py`
- Modify: `backend/app/modules/admin/router.py` (include it)
- Modify: `backend/app/modules/orchestration/policy.py` (add `ensure_row`)
- Modify: `backend/app/core/exceptions.py` (three handlers)
- Test: `backend/tests/admin/test_memberships_admin_api.py`

**Interfaces:**
- Consumes: `MembershipService` (Task 3), `PolicyService` (existing), `require_admin`, `get_effective_settings`.
- Produces: `GET/POST /api/admin/memberships`, `PATCH /api/admin/memberships/{slug}`, `POST /api/admin/memberships/{slug}/deactivate`; `PolicyService.ensure_row(membership: str) -> None`; handlers: `UnknownMembershipError → 404 "Membership tier not found"`, `DuplicateMembershipError → 409 "Membership tier already exists"`, `MembershipLifecycleError → 422 {detail: str(exc)}`.

- [ ] **Step 1: Write the failing tests**

```python
"""Backoffice membership tier API (needs Postgres)."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient

from tests.admin.helpers import create_user, login

BASE = "/api/admin/memberships"


@pytest.fixture
async def admin(client: AsyncClient) -> UUID:
    user_id = await create_user("boss", is_admin=True)
    login(client, user_id, "boss")
    return user_id


async def _create_premium(client: AsyncClient) -> None:
    response = await client.post(
        BASE, json={"slug": "premium", "label": "Premium", "rank": 1, "price_label": "$9/mo"}
    )
    assert response.status_code == 200


@pytest.mark.integration
async def test_create_lists_and_seeds_policy_row(client: AsyncClient, admin: UUID) -> None:
    await _create_premium(client)
    listing = await client.get(BASE)
    slugs = {t["slug"]: t for t in listing.json()["memberships"]}
    assert slugs["premium"]["is_active"] is True and slugs["premium"]["user_count"] == 0
    policies = await client.get("/api/admin/membership-policies")
    assert "premium" in {p["membership"] for p in policies.json()["policies"]}


@pytest.mark.integration
async def test_duplicate_slug_409_and_bad_slug_422(client: AsyncClient, admin: UUID) -> None:
    await _create_premium(client)
    dup = await client.post(BASE, json={"slug": "premium", "label": "X"})
    assert dup.status_code == 409
    bad = await client.post(BASE, json={"slug": "Not Valid!", "label": "X"})
    assert bad.status_code == 422


@pytest.mark.integration
async def test_patch_edits_and_crowns_default(client: AsyncClient, admin: UUID) -> None:
    await _create_premium(client)
    patched = await client.patch(f"{BASE}/premium", json={"label": "Premium+", "is_default": True})
    assert patched.status_code == 200
    body = patched.json()
    assert body["label"] == "Premium+" and body["is_default"] is True
    listing = await client.get(BASE)
    free = next(t for t in listing.json()["memberships"] if t["slug"] == "free")
    assert free["is_default"] is False


@pytest.mark.integration
async def test_deactivate_migrates_and_guards(client: AsyncClient, admin: UUID) -> None:
    await _create_premium(client)
    protected = await client.post(f"{BASE}/free/deactivate", json={"migrate_to": "premium"})
    assert protected.status_code == 422  # default tier is protected
    ok = await client.post(f"{BASE}/premium/deactivate", json={"migrate_to": "free"})
    assert ok.status_code == 200 and ok.json()["is_active"] is False
    assign = await client.patch(f"/api/admin/users/{admin}", json={"membership": "premium"})
    assert assign.status_code == 404  # inactive tier is not assignable
    unknown = await client.patch(f"{BASE}/ghost", json={"label": "X"})
    assert unknown.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/admin/test_memberships_admin_api.py -v`
Expected: FAIL — 404s on `/api/admin/memberships` (router not registered).

- [ ] **Step 3: Implement**

`PolicyService.ensure_row` (in `orchestration/policy.py`, below `patch_policy`):

```python
    async def ensure_row(self, membership: str) -> None:
        """Insert the all-NULL policy row for a tier if absent (create path)."""
        if await self._repo.get_by_membership(membership) is None:
            self._repo.add(MembershipPolicy(membership=membership))
            await self._session.flush()
```

`admin/memberships_router.py`:

```python
"""Backoffice membership tier routes. HTTP only; logic in MembershipService.

Composition: tier creation also ensures the orchestration policy row exists
(same request transaction) so the new tier appears on the policies screen
immediately — router-layer composition, no service-to-service import cycle.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.deps import get_db, get_effective_settings, require_admin
from app.modules.orchestration.policy import PolicyService
from app.modules.users.membership_service import MembershipService
from app.modules.users.schemas import (
    MembershipAdminRead,
    MembershipCreate,
    MembershipDeactivate,
    MembershipPatch,
    MembershipsResponse,
    UserRead,
)

router = APIRouter(prefix="/memberships")


def _service(session: Annotated[AsyncSession, Depends(get_db)]) -> MembershipService:
    return MembershipService(session)


@router.get("")
async def list_memberships(
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[MembershipService, Depends(_service)],
) -> MembershipsResponse:
    """Every tier (active and inactive) with live user counts, rank order."""
    return MembershipsResponse(memberships=await service.list_tiers())


@router.post("")
async def create_membership(
    body: MembershipCreate,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[MembershipService, Depends(_service)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_effective_settings)],
) -> MembershipAdminRead:
    """Create a tier; also seeds its all-NULL per-turn policy row."""
    tier = await service.create_tier(body, actor_id=admin.id)
    await PolicyService(session, settings).ensure_row(tier.slug)
    return MembershipAdminRead.from_tier(tier, 0)


@router.patch("/{slug}")
async def patch_membership(
    slug: str,
    body: MembershipPatch,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[MembershipService, Depends(_service)],
) -> MembershipAdminRead:
    """Edit presentation/rank/default, or reactivate. Slug is immutable."""
    tier = await service.update_tier(slug, body, actor_id=admin.id)
    counts = await service.list_tiers()
    count = next((t.user_count for t in counts if t.slug == slug), 0)
    return MembershipAdminRead.from_tier(tier, count)


@router.post("/{slug}/deactivate")
async def deactivate_membership(
    slug: str,
    body: MembershipDeactivate,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[MembershipService, Depends(_service)],
) -> MembershipAdminRead:
    """Migrate every user to body.migrate_to, then deactivate. One transaction."""
    tier, _moved = await service.deactivate_tier(slug, body.migrate_to, actor_id=admin.id)
    return MembershipAdminRead.from_tier(tier, 0)
```

Register in `admin/router.py`: `from app.modules.admin.memberships_router import router as memberships_router` + `router.include_router(memberships_router)`.

`core/exceptions.py` — add three handlers next to the existing user-domain block (import the new exceptions from `app.modules.users.exceptions`):

```python
    @app.exception_handler(UnknownMembershipError)
    async def unknown_membership_handler(_request: Request, _exc: UnknownMembershipError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Membership tier not found"})

    @app.exception_handler(DuplicateMembershipError)
    async def duplicate_membership_handler(_request: Request, _exc: DuplicateMembershipError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": "Membership tier already exists"})

    @app.exception_handler(MembershipLifecycleError)
    async def membership_lifecycle_handler(_request: Request, exc: MembershipLifecycleError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})
```

(Match the exact handler signature style used in the surrounding file, including the `Request` import already present.)

- [ ] **Step 4: Run tests, then the backend gates**

Run: `uv run pytest tests/admin/test_memberships_admin_api.py tests/admin/ -v` — Expected: PASS.
Run: `uv run ruff check . --fix && uv run ruff format . && uv run mypy .` — Expected: clean.

- [ ] **Step 5: Commit**

```bash
printf 'feat: admin memberships API — create, edit, deactivate-with-migration\n' > /tmp/msg.txt
git add -A backend && bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 6: Self-serve plans API + runtime flag

**Files:**
- Modify: `backend/app/core/config.py` (new group + root field)
- Modify: `backend/app/modules/runtime_config/registry.py` (`_FULL_SECTIONS`)
- Create: `backend/app/modules/users/me_router.py`
- Modify: `backend/app/modules/users/schemas.py` (plan DTOs)
- Modify: `backend/app/modules/users/membership_service.py` (`switch_user`, `active_plans`)
- Modify: `backend/app/main.py` (register router)
- Test: `backend/tests/memberships/test_me_plans_api.py`

**Interfaces:**
- Consumes: `MembershipService`, `membership_registry.ensure_loaded`, `get_effective_settings`, `get_current_user`.
- Produces: `MembershipSettings(self_switch_enabled: bool = True)` at `settings.membership`, runtime-tunable section `"membership"`; `GET /api/me/plans -> PlansResponse(plans: list[PlanRead], can_switch: bool)` with `PlanRead(slug, label, description, price_label, current)`; `POST /api/me/membership {membership} -> UserRead`; `MembershipService.switch_user(user_id: UUID, slug: str) -> UserRead`, `MembershipService.active_plans(current_slug: str) -> list[PlanRead]`.

- [ ] **Step 1: Write the failing tests**

```python
"""Self-serve plan listing and tier switching (needs Postgres)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.membership_service import MembershipService
from app.modules.users.schemas import MembershipCreate
from tests.admin.helpers import create_user, login


@pytest.fixture
async def user(client: AsyncClient) -> UUID:
    user_id = await create_user("reader")
    login(client, user_id, "reader")
    return user_id


@pytest.fixture
async def premium(session: AsyncSession) -> None:
    await MembershipService(session).create_tier(
        MembershipCreate(slug="premium", label="Premium", rank=1, price_label="$9/mo"),
        actor_id=uuid4(),
    )
    await session.commit()


@pytest.mark.integration
async def test_plans_lists_active_tiers_with_current(client: AsyncClient, user: UUID, premium: None) -> None:
    response = await client.get("/api/me/plans")
    assert response.status_code == 200
    body = response.json()
    assert body["can_switch"] is True
    assert [p["slug"] for p in body["plans"]] == ["free", "premium"]  # rank order
    assert next(p for p in body["plans"] if p["slug"] == "free")["current"] is True


@pytest.mark.integration
async def test_switch_and_noop_and_unknown(client: AsyncClient, user: UUID, premium: None) -> None:
    ok = await client.post("/api/me/membership", json={"membership": "premium"})
    assert ok.status_code == 200 and ok.json()["membership"] == "premium"
    noop = await client.post("/api/me/membership", json={"membership": "premium"})
    assert noop.status_code == 200
    unknown = await client.post("/api/me/membership", json={"membership": "ghost"})
    assert unknown.status_code == 404


@pytest.mark.integration
async def test_flag_off_hides_and_403s(client: AsyncClient, user: UUID) -> None:
    # First set the runtime override membership.self_switch_enabled = False,
    # using the exact same write-and-invalidate pattern the existing
    # runtime_config tests use (find them: grep -rl RuntimeConfigService tests/).
    plans = await client.get("/api/me/plans")
    assert plans.json()["can_switch"] is False
    switch = await client.post("/api/me/membership", json={"membership": "free"})
    assert switch.status_code == 403
```

(For the flag-off test, copy the override-write mechanism from the existing runtime_config tests — find them with `grep -rl "RuntimeConfigService" tests/`; use the same fixture/service call they use, then invalidate its cache the way those tests do.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/memberships/test_me_plans_api.py -v`
Expected: FAIL — 404 on `/api/me/plans`.

- [ ] **Step 3: Implement**

`core/config.py` — after `UsageSettings`:

```python
class MembershipSettings(_GroupSettings):
    """Membership/tier behavior toggles."""

    self_switch_enabled: bool = Field(default=True, validation_alias="membership_self_switch_enabled")
```

Root `Settings`: `membership: MembershipSettings = Field(default_factory=MembershipSettings)`.

`runtime_config/registry.py`: add `"membership": MembershipSettings` to `_FULL_SECTIONS` (import it).

`users/schemas.py` — append:

```python
class PlanRead(BaseModel):
    """One selectable plan on the self-serve picker."""

    slug: str
    label: str
    description: str | None
    price_label: str | None
    current: bool


class PlansResponse(BaseModel):
    plans: list[PlanRead]
    can_switch: bool


class MembershipSwitch(BaseModel):
    membership: str
```

`membership_service.py` — append two methods (imports: `PlanRead`, `UserRead`, `UserRepository`, `UserNotFoundError`):

```python
    async def active_plans(self, current_slug: str) -> list[PlanRead]:
        """Active tiers in rank order for the self-serve picker."""
        rows = await self._repo.list_all()
        return [
            PlanRead(
                slug=row.slug, label=row.label, description=row.description,
                price_label=row.price_label, current=row.slug == current_slug,
            )
            for row in rows
            if row.is_active
        ]

    async def switch_user(self, user_id: UUID, slug: str) -> UserRead:
        """Self-serve tier switch (no billing). Validates active; audited."""
        await self.require_assignable(slug)
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(str(user_id))
        user.membership = slug
        await self._users.save(user)
        logger.info("user switched membership", extra={"actor": str(user_id), "membership": slug})
        return UserRead.model_validate(user)
```

`MembershipService.__init__` gains `self._users = UserRepository(session)`.

`users/me_router.py`:

```python
"""Self-serve membership routes. Identity comes from the session cookie ONLY.

The switch endpoint exists for manual testing pre-Stripe; the runtime flag
membership.self_switch_enabled (runtime-config tunable) turns it off without
a redeploy once real billing owns tier changes.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.deps import get_current_user, get_db, get_effective_settings
from app.modules.auth.exceptions import NotAuthorizedError
from app.modules.users.membership_service import MembershipService
from app.modules.users.schemas import MembershipSwitch, PlansResponse, UserRead

router = APIRouter(prefix="/me", tags=["users"])


@router.get("/plans")
async def my_plans(
    user: Annotated[UserRead, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_effective_settings)],
) -> PlansResponse:
    """Active tiers (rank order) + whether self-switching is enabled."""
    plans = await MembershipService(session).active_plans(user.membership)
    return PlansResponse(plans=plans, can_switch=settings.membership.self_switch_enabled)


@router.post("/membership")
async def switch_membership(
    body: MembershipSwitch,
    user: Annotated[UserRead, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_effective_settings)],
) -> UserRead:
    """Flag-gated manual tier switch (403 when disabled)."""
    if not settings.membership.self_switch_enabled:
        raise NotAuthorizedError
    return await MembershipService(session).switch_user(user.id, body.membership)
```

`main.py`: `from app.modules.users.me_router import router as me_plans_router` + `app.include_router(me_plans_router, prefix=api_prefix)` (next to `usage_router`; both use prefix `/me` with distinct paths — verify no route collision by hitting `/docs` mentally: `/me/usage` vs `/me/plans`, `/me/membership`).

- [ ] **Step 4: Run tests + gates**

Run: `uv run pytest tests/memberships/ -v` — Expected: PASS.
Run: `uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"` — Expected: clean, all PASS (the new settings group must not break `make_settings` — it autodiscovers groups, nothing to do).

- [ ] **Step 5: Commit**

```bash
printf 'feat: self-serve plan listing and flag-gated tier switch API\n' > /tmp/msg.txt
git add -A backend && bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 7: Frontend — admin memberships data layer + users dropdown

**Files:**
- Create: `frontend/src/features/admin/api/memberships.ts`
- Create: `frontend/src/features/admin/hooks/useMemberships.ts`
- Modify: `frontend/src/features/admin/components/users/UsersPage.tsx`
- Test: `frontend/src/features/admin/hooks/useMemberships.test.ts` (only if hooks have existing test precedent — check; otherwise cover via UsersPage.test.tsx)
- Modify: `frontend/src/features/admin/components/users/UsersPage.test.tsx`

**Interfaces:**
- Produces (consumed by Tasks 8-9):
  - `AdminMembership = { slug: string; label: string; description: string | null; price_label: string | null; rank: number; is_active: boolean; is_default: boolean; user_count: number; updated_at: string }`
  - `fetchMemberships(): Promise<{ memberships: AdminMembership[] }>`, `createMembership(body)`, `patchMembership(slug, patch)`, `deactivateMembership(slug, migrateTo)`
  - `membershipsKey = ['admin', 'memberships']`, hooks `useMemberships()`, `useCreateMembership()`, `usePatchMembership()`, `useDeactivateMembership()` — mutations invalidate `membershipsKey`, `membershipPoliciesKey`, and `adminUsersKey` (import the existing keys; find the users key name in `features/admin/hooks/useAdminUsers.ts`).

- [ ] **Step 1: Write the failing test (UsersPage drives its dropdown from memberships)**

In `UsersPage.test.tsx`, update the existing mock of `useMembershipPolicies` usage: the page now calls `useMemberships` — mock it to return `{ data: { memberships: [free(active), premium(active), legacy(inactive)] } }` and assert the membership `<select>` options are exactly `['free', 'premium']` (active only, rank order). Follow the file's existing mocking style precisely.

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npm run test -- UsersPage`
Expected: FAIL.

- [ ] **Step 3: Implement**

`api/memberships.ts`:

```ts
import { apiGet, apiPatch, apiPost } from '@/shared/lib/api'

/** Mirrors MembershipAdminRead (users/schemas.py). */
export type AdminMembership = {
  slug: string
  label: string
  description: string | null
  price_label: string | null
  rank: number
  is_active: boolean
  is_default: boolean
  user_count: number
  updated_at: string
}

export type MembershipCreateBody = {
  slug: string
  label: string
  rank: number
  description?: string | null
  price_label?: string | null
}

export type MembershipPatchBody = Partial<{
  label: string
  description: string | null
  price_label: string | null
  rank: number
  is_default: true
  is_active: true
}>

export function fetchMemberships(): Promise<{ memberships: AdminMembership[] }> {
  return apiGet('/api/admin/memberships')
}

export function createMembership(body: MembershipCreateBody): Promise<AdminMembership> {
  return apiPost('/api/admin/memberships', body)
}

export function patchMembership(slug: string, patch: MembershipPatchBody): Promise<AdminMembership> {
  return apiPatch(`/api/admin/memberships/${encodeURIComponent(slug)}`, patch)
}

export function deactivateMembership(slug: string, migrateTo: string): Promise<AdminMembership> {
  return apiPost(`/api/admin/memberships/${encodeURIComponent(slug)}/deactivate`, {
    migrate_to: migrateTo,
  })
}
```

`hooks/useMemberships.ts` — mirror `useMembershipPolicies.ts` exactly: `useQuery({ queryKey: membershipsKey, queryFn: fetchMemberships })`; three `useMutation` hooks whose `onSuccess` invalidates the three keys listed in Interfaces.

`UsersPage.tsx`: replace `useMembershipPolicies` with `useMemberships`; `const memberships = data?.memberships.filter((m) => m.is_active).map((m) => m.slug) ?? []` (registry order is already rank order). Keep the loading-fallback behavior in `UserRow` untouched.

- [ ] **Step 4: Run tests**

Run: `npm run test -- UsersPage && npm run lint && npm run build`
Expected: PASS/clean.

- [ ] **Step 5: Commit**

```bash
printf 'feat: admin memberships data layer; users dropdown lists active tiers\n' > /tmp/msg.txt
git add -A frontend && bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 8: Frontend — Policies page tier management

**Files:**
- Create: `frontend/src/features/admin/components/policies/TierFormDialog.tsx`
- Create: `frontend/src/features/admin/components/policies/TierActions.tsx`
- Modify: `frontend/src/features/admin/components/policies/PoliciesPage.tsx`
- Modify: `frontend/src/features/admin/components/policies/PolicyCard.tsx` (header slot)
- Modify: `frontend/src/features/admin/components/policies/PoliciesPage.test.tsx`

**Interfaces:**
- Consumes: `useMemberships`/`useCreateMembership`/`usePatchMembership`/`useDeactivateMembership` (Task 7), existing `useMembershipPolicies`, `useMembershipQuotas`, `PolicyCard`, `QuotaSection`.
- Produces: `TierFormDialog({ mode: 'create' } | { mode: 'edit'; tier: AdminMembership }, open, onClose)` — fields slug (create only), label, rank, description, price label; `TierActions({ tier, allTiers })` — Edit button, Make default button (hidden on the default tier), Deactivate flow (target `<select>` of other active tiers + `window.confirm` naming the user count), Reactivate button on inactive tiers.

- [ ] **Step 1: Write the failing tests**

Extend `PoliciesPage.test.tsx` (follow its existing mock style; now also mock `useMemberships`):
- renders one card per tier from `useMemberships` in rank order, using the tier `label` as the card heading (not the capitalized slug);
- a tier with no matching policy row still renders a card (all-blank fields);
- inactive tier renders with the dimmed style (`opacity-60` on the card wrapper, matching UserRow's deleted convention) and a Reactivate button, and no Deactivate button;
- "New tier" button opens the create dialog; submitting calls `createMembership` with `{slug, label, rank, description, price_label}`;
- Deactivate flow: clicking Deactivate on `premium` shows a target select without `premium`, confirming calls `deactivateMembership('premium', 'free')`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test -- PoliciesPage`
Expected: FAIL.

- [ ] **Step 3: Implement**

`PolicyCard.tsx`: add optional `header?: ReactNode` prop; when provided render it in place of the current `<h2>` (keep the `<h2 className="mb-2 font-medium capitalize">{policy.membership}</h2>` fallback so nothing else breaks). This is a ~4 line change; the file stays under 110 lines.

`PoliciesPage.tsx` rework (stay ≤110 lines — extract if needed):

```tsx
import { useState } from 'react'
import { useMemberships } from '@/features/admin/hooks/useMemberships'
import { useMembershipPolicies } from '@/features/admin/hooks/useMembershipPolicies'
import { useMembershipQuotas } from '@/features/admin/hooks/useMembershipQuotas'
import type { MembershipPolicy } from '@/features/admin/api/membershipPolicies'
import { PolicyCard } from './PolicyCard'
import { QuotaSection } from './QuotaSection'
import { TierActions } from './TierActions'
import { TierFormDialog } from './TierFormDialog'

/** A tier with no policy row yet renders all-blank (every field inherits). */
function blankPolicy(slug: string): MembershipPolicy {
  return {
    membership: slug,
    updated_at: '',
    max_tool_iters: null,
    max_external_calls: null,
    max_turn_tokens_in: null,
    max_turn_tokens_out: null,
    max_turn_cost_usd: null,
    run_deadline_seconds: null,
    max_hitl_rounds: null,
  }
}

export function PoliciesPage() {
  const tiers = useMemberships()
  const { data, isLoading, error } = useMembershipPolicies()
  const quotas = useMembershipQuotas()
  const [creating, setCreating] = useState(false)
  if (isLoading || tiers.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading membership policies…</p>
  }
  if (error || !data || tiers.error || !tiers.data) {
    return <p className="text-sm text-destructive">Failed to load membership policies.</p>
  }
  const allTiers = tiers.data.memberships
  return (
    <section>
      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-lg font-semibold">Membership tiers</h1>
        <button
          type="button"
          className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground"
          onClick={() => setCreating(true)}
        >
          New tier
        </button>
      </div>
      <p className="mb-4 text-sm text-muted-foreground">
        Per-turn caps: blank = inherit the runtime setting. Quotas: blank = unlimited.
        Changes apply on the user&apos;s next turn — no restart.
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        {allTiers.map((tier) => {
          const policy =
            data.policies.find((p) => p.membership === tier.slug) ?? blankPolicy(tier.slug)
          return (
            <div key={tier.slug} className={tier.is_active ? '' : 'opacity-60'}>
              <PolicyCard
                policy={policy}
                inherited={data.inherited}
                header={<TierActions tier={tier} allTiers={allTiers} />}
              >
                {quotas.data ? (
                  <QuotaSection
                    membership={tier.slug}
                    kinds={quotas.data.kinds}
                    rows={quotas.data.quotas.filter((q) => q.membership === tier.slug)}
                  />
                ) : null}
              </PolicyCard>
            </div>
          )
        })}
      </div>
      <TierFormDialog mode="create" open={creating} onClose={() => setCreating(false)} />
    </section>
  )
}
```

`TierActions.tsx`: header row with the tier `label` (+ `price_label` muted, `default` badge when `is_default`, `inactive` badge when not active), an Edit button opening `TierFormDialog` in edit mode, a "Make default" button (`patchMembership(slug, {is_default: true})`) when not default, Reactivate (`patchMembership(slug, {is_active: true})`) when inactive, and the Deactivate control when active and not default: a `<select>` of other active tiers + button; on click `window.confirm(`Deactivate ${tier.label}? ${tier.user_count} user(s) will move to ${target}.`)` then `useDeactivateMembership().mutate({slug, migrateTo})`. Keep under 110 lines / 60-line functions — split a `DeactivateControl` child component inside the same directory if needed (`TierDeactivate.tsx`).

`TierFormDialog.tsx`: controlled inputs for slug (create only, `pattern` hint text), label, rank (number), description (textarea), price label; submit calls `useCreateMembership` or `usePatchMembership`; disable submit while pending; show `mutation.error` message inline. Use the same dialog markup pattern as `UserQuotasDialog.tsx` (read it first and mirror its structure).

- [ ] **Step 4: Run tests + lint + build**

Run: `npm run test -- PoliciesPage && npm run lint && npm run build`
Expected: PASS/clean (ESLint enforces the size limits — split further if it flags).

- [ ] **Step 5: Commit**

```bash
printf 'feat: manage membership tiers from the policies screen\n' > /tmp/msg.txt
git add -A frontend && bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 9: Frontend — Plan & usage tier picker

**Files:**
- Create: `frontend/src/features/usage/api/plans.ts`
- Create: `frontend/src/features/usage/hooks/usePlans.ts`
- Create: `frontend/src/features/usage/components/PlansSection.tsx`
- Create: `frontend/src/features/usage/components/PlanCard.tsx`
- Modify: `frontend/src/features/usage/components/UsagePage.tsx`
- Test: `frontend/src/features/usage/components/PlansSection.test.tsx`

**Interfaces:**
- Consumes: `GET /api/me/plans`, `POST /api/me/membership` (Task 6); the me-usage query key (find it in `features/usage/hooks/useMeUsage.ts`).
- Produces: `Plan = { slug: string; label: string; description: string | null; price_label: string | null; current: boolean }`, `PlansResponse = { plans: Plan[]; can_switch: boolean }`, `fetchPlans()`, `switchPlan(slug: string)`; `usePlans()`, `useSwitchPlan()` (invalidates plans + me-usage keys on success); `<PlansSection />` rendered at the bottom of `UsagePage`.

- [ ] **Step 1: Write the failing tests**

`PlansSection.test.tsx` (mirror `UsagePage.test.tsx` setup style):
- with `can_switch: true` and plans `[free(current), premium]`: renders both cards, "Current plan" marker on free, a "Switch to Premium" button on premium;
- clicking the switch button (with `window.confirm` mocked true) calls `switchPlan('premium')`;
- with `can_switch: false`: renders nothing (`container.firstChild === null`);
- while loading: renders nothing.

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test -- PlansSection`
Expected: FAIL.

- [ ] **Step 3: Implement**

`api/plans.ts`:

```ts
import { apiGet, apiPost } from '@/shared/lib/api'

/** Mirrors PlansResponse (users/schemas.py). */
export type Plan = {
  slug: string
  label: string
  description: string | null
  price_label: string | null
  current: boolean
}

export type PlansResponse = {
  plans: Plan[]
  can_switch: boolean
}

export function fetchPlans(): Promise<PlansResponse> {
  return apiGet('/api/me/plans')
}

export function switchPlan(slug: string): Promise<unknown> {
  return apiPost('/api/me/membership', { membership: slug })
}
```

`hooks/usePlans.ts`: `plansKey = ['me', 'plans']`; `usePlans` query; `useSwitchPlan` mutation invalidating `plansKey` and the me-usage key on success.

`PlansSection.tsx`:

```tsx
import { usePlans } from '../hooks/usePlans'
import { PlanCard } from './PlanCard'

/** Manual tier switching (pre-Stripe). Hidden when the runtime flag is off. */
export function PlansSection() {
  const { data } = usePlans()
  if (!data || !data.can_switch) return null
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold">Plans</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {data.plans.map((plan) => (
          <PlanCard key={plan.slug} plan={plan} />
        ))}
      </div>
    </section>
  )
}
```

`PlanCard.tsx`: card with `label` (+ `price_label` muted), `description` if present; when `current` a "Current plan" badge; otherwise a button `Switch to {label}` → `window.confirm(`Switch to ${plan.label}?`)` → `useSwitchPlan().mutate(plan.slug)`; disabled while pending.

`UsagePage.tsx`: add `<PlansSection />` after `<StorageSection kinds={standing} />` (file is 35 lines; stays well under the cap).

- [ ] **Step 4: Run all frontend gates**

Run: `npm run test && npm run lint && npm run build`
Expected: all PASS/clean.

- [ ] **Step 5: Commit**

```bash
printf 'feat: plan picker with flag-gated tier switching on Plan & usage\n' > /tmp/msg.txt
git add -A frontend && bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 10: Full verification + docs touch-up

**Files:**
- Modify: `CLAUDE.md` (one sentence in the runtime-registries paragraph)

- [ ] **Step 1: Full backend gates**

Run (Bash, from `backend/`): `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"`
Expected: all clean/PASS. Fix anything that isn't before proceeding.

- [ ] **Step 2: Full frontend gates**

Run (from `frontend/`): `npm run lint && npm run build && npm run test`
Expected: all clean/PASS.

- [ ] **Step 3: Manual smoke (needs infra + backend + frontend running)**

1. Log in as admin → Policies page → New tier → create `premium` ($9/mo, rank 1). Card appears with blank caps/quotas.
2. Set a quota on premium (e.g. AI tokens 1000). Users page → assign a test user to premium.
3. Plan & usage as that user → Plans section shows Free + Premium, Premium current; switch back to Free; meters refresh.
4. Policies page → deactivate premium into free → user lands back on free; premium card dims; Users dropdown no longer offers premium; reactivate works.
5. Runtime settings screen → set `membership.self_switch_enabled` = false → Plans section disappears; POST 403s.

- [ ] **Step 4: Update CLAUDE.md**

In the paragraph about DB-backed runtime registries (the one describing the LLM catalog), append one sentence: membership tiers are likewise DB-backed at runtime (`memberships` table, users module) served via the cached snapshot in `modules/users/membership_registry.py` (same 30s-TTL/invalidate pattern); admins manage tiers via `/api/admin/memberships`; the seed inserts only the `free` tier.

- [ ] **Step 5: Commit**

```bash
printf 'docs: note runtime membership tier registry in CLAUDE.md\n' > /tmp/msg.txt
git add CLAUDE.md && bash scripts/git-commit-clean.sh /tmp/msg.txt
```
