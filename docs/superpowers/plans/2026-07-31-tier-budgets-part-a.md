# Tier Budgets (Part A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the per-turn orchestration budgets (tool iterations, external calls, turn tokens, turn cost, wall clock, HITL rounds) from global settings to membership-tier lookups, frozen per turn, with an admin API and backoffice screen.

**Architecture:** A new orchestration-owned `membership_policies` table holds the seven nullable per-turn cap overrides (NULL = inherit) — per-turn caps ONLY; all monthly/standing quotas live in Part B's `membership_quotas` table (quotas module), per the spec §3.0 amendment. `PolicyService.resolve(user)` produces a frozen `ResolvedPolicy` via specificity-wins (tier field if NOT NULL, else the effective runtime settings the chat path already receives). `RunBudget.from_policy` replaces `from_settings` in the loop; the HITL freeze snapshot gains the resolved caps so a resumed turn never re-resolves. Admin CRUD is PATCH-only (rows mirror the `Membership` enum) behind `require_admin`, plus a backoffice "Memberships" screen.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, pydantic v2, React 19, react-query, vitest.

**Spec:** `docs/superpowers/specs/2026-07-31-tier-usage-management.md` (approved; shared with Parts B–C). Read §3.0–§3.5 before starting — especially the amendment (per-turn caps here, quotas in Part B) and the frozen-policy rules.

**Sequencing:** All hard dependencies are merged (verified 2026-07-31): `Membership` enum + rank map (`users/membership.py`), runtime_config effective-settings chain, `llm_executions.user_id` migration `cc8afb8f06aa` (current Alembic head). Part B starts only after Tasks 1–2 here are merged.

## Global Constraints

- Backend gates per task (run from `backend/`, **via the Bash tool** — `uv` is not on the PowerShell PATH): `uv run ruff check . --fix && uv run ruff format .`, `uv run mypy .`, `uv run pytest -m "unit or integration"`.
- Frontend gates (from `frontend/`): `npm run lint`, `npm run build`, `npm run test`.
- Integration tests need Postgres/Redis/MinIO and `TEST_DATABASE_URL` pointing at a separate test DB — never the app DB. Apply new migrations to the test DB too (`DATABASE_URL=<TEST_DATABASE_URL value> uv run alembic upgrade head`).
- Commit per task: write the message to `/tmp/msg.txt`, then `bash scripts/git-commit-clean.sh /tmp/msg.txt`; verify with `git log -1 --format=%B`. **Never** add `Co-authored-by`/`Made-with` trailers.
- Ruff limits: complexity ≤10, statements ≤20, branches ≤6, args ≤6. Frontend ESLint: file ≤110 lines, function ≤60 lines, nesting ≤3. Split helpers rather than disabling rules.
- Full type hints, strict mypy. Tests build settings via `tests/factories.py::make_settings(**flat_overrides)` — never `Settings()` directly.
- Module direction: router → service → repository. Orchestration reads membership from the `UserRead` it is handed and owns `membership_policies`; it never touches users'/llm's repositories.
- Policy values are **not secrets** — log them freely (structured `extra={...}`).
- **NULL semantics (repeat in every docstring/comment where relevant):** per-turn columns NULL = inherit — never "unlimited". This table carries NO quota columns (quotas are Part B's keyed `membership_quotas` table).

---

### Task 1: `membership_policies` model + migration + startup seed

**Files:**
- Create: `backend/app/modules/orchestration/models.py`
- Create: `backend/app/modules/orchestration/seed.py`
- Modify: `backend/app/core/orm.py` (register the new models module)
- Modify: `backend/app/main.py` (lifespan seed call)
- Create: `backend/migrations/versions/<generated>_add_membership_policies.py`
- Test: `backend/tests/orchestration/test_membership_policy_seed.py`

**Interfaces:**
- Produces: `MembershipPolicy` ORM model (table `membership_policies`; columns `id`, `membership` unique, seven nullable per-turn caps named **exactly** like `LlmRuntimeSettings` fields — `max_tool_iters`, `max_external_calls`, `max_turn_tokens_in`, `max_turn_tokens_out`, `max_turn_cost_usd`, `run_deadline_seconds`, `max_hitl_rounds` — plus `created_at`, `updated_at`; NO quota columns); `seed_membership_policies(session: AsyncSession | None = None) -> None` (insert-if-missing, never overwrites). Tasks 2–5 rely on these names.

- [ ] **Step 1: Write the model**

```python
# backend/app/modules/orchestration/models.py
"""SQLAlchemy models for orchestration-owned AI policy."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MembershipPolicy(Base):
    """Per-tier PER-TURN cap overrides — one row per Membership enum value.

    NULL = inherit the effective runtime setting (there is always a global
    fallback; per-turn caps are safety rails that can never be absent).
    Monthly/standing quotas do NOT live here — they are keyed rows in the
    quotas module's membership_quotas table (spec §3.0/§3.1).
    """

    __tablename__ = "membership_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    membership: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    # Per-turn budget overrides. Field names match LlmRuntimeSettings exactly
    # so resolution can iterate one shared name list. NULL = inherit.
    max_tool_iters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_external_calls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_turn_tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_turn_tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_turn_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    run_deadline_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_hitl_rounds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 2: Register the models module**

In `backend/app/core/orm.py::import_all_models`, add (alphabetical position, matching the existing style):

```python
    from app.modules.orchestration import models as orchestration_models
```

and add `orchestration_models,` to the `_ = (...)` tuple.

- [ ] **Step 3: Write the seed helper**

```python
# backend/app/modules/orchestration/seed.py
"""Seed membership_policies rows (insert-if-missing; never overwrites edits)."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.modules.orchestration.models import MembershipPolicy
from app.modules.users.membership import Membership

logger = logging.getLogger(__name__)


async def seed_membership_policies(session: AsyncSession | None = None) -> None:
    """Ensure one all-NULL policy row exists per Membership value.

    Idempotent, insert-if-missing: a restart never reverts admin edits
    (same contract as the LLM catalog seed). New enum values get their row
    on the next startup even if the migration predates them.
    """
    if session is not None:
        await _seed(session)
        await session.commit()
        return
    async with SessionLocal() as owned:
        await _seed(owned)
        await owned.commit()


async def _seed(session: AsyncSession) -> None:
    existing = set(
        (await session.execute(select(MembershipPolicy.membership))).scalars().all()
    )
    missing = [m.value for m in Membership if m.value not in existing]
    for value in missing:
        session.add(MembershipPolicy(membership=value))
    if missing:
        logger.info("seeding membership policies", extra={"memberships": missing})
```

In `backend/app/main.py`: add `from app.modules.orchestration.seed import seed_membership_policies` to the imports and call `await seed_membership_policies()` in `lifespan` after `await seed_llm_models()`.

- [ ] **Step 4: Generate and fill the migration**

Run (from `backend/`): `uv run alembic revision -m "add membership_policies"`, then verify `uv run alembic heads` shows exactly one head and the generated `down_revision` is `"cc8afb8f06aa"`. Fill in:

```python
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.create_table(
        "membership_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership", sa.String(length=32), nullable=False),
        # Per-turn caps: NULL = inherit the effective runtime setting.
        sa.Column("max_tool_iters", sa.Integer(), nullable=True,
                  comment="NULL = inherit effective runtime setting"),
        sa.Column("max_external_calls", sa.Integer(), nullable=True,
                  comment="NULL = inherit effective runtime setting"),
        sa.Column("max_turn_tokens_in", sa.Integer(), nullable=True,
                  comment="NULL = inherit effective runtime setting"),
        sa.Column("max_turn_tokens_out", sa.Integer(), nullable=True,
                  comment="NULL = inherit effective runtime setting"),
        sa.Column("max_turn_cost_usd", sa.Float(), nullable=True,
                  comment="NULL = inherit effective runtime setting"),
        sa.Column("run_deadline_seconds", sa.Integer(), nullable=True,
                  comment="NULL = inherit effective runtime setting"),
        sa.Column("max_hitl_rounds", sa.Integer(), nullable=True,
                  comment="NULL = inherit effective runtime setting"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_membership_policies_membership"),
        "membership_policies",
        ["membership"],
        unique=True,
    )
    # Seed the CURRENT enum values, hardcoded — migrations must not import
    # app enums (replay determinism). Future values are seeded at startup.
    table = sa.table(
        "membership_policies",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("membership", sa.String()),
    )
    op.bulk_insert(table, [{"id": uuid.uuid4(), "membership": m} for m in ("free",)])


def downgrade() -> None:
    op.drop_index(op.f("ix_membership_policies_membership"), table_name="membership_policies")
    op.drop_table("membership_policies")
```

- [ ] **Step 5: Verify the migration is reversible; apply to both DBs**

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
DATABASE_URL=<your TEST_DATABASE_URL value> uv run alembic upgrade head
```

Expected: all succeed; `membership_policies` exists in both DBs with one `free` row.

- [ ] **Step 6: Write the failing tests**

```python
# backend/tests/orchestration/test_membership_policy_seed.py
"""Seeding contract: every enum value gets a row; edits survive (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from app.core.config import get_settings
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.seed import seed_membership_policies
from app.modules.users.membership import Membership
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
        # Leave a freshly seeded table behind for other suites.
        await db.execute(delete(MembershipPolicy))
        await db.commit()
        await seed_membership_policies(db)
    await engine.dispose()


async def _rows(session: AsyncSession) -> list[MembershipPolicy]:
    return list((await session.execute(select(MembershipPolicy))).scalars().all())


@pytest.mark.integration
@pytest.mark.asyncio
async def test_every_membership_value_has_all_null_seed_row(session: AsyncSession) -> None:
    await session.execute(delete(MembershipPolicy))
    await session.commit()
    await seed_membership_policies(session)
    rows = await _rows(session)
    assert {row.membership for row in rows} == {m.value for m in Membership}
    for row in rows:
        assert row.max_tool_iters is None
        assert row.max_external_calls is None
        assert row.max_turn_tokens_in is None
        assert row.max_turn_tokens_out is None
        assert row.max_turn_cost_usd is None
        assert row.run_deadline_seconds is None
        assert row.max_hitl_rounds is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_seed_is_idempotent_and_never_overwrites_edits(
    session: AsyncSession,
) -> None:
    await session.execute(delete(MembershipPolicy))
    await session.commit()
    await seed_membership_policies(session)
    row = (
        await session.execute(
            select(MembershipPolicy).where(MembershipPolicy.membership == Membership.FREE.value)
        )
    ).scalar_one()
    row.max_tool_iters = 2
    await session.commit()

    await seed_membership_policies(session)

    await session.refresh(row)
    assert row.max_tool_iters == 2
    assert len(await _rows(session)) == len(list(Membership))
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/orchestration/test_membership_policy_seed.py -v`
Expected: PASS (2 tests). (They were failing before Steps 1–5 with `ModuleNotFoundError` / missing table; if you wrote them first you already saw the red state.)

- [ ] **Step 8: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add membership_policies table with per-tier budget and quota columns\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 2: Policy resolution service (`ResolvedPolicy` + `PolicyService`)

**Files:**
- Create: `backend/app/modules/orchestration/repository.py`
- Create: `backend/app/modules/orchestration/policy.py`
- Test: `backend/tests/orchestration/test_policy_resolution.py`

**Interfaces:**
- Consumes: `MembershipPolicy` (Task 1), `UserRead` (has `membership: Membership`, `is_admin: bool`), `Settings.llm_runtime`.
- Produces (used by Tasks 3–5 and Part B):
  - `MembershipPolicyRepository(session)`: `async get_by_membership(membership: str) -> MembershipPolicy | None`, `async list_all() -> list[MembershipPolicy]`, `async save(row) -> MembershipPolicy`, `def add(row) -> None`
  - `ResolvedPolicy` frozen dataclass: `membership: str`, `is_admin: bool`, the seven per-turn caps (same names/types as `LlmRuntimeSettings`), `tier_overridden: tuple[str, ...]` — no quota fields (quotas resolve via Part B's quotas module)
  - `PolicyService(session, settings)`: `async resolve(user: UserRead) -> ResolvedPolicy`
  - Module constant `_PER_TURN_FIELDS` (private; Task 5 reuses via `PolicyService.inherited_defaults`)

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/orchestration/test_policy_resolution.py
"""Resolution chain permutations: tier set/NULL x runtime override present/absent."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.core.config import Settings, get_settings
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.policy import PolicyService
from app.modules.orchestration.seed import seed_membership_policies
from app.modules.runtime_config import cache
from app.modules.runtime_config.service import RuntimeConfigService
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.factories import make_settings


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
        await db.rollback()
        await db.execute(delete(MembershipPolicy))
        await db.commit()
        await seed_membership_policies(db)
    await engine.dispose()


def _user(membership: Membership = Membership.FREE, *, is_admin: bool = False) -> UserRead:
    """resolve() only reads membership/is_admin — no DB user needed."""
    return UserRead(
        id=uuid4(),
        username="policy-test",
        email=None,
        is_admin=is_admin,
        membership=membership,
        created_at=datetime.now(UTC),
    )


async def _set_free_tier(session: AsyncSession, **values: int | float | None) -> None:
    await session.execute(delete(MembershipPolicy))
    await session.commit()
    await seed_membership_policies(session)
    row = (
        await session.execute(
            select(MembershipPolicy).where(MembershipPolicy.membership == Membership.FREE.value)
        )
    ).scalar_one()
    for field, value in values.items():
        setattr(row, field, value)
    await session.commit()


def _effective(base: Settings, **runtime_overrides: int | float) -> Settings:
    """Simulate get_effective_settings output (runtime_config layer applied)."""
    runtime = base.llm_runtime.model_copy(update=runtime_overrides)
    return base.model_copy(update={"llm_runtime": runtime})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tier_null_inherits_env_default(session: AsyncSession) -> None:
    await _set_free_tier(session)  # all NULL
    settings = make_settings(llm_max_tool_iters=9)
    policy = await PolicyService(session, settings).resolve(_user())
    assert policy.max_tool_iters == 9
    assert policy.tier_overridden == ()
    assert policy.membership == "free"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tier_null_inherits_runtime_override(session: AsyncSession) -> None:
    await _set_free_tier(session)
    settings = _effective(make_settings(llm_max_tool_iters=9), max_tool_iters=4)
    policy = await PolicyService(session, settings).resolve(_user())
    assert policy.max_tool_iters == 4


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tier_value_beats_runtime_override_even_when_looser(
    session: AsyncSession,
) -> None:
    # Specificity-wins, NOT strictest-wins: 12 > 4 and the tier still wins.
    await _set_free_tier(session, max_tool_iters=12)
    settings = _effective(make_settings(llm_max_tool_iters=9), max_tool_iters=4)
    policy = await PolicyService(session, settings).resolve(_user())
    assert policy.max_tool_iters == 12
    assert "max_tool_iters" in policy.tier_overridden


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tier_value_beats_env_default(session: AsyncSession) -> None:
    await _set_free_tier(session, max_turn_cost_usd=0.5, max_hitl_rounds=1)
    policy = await PolicyService(session, make_settings()).resolve(_user())
    assert policy.max_turn_cost_usd == 0.5
    assert policy.max_hitl_rounds == 1
    # Untouched fields still inherit.
    assert policy.max_external_calls == make_settings().llm_runtime.max_external_calls


@pytest.mark.integration
@pytest.mark.asyncio
async def test_missing_row_inherits_everything(session: AsyncSession) -> None:
    await session.execute(delete(MembershipPolicy))
    await session.commit()
    settings = make_settings(llm_max_turn_tokens_out=1234)
    policy = await PolicyService(session, settings).resolve(_user())
    assert policy.max_turn_tokens_out == 1234
    assert policy.tier_overridden == ()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_identity_passes_through(session: AsyncSession) -> None:
    await _set_free_tier(session)
    policy = await PolicyService(session, make_settings()).resolve(
        _user(is_admin=True)
    )
    assert policy.is_admin is True
    assert policy.membership == "free"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_chain_through_real_runtime_config(session: AsyncSession) -> None:
    """End-to-end: app_settings override row -> effective_settings -> resolve."""
    await _set_free_tier(session)
    admin = await UserService(session).ensure_user(
        UserCreate(username=f"pol_{uuid4().hex[:8]}", password="test-pass-123")
    )
    base = make_settings(llm_max_tool_iters=9)
    rc = RuntimeConfigService(session, base)
    await rc.set_override("llm_runtime.max_tool_iters", 3, updated_by=admin.id)
    await session.commit()
    try:
        effective = await RuntimeConfigService(session, base).effective_settings()
        policy = await PolicyService(session, effective).resolve(_user())
        assert policy.max_tool_iters == 3
    finally:
        await rc.clear_override("llm_runtime.max_tool_iters", updated_by=admin.id)
        await session.commit()
        cache.invalidate()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/orchestration/test_policy_resolution.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.modules.orchestration.policy'`

- [ ] **Step 3: Implement the repository**

```python
# backend/app/modules/orchestration/repository.py
"""DB access for orchestration-owned tables (membership_policies only)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orchestration.models import MembershipPolicy


class MembershipPolicyRepository:
    """membership_policies access — this module's table only."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_membership(self, membership: str) -> MembershipPolicy | None:
        stmt = select(MembershipPolicy).where(MembershipPolicy.membership == membership)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_all(self) -> list[MembershipPolicy]:
        stmt = select(MembershipPolicy).order_by(MembershipPolicy.membership)
        return list((await self._session.execute(stmt)).scalars().all())

    def add(self, row: MembershipPolicy) -> None:
        self._session.add(row)

    async def save(self, row: MembershipPolicy) -> MembershipPolicy:
        await self._session.flush()
        await self._session.refresh(row)
        return row
```

- [ ] **Step 4: Implement `policy.py`**

```python
# backend/app/modules/orchestration/policy.py
"""Per-tier policy resolution: specificity-wins over effective settings.

Chain (spec §3.2): tier row field if NOT NULL, else the effective runtime
setting. The Settings instance handed in must already be runtime-config
effective (the chat path builds services via `get_effective_settings`), so
the runtime-override and env-default layers are pre-collapsed here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.repository import MembershipPolicyRepository
from app.modules.users.schemas import UserRead

logger = logging.getLogger(__name__)

# Per-turn caps. Names match BOTH LlmRuntimeSettings fields and
# MembershipPolicy columns, so one list drives the whole chain.
_PER_TURN_FIELDS = (
    "max_tool_iters",
    "max_external_calls",
    "max_turn_tokens_in",
    "max_turn_tokens_out",
    "max_turn_cost_usd",
    "run_deadline_seconds",
    "max_hitl_rounds",
)


@dataclass(frozen=True, slots=True)
class ResolvedPolicy:
    """Frozen per-turn policy for one user, resolved once at turn start.

    Per-turn caps only. Monthly/standing quotas resolve through the quotas
    module (Part B) — deliberately NOT carried here.
    """

    membership: str
    is_admin: bool
    max_tool_iters: int
    max_external_calls: int
    max_turn_tokens_in: int
    max_turn_tokens_out: int
    max_turn_cost_usd: float
    run_deadline_seconds: int
    max_hitl_rounds: int
    tier_overridden: tuple[str, ...]


class PolicyService:
    """Resolves and (Task 5) administers per-tier AI policies."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._repo = MembershipPolicyRepository(session)
        self._settings = settings

    async def resolve(self, user: UserRead) -> ResolvedPolicy:
        """Frozen policy for this user's tier. Missing row = inherit all."""
        row = await self._repo.get_by_membership(user.membership.value)
        if row is None:
            logger.warning(
                "no membership_policies row; inheriting all defaults",
                extra={"membership": user.membership.value},
            )
        caps, overridden = self._per_turn_caps(row)
        policy = ResolvedPolicy(
            membership=user.membership.value,
            is_admin=user.is_admin,
            tier_overridden=tuple(overridden),
            **caps,
        )
        # Policy values are not secrets — log freely (spec §4.3).
        logger.info(
            "tier policy resolved",
            extra={"membership": policy.membership, "tier_overridden": overridden, **caps},
        )
        return policy

    def _per_turn_caps(
        self, row: MembershipPolicy | None
    ) -> tuple[dict[str, Any], list[str]]:
        runtime = self._settings.llm_runtime
        caps: dict[str, Any] = {}
        overridden: list[str] = []
        for field in _PER_TURN_FIELDS:
            tier_value = getattr(row, field) if row is not None else None
            if tier_value is None:
                caps[field] = getattr(runtime, field)
            else:
                caps[field] = tier_value
                overridden.append(field)
        return caps, overridden
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/orchestration/test_policy_resolution.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add per-tier policy resolution service (specificity-wins chain)\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 3: Wire the orchestration loop to the resolved policy

**Files:**
- Modify: `backend/app/modules/orchestration/budget.py`
- Modify: `backend/app/modules/orchestration/service.py` (`run`, `resume_confirm`, `_resume_confirm`, `_pause_for_confirm`)
- Modify: `backend/app/modules/llm/chat_service.py` (`stream_chat`, `stream_confirm`)
- Modify: `backend/app/modules/llm/router.py` (pass `user`, not `user.id`)
- Modify: existing tests that call `stream_chat`/`stream_confirm` with `user.id` (see Step 4)
- Test: `backend/tests/orchestration/test_tier_budgets.py`

**Interfaces:**
- Consumes: `PolicyService.resolve`, `ResolvedPolicy` (Task 2).
- Produces (used by Task 4 and Part B):
  - `RunBudget` gains fields `run_deadline_seconds: int`, `max_hitl_rounds: int`, `membership: str = "unknown"` and classmethod `from_policy(policy: ResolvedPolicy) -> RunBudget`; `from_settings` remains (existing budget tests keep passing — proof of no behavior change); `summary()` gains a `"membership"` key (flows into every `done` event — the existing run record, spec §4.3).
  - `OrchestrationService.run(user: UserRead, conversation_id, ui_context=None)` and `resume_confirm(user: UserRead, ...)` — `UUID` first params replaced by `UserRead`.
  - `ChatService.stream_chat(user: UserRead, message, conversation_id, ui_context=None)`, `stream_confirm(user: UserRead, ...)`. (`get_conversation` keeps taking `user_id: UUID`.)

- [ ] **Step 1: Extend `RunBudget`**

In `backend/app/modules/orchestration/budget.py`: add `from app.modules.orchestration.policy import ResolvedPolicy` to imports; add the three fields **between** `deadline_mono` and the counter defaults:

```python
    max_cost_usd: float
    deadline_mono: float
    run_deadline_seconds: int
    max_hitl_rounds: int
    membership: str = "unknown"
    tokens_in: int = 0
```

Update `from_settings` and add `from_policy`:

```python
    @classmethod
    def from_settings(cls, settings: Settings) -> RunBudget:
        """Build budget from app settings (tests / non-tier callers)."""
        runtime = settings.llm_runtime
        return cls(
            max_iters=runtime.max_tool_iters,
            max_external_calls=runtime.max_external_calls,
            max_tokens_in=runtime.max_turn_tokens_in,
            max_tokens_out=runtime.max_turn_tokens_out,
            max_cost_usd=runtime.max_turn_cost_usd,
            deadline_mono=time.monotonic() + runtime.run_deadline_seconds,
            run_deadline_seconds=runtime.run_deadline_seconds,
            max_hitl_rounds=runtime.max_hitl_rounds,
        )

    @classmethod
    def from_policy(cls, policy: ResolvedPolicy) -> RunBudget:
        """Build budget from a frozen per-tier policy (the production path)."""
        return cls(
            max_iters=policy.max_tool_iters,
            max_external_calls=policy.max_external_calls,
            max_tokens_in=policy.max_turn_tokens_in,
            max_tokens_out=policy.max_turn_tokens_out,
            max_cost_usd=policy.max_turn_cost_usd,
            deadline_mono=time.monotonic() + policy.run_deadline_seconds,
            run_deadline_seconds=policy.run_deadline_seconds,
            max_hitl_rounds=policy.max_hitl_rounds,
            membership=policy.membership,
        )
```

In `summary()`, add `"membership": self.membership,` to the returned dict.

- [ ] **Step 2: Thread `UserRead` through orchestration**

In `backend/app/modules/orchestration/service.py`:

Add imports: `from app.modules.orchestration.policy import PolicyService` and `from app.modules.users.schemas import UserRead`.

Replace `run` (currently `service.py:164`):

```python
    async def run(
        self,
        user: UserRead,
        conversation_id: UUID,
        ui_context: dict[str, Any] | None = None,
    ) -> AsyncIterator[ChatSseEvent]:
        """Yield SSE events for one tool-using assistant turn."""
        policy = await PolicyService(self._session, self._settings).resolve(user)
        ctx = self._make_ctx(user.id, conversation_id, uuid4())
        budget = RunBudget.from_policy(policy)
        context = await ConversationContextService(
            self._repo,
            self._llm,
            self._settings,
        ).build(user.id, conversation_id)
```

(the rest of the body is unchanged — `messages = ...` etc.).

In `resume_confirm` and `_resume_confirm`, change the first parameter from `user_id: UUID` to `user: UserRead`, and inside `_resume_confirm` use `user.id` where `user_id` was used (`_require_pending(user.id, ...)`, `_make_ctx(user.id, ...)`). Replace the budget line (`service.py:227`) with a fresh per-turn resolve (Task 4 will prefer the frozen snapshot):

```python
        budget = RunBudget.from_policy(
            await PolicyService(self._session, self._settings).resolve(user)
        )
        apply_budget_snapshot(budget, budget_raw)
```

In `_pause_for_confirm` (`service.py:435`), replace the settings read:

```python
        if pack.hitl_rounds >= pack.budget.max_hitl_rounds:
```

In `backend/app/modules/llm/chat_service.py`: add `from app.modules.users.schemas import UserRead`; change `stream_chat(self, user_id: UUID, ...)` to `stream_chat(self, user: UserRead, ...)` and `stream_confirm(self, user_id: UUID, ...)` to `stream_confirm(self, user: UserRead, ...)`. Inside, use `user.id` for `_prepare_conversation` / `get_conversation_for_user`, and pass `user` to `orch.run(...)` / `orch.resume_confirm(...)`.

In `backend/app/modules/llm/router.py`: `service.stream_chat(user, body.message, ...)` (line 73) and `service.stream_confirm(user, conversation_id, body.call_id, ...)` (line 94).

- [ ] **Step 3: Verify no other production call sites remain**

```bash
grep -rn "stream_chat(\|stream_confirm(\|\.run(user_id\|resume_confirm(" backend/app | grep -v "def "
```

Expected: only the router lines you just updated (plus unrelated matches like arq `.run(` if any — inspect each).

- [ ] **Step 4: Update existing test call sites**

```bash
grep -rln "stream_chat(user.id\|stream_confirm(\s*user.id\|stream_chat(\s*user.id" backend/tests
grep -rln "stream_chat(\|stream_confirm(" backend/tests
```

In every hit (expected: `tests/llm/test_orchestration.py`, `test_hitl.py`, `test_chat.py`, `test_message_ordering.py`, `test_download_confirmation_outcome.py`, `test_import_discovered_hitl.py`, `test_audio_download_form.py`, `test_propose_choices.py`, `test_conversation_context.py` — the actual list comes from the grep), change the first argument from `user.id` to `user` (the helpers there already return `UserRead` from `ensure_user`). Calls to `get_conversation(user.id, ...)` stay unchanged. Do **not** change test logic — this is a mechanical signature update; these suites passing is the "no behavior change with all-NULL rows" proof.

- [ ] **Step 5: Write the failing tier-enforcement tests**

```python
# backend/tests/orchestration/test_tier_budgets.py
"""Tier rows drive the loop budget without restart (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from app.core.config import Settings, get_settings
from app.modules.llm.chat_service import ChatService
from app.modules.llm.types import ToolCall, ToolCallingRequest, ToolCallingResponse, Usage
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.seed import seed_membership_policies
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
        await db.execute(delete(MembershipPolicy))
        await db.commit()
        await seed_membership_policies(db)
        yield db
        await db.rollback()
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


async def _user(session: AsyncSession) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(username=f"tier_{uuid4().hex[:8]}", password="test-pass-123")
    )


async def _tighten_free_tier(session: AsyncSession, **values: int | float) -> None:
    row = (
        await session.execute(
            select(MembershipPolicy).where(MembershipPolicy.membership == Membership.FREE.value)
        )
    ).scalar_one()
    for field, value in values.items():
        setattr(row, field, value)
    await session.commit()


def _tool_then_text_llm() -> Any:
    calls = {"n": 0}

    async def _fake(req: ToolCallingRequest, **_kwargs: Any) -> ToolCallingResponse:
        del req
        calls["n"] += 1
        if calls["n"] == 1:
            return ToolCallingResponse(
                text=None,
                tool_calls=[
                    ToolCall(id="t1", name="search_user_books", arguments={"query": "x"})
                ],
                usage=Usage(10, 5),
                model="gemini-3.5-flash-lite",
                provider="gemini",
            )
        return ToolCallingResponse(
            text="All done.",
            tool_calls=[],
            usage=Usage(10, 5),
            model="gemini-3.5-flash-lite",
            provider="gemini",
        )

    return _fake


@pytest.mark.integration
@pytest.mark.asyncio
async def test_all_null_row_behaves_like_settings(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(session)
    service = ChatService(session, _settings())
    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_tool_then_text_llm()))
    events = [e async for e in service.stream_chat(user, "list my books", None)]
    assert events[-1].event == "done"
    assert events[-1].data["status"] == "complete"
    assert events[-1].data["membership"] == "free"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tier_row_tightens_iters_without_restart(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The fake needs 2 LLM rounds (tool round + answer); tier allows 1.
    await _tighten_free_tier(session, max_tool_iters=1)
    user = await _user(session)
    service = ChatService(session, _settings())
    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_tool_then_text_llm()))
    events = [e async for e in service.stream_chat(user, "list my books", None)]
    error = next(e for e in events if e.event == "error")
    assert error.data["code"] == "budget_exceeded"
    assert "iterations" in error.data["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tier_row_tightens_cost_cap(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _tighten_free_tier(session, max_turn_cost_usd=0.000001)
    user = await _user(session)
    service = ChatService(session, _settings())

    async def _costly(req: ToolCallingRequest, **_kwargs: Any) -> ToolCallingResponse:
        del req
        return ToolCallingResponse(
            text=None,
            tool_calls=[ToolCall(id="c1", name="search_user_books", arguments={"query": "x"})],
            usage=Usage(10, 5, cost_usd=0.01),
            model="gemini-3.5-flash-lite",
            provider="gemini",
        )

    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_costly))
    events = [e async for e in service.stream_chat(user, "hello", None)]
    error = next(e for e in events if e.event == "error")
    assert error.data["code"] == "budget_exceeded"
```

(`Usage` is `(tokens_in, tokens_out, cost_usd=None)` in `app/modules/llm/types.py:45` — the keyword form above is valid; `_accumulate` reads `resp.usage.cost_usd`.)

- [ ] **Step 6: Run the new tests to verify they fail, then the wiring makes them pass**

Run: `uv run pytest tests/orchestration/test_tier_budgets.py -v`
Expected before Step 1–2: FAIL (signature mismatch). After: PASS (3 tests).

- [ ] **Step 7: Run the full suite — the no-behavior-change proof**

Run: `uv run pytest -m "unit or integration"`
Expected: PASS, including all pre-existing budget/orchestration/HITL/chat tests, with only the mechanical `user.id` → `user` edits from Step 4.

- [ ] **Step 8: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: drive orchestration budgets from frozen per-tier policy\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 4: Freeze the resolved caps across HITL pauses

**Files:**
- Modify: `backend/app/modules/orchestration/hitl_pause.py`
- Modify: `backend/app/modules/orchestration/service.py` (`_resume_confirm` budget restore)
- Test: `backend/tests/orchestration/test_hitl_frozen_policy.py`

**Interfaces:**
- Consumes: `RunBudget` fields incl. `run_deadline_seconds`/`max_hitl_rounds`/`membership` (Task 3).
- Produces: freeze snapshot `"budget"` dict gains a `"caps"` sub-dict; `budget_from_snapshot(raw: dict[str, Any]) -> RunBudget | None` in `hitl_pause.py` (None for pre-caps legacy snapshots → caller resolves fresh).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/orchestration/test_hitl_frozen_policy.py
"""A resumed turn uses the policy resolved at turn start (spec §3.4)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.core.config import Settings, get_settings
from app.modules.llm.chat_service import ChatService
from app.modules.llm.types import ToolCall, ToolCallingRequest, ToolCallingResponse, Usage
from app.modules.orchestration.hitl_pause import budget_from_snapshot
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.seed import seed_membership_policies
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.factories import make_settings
from tests.llm.stream_fakes import stream_from_call

_URL = "https://novelfull.net/book/foo.html"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(delete(MembershipPolicy))
        await db.commit()
        await seed_membership_policies(db)
        yield db
        await db.rollback()
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
        llm_assistant_mode="external_allowed",
    )


async def _user(session: AsyncSession) -> UserRead:
    return await UserService(session).ensure_user(
        UserCreate(username=f"frz_{uuid4().hex[:8]}", password="test-pass-123")
    )


def _scrape_then_reply() -> Any:
    calls = {"n": 0}

    async def _fake(req: ToolCallingRequest, **_kwargs: Any) -> ToolCallingResponse:
        del req
        calls["n"] += 1
        if calls["n"] == 1:
            return ToolCallingResponse(
                text=None,
                tool_calls=[
                    ToolCall(
                        id="sc1",
                        name="scrape_book_range",
                        arguments={"url": _URL, "start_chapter": 1, "chapter_count": 10},
                    )
                ],
                usage=Usage(10, 5),
                model="gemini-3.5-flash-lite",
                provider="gemini",
            )
        return ToolCallingResponse(
            text="Understood, not scraping.",
            tool_calls=[],
            usage=Usage(12, 6),
            model="gemini-3.5-flash-lite",
            provider="gemini",
        )

    return _fake


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resume_uses_caps_frozen_at_turn_start(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tighten the tier mid-pause; the resumed turn still runs under old caps."""
    user = await _user(session)
    service = ChatService(session, _settings())
    monkeypatch.setattr(service._llm, "stream_tools", stream_from_call(_scrape_then_reply()))

    events = [e async for e in service.stream_chat(user, "scrape this", None)]
    assert events[-1].data.get("status") == "awaiting_confirmation"
    call_id = UUID(str(events[-1].data["call_id"]))
    conv_id = UUID(str(events[0].data["conversation_id"]))

    # Mid-pause tier change: 1 iteration would already be exhausted.
    await session.execute(
        update(MembershipPolicy)
        .where(MembershipPolicy.membership == Membership.FREE.value)
        .values(max_tool_iters=1)
    )
    await session.commit()

    # Decline -> the loop resumes for the wrap-up LLM round (iteration 2).
    # Frozen caps (default 6) allow it; a re-resolve (cap 1) would not.
    resume = [
        e
        async for e in service.stream_confirm(
            user, conv_id, call_id, approved=False, values=None
        )
    ]
    assert not [e for e in resume if e.event == "error"]
    assert resume[-1].data.get("status") == "complete"
    assert resume[-1].data.get("membership") == "free"


@pytest.mark.unit
def test_legacy_snapshot_without_caps_returns_none() -> None:
    raw = {"cost_usd": 0.1, "iters": 2, "external_calls": 1, "tokens_in": 5, "tokens_out": 3}
    assert budget_from_snapshot(raw) is None


@pytest.mark.unit
def test_snapshot_roundtrip_restores_caps_and_counters() -> None:
    raw = {
        "cost_usd": 0.01,
        "iters": 2,
        "external_calls": 1,
        "tokens_in": 100,
        "tokens_out": 50,
        "caps": {
            "max_iters": 9,
            "max_external_calls": 4,
            "max_tokens_in": 1000,
            "max_tokens_out": 500,
            "max_cost_usd": 0.5,
            "run_deadline_seconds": 77,
            "max_hitl_rounds": 2,
            "membership": "free",
        },
    }
    budget = budget_from_snapshot(raw)
    assert budget is not None
    assert budget.max_iters == 9
    assert budget.iters == 2
    assert budget.max_hitl_rounds == 2
    assert budget.run_deadline_seconds == 77
    assert budget.membership == "free"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/orchestration/test_hitl_frozen_policy.py -v`
Expected: FAIL — `ImportError: cannot import name 'budget_from_snapshot'`.

- [ ] **Step 3: Extend the freeze snapshot**

In `backend/app/modules/orchestration/hitl_pause.py`: add `import time` to imports. In `freeze_pending`, extend the `"budget"` entry of `snapshot`:

```python
        "budget": {
            "cost_usd": req.budget.cost_usd,
            "iters": req.budget.iters,
            "external_calls": req.budget.external_calls,
            "tokens_in": req.budget.tokens_in,
            "tokens_out": req.budget.tokens_out,
            # Frozen caps: a resumed turn must use the policy resolved at
            # turn start, never a fresh resolve (spec §3.4).
            "caps": {
                "max_iters": req.budget.max_iters,
                "max_external_calls": req.budget.max_external_calls,
                "max_tokens_in": req.budget.max_tokens_in,
                "max_tokens_out": req.budget.max_tokens_out,
                "max_cost_usd": req.budget.max_cost_usd,
                "run_deadline_seconds": req.budget.run_deadline_seconds,
                "max_hitl_rounds": req.budget.max_hitl_rounds,
                "membership": req.budget.membership,
            },
        },
```

Change `restore_snapshot`'s return annotation for the budget dict from `dict[str, float | int]` to `dict[str, Any]` (it now nests `caps`), and update `apply_budget_snapshot(budget: RunBudget, raw: dict[str, Any])` to match. Add:

```python
def budget_from_snapshot(raw: dict[str, Any]) -> RunBudget | None:
    """Rebuild the frozen budget (caps + counters) from a pause snapshot.

    Returns None for pre-caps legacy snapshots — the caller resolves policy
    fresh (one-time fallback). The wall-clock window RESTARTS here: the
    frozen run_deadline_seconds value applies from now, not from the
    original turn start, or every resume after a long pause would expire
    instantly (spec §3.4). The cap is frozen; the clock is per segment.
    """
    caps = raw.get("caps")
    if not isinstance(caps, dict):
        return None
    seconds = int(caps["run_deadline_seconds"])
    budget = RunBudget(
        max_iters=int(caps["max_iters"]),
        max_external_calls=int(caps["max_external_calls"]),
        max_tokens_in=int(caps["max_tokens_in"]),
        max_tokens_out=int(caps["max_tokens_out"]),
        max_cost_usd=float(caps["max_cost_usd"]),
        deadline_mono=time.monotonic() + seconds,
        run_deadline_seconds=seconds,
        max_hitl_rounds=int(caps["max_hitl_rounds"]),
        membership=str(caps.get("membership") or "unknown"),
    )
    apply_budget_snapshot(budget, raw)
    return budget
```

- [ ] **Step 4: Prefer the frozen snapshot on resume**

In `backend/app/modules/orchestration/service.py::_resume_confirm`, replace the budget block from Task 3 with:

```python
        budget = budget_from_snapshot(budget_raw)
        if budget is None:
            budget = RunBudget.from_policy(
                await PolicyService(self._session, self._settings).resolve(user)
            )
            apply_budget_snapshot(budget, budget_raw)
```

Add `budget_from_snapshot` to the existing `from app.modules.orchestration.hitl_pause import (...)` block.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/orchestration/test_hitl_frozen_policy.py tests/llm/test_hitl.py -v`
Expected: PASS (new tests + the pre-existing HITL suite unchanged).

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: freeze resolved tier caps across HITL pauses\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 5: Admin API for membership policies

**Files:**
- Create: `backend/app/modules/orchestration/schemas.py`
- Modify: `backend/app/modules/orchestration/policy.py` (admin methods)
- Create: `backend/app/modules/orchestration/admin_router.py`
- Modify: `backend/app/main.py` (register router)
- Test: `backend/tests/orchestration/test_membership_policy_api.py`

**Interfaces:**
- Consumes: `PolicyService`, `MembershipPolicyRepository` (Task 2), `require_admin`, `get_effective_settings`.
- Produces (used by Task 6's frontend and Part B's usage screen):
  - `GET /api/admin/membership-policies` → `{"policies": [MembershipPolicyRead...], "inherited": {"max_tool_iters": 6, ...}}` (inherited = current effective per-turn defaults, for rendering "inherit (6)")
  - `PATCH /api/admin/membership-policies/{membership}` (path param typed `Membership` → 422 on unknown tier) with `MembershipPolicyPatch` body — omitted field unchanged; explicit `null` clears to inherit. No POST/DELETE: rows mirror the enum.
  - `PolicyService.list_policies() -> list[MembershipPolicy]`, `inherited_defaults() -> dict[str, float | int]`, `patch_policy(membership: Membership, patch: MembershipPolicyPatch, *, actor_id: UUID) -> MembershipPolicy` (self-heals a missing row for a valid enum value).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/orchestration/test_membership_policy_api.py
"""Admin membership-policies API: authz + PATCH semantics (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from uuid import UUID

import pytest
from app.core.config import get_settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.orchestration.models import MembershipPolicy
from app.modules.orchestration.seed import seed_membership_policies
from app.modules.users.membership import Membership
from app.modules.users.models import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.dbcleanup import clear_users

_HOST = "test.local"  # single-label hosts drop cookies (see test_auth_api.py)
BASE = "/api/admin/membership-policies"


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
        await session.execute(delete(MembershipPolicy))
        await session.commit()
        await seed_membership_policies(session)
    async with engine.begin() as conn:
        await clear_users(conn)
    app.dependency_overrides[get_db] = _make_db_override(session_factory)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=f"http://{_HOST}") as http:
        yield http
    app.dependency_overrides.clear()
    async with session_factory() as session:
        await session.execute(delete(MembershipPolicy))
        await session.commit()
        await seed_membership_policies(session)
    async with engine.begin() as conn:
        await clear_users(conn)
    await engine.dispose()


async def _create_user(username: str, *, is_admin: bool) -> UUID:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=None,
            google_sub=f"{username}-sub",
            is_admin=is_admin,
        )
        session.add(user)
        await session.commit()
        user_id = user.id
    await engine.dispose()
    return user_id


def _login(client: AsyncClient, user_id: UUID, username: str) -> None:
    token = create_access_token(user_id=user_id, username=username, settings=get_settings())
    client.cookies.set(COOKIE_NAME, token, domain=_HOST, path="/")


@pytest.fixture
async def admin_client(client: AsyncClient) -> AsyncClient:
    user_id = await _create_user("policy-admin", is_admin=True)
    _login(client, user_id, "policy-admin")
    return client


@pytest.mark.integration
async def test_anonymous_gets_401(client: AsyncClient) -> None:
    assert (await client.get(BASE)).status_code == 401


@pytest.mark.integration
async def test_non_admin_gets_403(client: AsyncClient) -> None:
    user_id = await _create_user("policy-user", is_admin=False)
    _login(client, user_id, "policy-user")
    assert (await client.get(BASE)).status_code == 403


@pytest.mark.integration
async def test_list_returns_row_per_tier_with_inherited_defaults(
    admin_client: AsyncClient,
) -> None:
    response = await admin_client.get(BASE)
    assert response.status_code == 200
    body = response.json()
    memberships = {p["membership"] for p in body["policies"]}
    assert memberships == {m.value for m in Membership}
    assert body["inherited"]["max_tool_iters"] >= 1
    free = next(p for p in body["policies"] if p["membership"] == "free")
    assert free["max_tool_iters"] is None  # NULL = inherit


@pytest.mark.integration
async def test_patch_sets_and_clears_fields(admin_client: AsyncClient) -> None:
    patched = await admin_client.patch(
        f"{BASE}/free", json={"max_tool_iters": 3, "max_hitl_rounds": 1}
    )
    assert patched.status_code == 200
    assert patched.json()["max_tool_iters"] == 3
    assert patched.json()["max_hitl_rounds"] == 1

    # Omitted fields unchanged; explicit null clears back to inherit.
    cleared = await admin_client.patch(f"{BASE}/free", json={"max_tool_iters": None})
    assert cleared.status_code == 200
    assert cleared.json()["max_tool_iters"] is None
    assert cleared.json()["max_hitl_rounds"] == 1


@pytest.mark.integration
async def test_patch_rejects_invalid_values_and_unknown_tier(
    admin_client: AsyncClient,
) -> None:
    assert (
        await admin_client.patch(f"{BASE}/free", json={"max_tool_iters": 0})
    ).status_code == 422
    assert (
        await admin_client.patch(f"{BASE}/platinum", json={"max_tool_iters": 3})
    ).status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/orchestration/test_membership_policy_api.py -v`
Expected: FAIL — 404 (routes missing).

- [ ] **Step 3: Write the schemas**

```python
# backend/app/modules/orchestration/schemas.py
"""Pydantic DTOs for the membership-policies admin API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.modules.users.membership import Membership


class MembershipPolicyRead(BaseModel):
    """One tier row of per-turn cap overrides. None = inherit."""

    model_config = ConfigDict(from_attributes=True)

    membership: Membership
    max_tool_iters: int | None
    max_external_calls: int | None
    max_turn_tokens_in: int | None
    max_turn_tokens_out: int | None
    max_turn_cost_usd: float | None
    run_deadline_seconds: int | None
    max_hitl_rounds: int | None
    updated_at: datetime


class MembershipPolicyPatch(BaseModel):
    """PATCH body — omitted fields unchanged; explicit null = inherit.

    Bounds mirror LlmRuntimeSettings so a tier override can never carry a
    value the settings layer itself would reject.
    """

    max_tool_iters: Annotated[int, Field(ge=1)] | None = None
    max_external_calls: Annotated[int, Field(ge=0)] | None = None
    max_turn_tokens_in: Annotated[int, Field(ge=1)] | None = None
    max_turn_tokens_out: Annotated[int, Field(ge=1)] | None = None
    max_turn_cost_usd: Annotated[float, Field(gt=0)] | None = None
    run_deadline_seconds: Annotated[int, Field(ge=1)] | None = None
    max_hitl_rounds: Annotated[int, Field(ge=0)] | None = None


class MembershipPoliciesResponse(BaseModel):
    """GET payload: all tier rows + current inherited per-turn defaults."""

    policies: list[MembershipPolicyRead]
    inherited: dict[str, float | int]
```

- [ ] **Step 4: Add admin methods to `PolicyService`**

Append to `PolicyService` in `backend/app/modules/orchestration/policy.py` (add `from uuid import UUID` and `from app.modules.orchestration.schemas import MembershipPolicyPatch` to imports):

```python
    async def list_policies(self) -> list[MembershipPolicy]:
        """All tier rows, ordered by membership."""
        return await self._repo.list_all()

    def inherited_defaults(self) -> dict[str, float | int]:
        """Current effective per-turn values (what NULL inherits right now)."""
        runtime = self._settings.llm_runtime
        return {field: getattr(runtime, field) for field in _PER_TURN_FIELDS}

    async def patch_policy(
        self,
        membership: Membership,
        patch: MembershipPolicyPatch,
        *,
        actor_id: UUID,
    ) -> MembershipPolicy:
        """Apply supplied fields (explicit null clears). Self-heals a missing row."""
        row = await self._repo.get_by_membership(membership.value)
        if row is None:
            row = MembershipPolicy(membership=membership.value)
            self._repo.add(row)
        changes = patch.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(row, field, value)
        saved = await self._repo.save(row)
        logger.info(
            "membership policy updated",
            extra={"membership": membership.value, "actor": str(actor_id), "changes": changes},
        )
        return saved
```

Also add `from app.modules.users.membership import Membership` to `policy.py` imports.

- [ ] **Step 5: Write the router and register it**

```python
# backend/app/modules/orchestration/admin_router.py
"""Admin CRUD for membership AI policies. HTTP only; logic in PolicyService.

PATCH-only by design: rows mirror the Membership enum (no create/delete).
Follows the runtime_config admin router pattern.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.deps import get_db, get_effective_settings, require_admin
from app.modules.orchestration.policy import PolicyService
from app.modules.orchestration.schemas import (
    MembershipPoliciesResponse,
    MembershipPolicyPatch,
    MembershipPolicyRead,
)
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/admin/membership-policies", tags=["admin"])


def _service(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_effective_settings)],
) -> PolicyService:
    return PolicyService(session, settings)


@router.get("")
async def list_policies(
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[PolicyService, Depends(_service)],
) -> MembershipPoliciesResponse:
    """Every tier row plus the current inherited (effective) defaults."""
    rows = await service.list_policies()
    return MembershipPoliciesResponse(
        policies=[MembershipPolicyRead.model_validate(row) for row in rows],
        inherited=service.inherited_defaults(),
    )


@router.patch("/{membership}")
async def patch_policy(
    membership: Membership,
    body: MembershipPolicyPatch,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[PolicyService, Depends(_service)],
) -> MembershipPolicyRead:
    """Update one tier; omitted fields unchanged, explicit null clears."""
    row = await service.patch_policy(membership, body, actor_id=admin.id)
    return MembershipPolicyRead.model_validate(row)
```

In `backend/app/main.py`: add `from app.modules.orchestration.admin_router import router as membership_admin_router` and, in `_register_routers`, `app.include_router(membership_admin_router, prefix=api_prefix)` next to `llm_admin_router`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/orchestration/test_membership_policy_api.py -v`
Expected: PASS (6 tests)

- [ ] **Step 7: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add admin API for membership AI policies\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 6: Backoffice "Memberships" screen

**Files:**
- Create: `frontend/src/features/admin/api/membershipPolicies.ts`
- Create: `frontend/src/features/admin/hooks/useMembershipPolicies.ts`
- Create: `frontend/src/features/admin/logic/policyFields.ts`
- Create: `frontend/src/features/admin/logic/policyFields.test.ts`
- Create: `frontend/src/features/admin/components/policies/PoliciesPage.tsx`
- Create: `frontend/src/features/admin/components/policies/PolicyCard.tsx`
- Create: `frontend/src/features/admin/components/policies/PolicyField.tsx`
- Create: `frontend/src/features/admin/components/policies/PoliciesPage.test.tsx`
- Modify: `frontend/src/features/admin/components/AdminNav.tsx` (nav link)
- Modify: `frontend/src/features/admin/index.ts` (barrel export)
- Modify: `frontend/src/app/App.tsx` (route)

**Interfaces:**
- Consumes: `GET/PATCH /api/admin/membership-policies` (Task 5), `Page`-less list payload `{policies, inherited}`.
- Produces: route `/admin/policies`, nav label "Memberships".

- [ ] **Step 1: Write the failing logic tests**

```typescript
// frontend/src/features/admin/logic/policyFields.test.ts
import { describe, expect, it } from 'vitest'
import { parsePolicyInput, placeholderFor, POLICY_FIELDS } from './policyFields'

describe('parsePolicyInput', () => {
  it('maps blank to null (inherit)', () => {
    expect(parsePolicyInput('')).toBeNull()
    expect(parsePolicyInput('   ')).toBeNull()
  })
  it('parses numbers', () => {
    expect(parsePolicyInput('42')).toBe(42)
    expect(parsePolicyInput('0.25')).toBe(0.25)
  })
  it('rejects garbage and negatives as undefined (invalid)', () => {
    expect(parsePolicyInput('abc')).toBeUndefined()
    expect(parsePolicyInput('-3')).toBeUndefined()
  })
})

describe('placeholderFor', () => {
  it('shows the inherited value for per-turn fields', () => {
    const meta = POLICY_FIELDS.find((f) => f.key === 'max_tool_iters')!
    expect(placeholderFor(meta, { max_tool_iters: 6 })).toBe('inherit (6)')
  })
  it('falls back gracefully when the inherited value is missing', () => {
    const meta = POLICY_FIELDS.find((f) => f.key === 'max_hitl_rounds')!
    expect(placeholderFor(meta, {})).toBe('inherit (—)')
  })
})
```

Run (from `frontend/`): `npm run test -- policyFields` — expected FAIL (module not found).

- [ ] **Step 2: Implement the field metadata + parsing logic**

```typescript
// frontend/src/features/admin/logic/policyFields.ts
export type PolicyFieldKey =
  | 'max_tool_iters'
  | 'max_external_calls'
  | 'max_turn_tokens_in'
  | 'max_turn_tokens_out'
  | 'max_turn_cost_usd'
  | 'run_deadline_seconds'
  | 'max_hitl_rounds'

export type PolicyFieldMeta = {
  key: PolicyFieldKey
  /** All fields here are per-turn caps: null = inherit the runtime setting. */
  label: string
}

export const POLICY_FIELDS: PolicyFieldMeta[] = [
  { key: 'max_tool_iters', label: 'Max tool iterations / turn' },
  { key: 'max_external_calls', label: 'Max external calls / turn' },
  { key: 'max_turn_tokens_in', label: 'Max tokens in / turn' },
  { key: 'max_turn_tokens_out', label: 'Max tokens out / turn' },
  { key: 'max_turn_cost_usd', label: 'Max cost (USD) / turn' },
  { key: 'run_deadline_seconds', label: 'Run deadline (seconds)' },
  { key: 'max_hitl_rounds', label: 'Max confirmation rounds / turn' },
]

/** '' -> null (inherit); invalid -> undefined (block save). */
export function parsePolicyInput(raw: string): number | null | undefined {
  const trimmed = raw.trim()
  if (trimmed === '') return null
  const value = Number(trimmed)
  return Number.isFinite(value) && value >= 0 ? value : undefined
}

export function placeholderFor(
  meta: PolicyFieldMeta,
  inherited: Record<string, number>,
): string {
  const value = inherited[meta.key]
  return `inherit (${value ?? '—'})`
}
```

Run: `npm run test -- policyFields` — expected PASS.

- [ ] **Step 3: API client + hook**

```typescript
// frontend/src/features/admin/api/membershipPolicies.ts
import { apiGet, apiPatch } from '@/shared/lib/api'
import type { PolicyFieldKey } from '@/features/admin/logic/policyFields'

/** Mirrors MembershipPolicyRead (orchestration/schemas.py). */
export type MembershipPolicy = {
  membership: string
  updated_at: string
} & Record<PolicyFieldKey, number | null>

export type MembershipPoliciesResponse = {
  policies: MembershipPolicy[]
  inherited: Record<string, number>
}

export type PolicyPatch = Partial<Record<PolicyFieldKey, number | null>>

export function fetchMembershipPolicies(): Promise<MembershipPoliciesResponse> {
  return apiGet('/api/admin/membership-policies')
}

export function patchMembershipPolicy(
  membership: string,
  patch: PolicyPatch,
): Promise<MembershipPolicy> {
  return apiPatch(`/api/admin/membership-policies/${encodeURIComponent(membership)}`, patch)
}
```

(`apiPatch` is the helper `api/users.ts` uses for admin PATCHes; if the shared client names it differently, match that name.)

```typescript
// frontend/src/features/admin/hooks/useMembershipPolicies.ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchMembershipPolicies,
  patchMembershipPolicy,
  type PolicyPatch,
} from '@/features/admin/api/membershipPolicies'

export const membershipPoliciesKey = ['admin', 'membership-policies'] as const

export function useMembershipPolicies() {
  return useQuery({ queryKey: membershipPoliciesKey, queryFn: fetchMembershipPolicies })
}

export function usePatchMembershipPolicy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ membership, patch }: { membership: string; patch: PolicyPatch }) =>
      patchMembershipPolicy(membership, patch),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: membershipPoliciesKey }),
  })
}
```

- [ ] **Step 4: Components**

```tsx
// frontend/src/features/admin/components/policies/PolicyField.tsx
import type { PolicyFieldMeta } from '@/features/admin/logic/policyFields'
import { placeholderFor } from '@/features/admin/logic/policyFields'

type Props = {
  meta: PolicyFieldMeta
  value: string
  inherited: Record<string, number>
  onChange: (raw: string) => void
}

export function PolicyField({ meta, value, inherited, onChange }: Props) {
  return (
    <label className="flex flex-col gap-0.5 text-sm">
      <span className="text-muted-foreground">{meta.label}</span>
      <input
        className="rounded-md border border-border bg-background px-2 py-1 tabular-nums"
        inputMode="decimal"
        value={value}
        placeholder={placeholderFor(meta, inherited)}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}
```

```tsx
// frontend/src/features/admin/components/policies/PolicyCard.tsx
import { useState } from 'react'
import type { MembershipPolicy, PolicyPatch } from '@/features/admin/api/membershipPolicies'
import { usePatchMembershipPolicy } from '@/features/admin/hooks/useMembershipPolicies'
import { parsePolicyInput, POLICY_FIELDS } from '@/features/admin/logic/policyFields'
import { PolicyField } from './PolicyField'

type Props = { policy: MembershipPolicy; inherited: Record<string, number> }

function initialDrafts(policy: MembershipPolicy): Record<string, string> {
  return Object.fromEntries(
    POLICY_FIELDS.map((f) => [f.key, policy[f.key] === null ? '' : String(policy[f.key])]),
  )
}

export function PolicyCard({ policy, inherited }: Props) {
  const [drafts, setDrafts] = useState(() => initialDrafts(policy))
  const [invalid, setInvalid] = useState(false)
  const mutation = usePatchMembershipPolicy()

  const onSave = () => {
    const patch: PolicyPatch = {}
    for (const field of POLICY_FIELDS) {
      const parsed = parsePolicyInput(drafts[field.key] ?? '')
      if (parsed === undefined) {
        setInvalid(true)
        return
      }
      if (parsed !== (policy[field.key] ?? null)) patch[field.key] = parsed
    }
    setInvalid(false)
    if (Object.keys(patch).length > 0) mutation.mutate({ membership: policy.membership, patch })
  }

  return (
    <div className="rounded-lg border border-border p-4">
      <h2 className="mb-2 font-medium capitalize">{policy.membership}</h2>
      <div className="grid gap-2 sm:grid-cols-2">
        {POLICY_FIELDS.map((meta) => (
          <PolicyField
            key={meta.key}
            meta={meta}
            value={drafts[meta.key] ?? ''}
            inherited={inherited}
            onChange={(raw) => setDrafts((prev) => ({ ...prev, [meta.key]: raw }))}
          />
        ))}
      </div>
      {invalid ? <p className="mt-2 text-sm text-destructive">Enter numbers (or blank).</p> : null}
      <button
        type="button"
        className="mt-3 rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
        disabled={mutation.isPending}
        onClick={onSave}
      >
        {mutation.isPending ? 'Saving…' : 'Save'}
      </button>
    </div>
  )
}
```

```tsx
// frontend/src/features/admin/components/policies/PoliciesPage.tsx
import { useMembershipPolicies } from '@/features/admin/hooks/useMembershipPolicies'
import { PolicyCard } from './PolicyCard'

export function PoliciesPage() {
  const { data, isLoading, error } = useMembershipPolicies()
  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading membership policies…</p>
  }
  if (error || !data) {
    return <p className="text-sm text-destructive">Failed to load membership policies.</p>
  }
  return (
    <section>
      <h1 className="mb-1 text-lg font-semibold">Membership AI policies</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Per-turn caps: blank = inherit the runtime setting. Changes apply on the
        user&apos;s next turn — no restart. (Monthly quotas get their own section
        here in Part B.)
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        {data.policies.map((policy) => (
          <PolicyCard key={policy.membership} policy={policy} inherited={data.inherited} />
        ))}
      </div>
    </section>
  )
}
```

- [ ] **Step 5: Wire nav, route, barrel**

- `AdminNav.tsx`: add `{ to: '/admin/policies', label: 'Memberships' }` after the `Users` entry.
- `frontend/src/features/admin/index.ts`: add `export { PoliciesPage } from './components/policies/PoliciesPage'`.
- `App.tsx`: import `PoliciesPage` from `@/features/admin` and add `<Route path="policies" element={<PoliciesPage />} />` inside the `/admin` route group.

- [ ] **Step 6: Write the page test**

```tsx
// frontend/src/features/admin/components/policies/PoliciesPage.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { PoliciesPage } from './PoliciesPage'
import {
  fetchMembershipPolicies,
  patchMembershipPolicy,
} from '@/features/admin/api/membershipPolicies'

vi.mock('@/features/admin/api/membershipPolicies', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  fetchMembershipPolicies: vi.fn(),
  patchMembershipPolicy: vi.fn(),
}))

const FREE = {
  membership: 'free',
  max_tool_iters: null,
  max_external_calls: null,
  max_turn_tokens_in: null,
  max_turn_tokens_out: null,
  max_turn_cost_usd: null,
  run_deadline_seconds: null,
  max_hitl_rounds: 2,
  updated_at: '2026-07-31T00:00:00Z',
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <PoliciesPage />
    </QueryClientProvider>,
  )
}

describe('PoliciesPage', () => {
  it('renders inherit placeholders for NULL caps', async () => {
    vi.mocked(fetchMembershipPolicies).mockResolvedValue({
      policies: [FREE],
      inherited: { max_tool_iters: 6 },
    })
    renderPage()
    expect(await screen.findByText('free')).toBeTruthy()
    expect(screen.getByPlaceholderText('inherit (6)')).toBeTruthy()
  })

  it('saves only changed fields, blank as null (inherit)', async () => {
    vi.mocked(fetchMembershipPolicies).mockResolvedValue({
      policies: [FREE],
      inherited: { max_tool_iters: 6 },
    })
    vi.mocked(patchMembershipPolicy).mockResolvedValue({ ...FREE, max_tool_iters: 3 })
    renderPage()
    const input = await screen.findByPlaceholderText('inherit (6)')
    fireEvent.change(input, { target: { value: '3' } })
    const hitlInput = screen.getByDisplayValue('2')
    fireEvent.change(hitlInput, { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() =>
      expect(vi.mocked(patchMembershipPolicy)).toHaveBeenCalledWith('free', {
        max_tool_iters: 3,
        max_hitl_rounds: null,
      }),
    )
  })
})
```

- [ ] **Step 7: Run frontend gates**

```bash
npm run test
npm run lint
npm run build
```

Expected: all pass (fix any ESLint size-limit violations by extracting further, never by disabling).

- [ ] **Step 8: Commit**

```bash
printf 'feat: add backoffice membership policies screen\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```
