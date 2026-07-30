# DB-backed Runtime LLM Model Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `model_providers`/`model_configurations` the runtime source of truth for the LLM model catalog (enablement, capabilities, pricing) with a cached per-process snapshot, an admin API to manage it, and the code catalog demoted to seed-only defaults.

**Architecture:** A new `modules/llm/catalog.py` holds a per-process snapshot (`tuple[ModelSpec, ...]`, 30s TTL, invalidate-on-write — same pattern as `modules/runtime_config/cache.py`) loaded async from the DB and read sync by `ModelRouter.candidates()`. `LlmService` entry points await a new `ensure_ready()` that warms the snapshot; `ChatService` uses it at the same boundary where `ensure_enabled()` sits today, so an all-disabled catalog degrades exactly like `llm_enabled=false`. Admin CRUD lives in `modules/llm/admin_router.py` (`/api/admin/llm/catalog`, `require_admin`) calling a new `ModelCatalogAdminService`. Cost recording needs no code change — `ModelSpec` provenance switches to the DB snapshot, so `telemetry.py` unit prices become DB prices automatically (proven by test).

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, pydantic v2, pytest (markers `unit`/`integration`), Postgres.

**Spec:** `docs/superpowers/specs/2026-07-30-llm-model-catalog-db-design.md`.

## Global Constraints

- All backend gates must pass per task, run from `backend/`: `uv run ruff check . --fix && uv run ruff format .`, `uv run mypy .`, `uv run pytest -m "unit or integration"`. No CI — these gates are the only gate.
- `uv` may be missing from PowerShell's PATH on this machine — run `uv` commands through Git Bash.
- Integration tests need Postgres/Redis/MinIO; `tests/conftest.py` pins `DATABASE_URL` to `TEST_DATABASE_URL` (default `rtm_test`) and auto-applies migrations at session start — never point tests at the app DB.
- Commit with `bash scripts/git-commit-clean.sh /tmp/msg.txt` (write the message to `/tmp/msg.txt` first). **Never** add `Co-authored-by`/`Made-with` trailers. Verify with `git log -1 --format=%B`.
- Ruff limits: complexity ≤10, statements ≤20, branches ≤6, args ≤6. Full type hints; strict mypy; no bare `except`.
- Tests build settings via `tests/factories.py::make_settings(**flat_overrides)` — never `Settings()` directly.
- Only the llm module touches `model_providers`/`model_configurations`. Provider SDK imports stay in `modules/llm/providers/`.
- Module dependency direction: router → service → repository. The admin router calls `ModelCatalogAdminService` only.
- Branch: `feature/llm-model-catalog-db`, created off the branch containing the merged runtime_config work (`main` once `feature/runtime-config` merges; otherwise off `feature/runtime-config`).

---

### Task 1: Pricing columns migration + seed writes pricing (insert-if-missing preserved)

**Files:**
- Modify: `backend/app/modules/llm/models.py` (ModelProvider, ModelConfiguration)
- Modify: `backend/app/modules/llm/repository.py` (`upsert_model`)
- Create: `backend/migrations/versions/<generated>_add_model_catalog_pricing.py`
- Test: `backend/tests/llm/test_catalog_seed.py`

**Interfaces:**
- Consumes: existing `ModelSpec.input_cost_per_1m` / `output_cost_per_1m` (registry), `LlmRepository.upsert_provider` / `upsert_model`, `seed_llm_models()`.
- Produces (used by Tasks 2, 5): `ModelConfiguration.input_cost_per_1m: float`, `ModelConfiguration.output_cost_per_1m: float`, `ModelConfiguration.updated_at: datetime`, `ModelProvider.updated_at: datetime`, unique constraint `uq_model_configurations_provider_model` on `(provider_id, model_name)`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/llm/test_catalog_seed.py
"""Seed semantics: pricing on insert; restart never overwrites admin edits."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from app.core.db import SessionLocal
from app.modules.llm.models import ModelConfiguration
from app.modules.llm.seed import seed_llm_models
from sqlalchemy import select, text

LITE = "gemini-3.5-flash-lite"


async def _reset_catalog_rows() -> None:
    async with SessionLocal() as session:
        await session.execute(text("DELETE FROM model_configurations"))
        await session.execute(text("DELETE FROM model_providers"))
        await session.commit()


@pytest.fixture
async def pristine_catalog() -> AsyncIterator[None]:
    """Empty catalog tables before the test; restore seeded defaults after."""
    await _reset_catalog_rows()
    yield
    await _reset_catalog_rows()
    await seed_llm_models()


async def _flash_lite_row() -> ModelConfiguration:
    async with SessionLocal() as session:
        result = await session.execute(
            select(ModelConfiguration).where(ModelConfiguration.model_name == LITE)
        )
        return result.scalar_one()


@pytest.mark.integration
async def test_seed_inserts_pricing(pristine_catalog: None) -> None:
    await seed_llm_models()
    row = await _flash_lite_row()
    assert row.input_cost_per_1m == 0.10
    assert row.output_cost_per_1m == 0.40
    assert row.updated_at is not None


@pytest.mark.integration
async def test_reseed_never_overwrites_admin_edits(pristine_catalog: None) -> None:
    await seed_llm_models()
    async with SessionLocal() as session:
        result = await session.execute(
            select(ModelConfiguration).where(ModelConfiguration.model_name == LITE)
        )
        row = result.scalar_one()
        row.enabled = False
        row.input_cost_per_1m = 9.99
        await session.commit()
    await seed_llm_models()
    row = await _flash_lite_row()
    assert row.enabled is False
    assert row.input_cost_per_1m == 9.99
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `uv run pytest tests/llm/test_catalog_seed.py -v`
Expected: FAIL — `AttributeError` / SQL error: `input_cost_per_1m` does not exist.

- [ ] **Step 3: Update the models**

In `backend/app/modules/llm/models.py`, add `UniqueConstraint` to the `sqlalchemy` import block, then:

To `ModelProvider`, after the `config` column:

```python
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

To `ModelConfiguration`, add a table-args line right under `__tablename__` and three columns after `enabled`:

```python
    __table_args__ = (
        UniqueConstraint(
            "provider_id", "model_name", name="uq_model_configurations_provider_model"
        ),
    )
```

```python
    # USD per 1M tokens; runtime truth for cost records (code catalog is seed-only).
    input_cost_per_1m: Mapped[float] = mapped_column(Float, default=0.0)
    output_cost_per_1m: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 4: Write pricing on seed insert**

In `backend/app/modules/llm/repository.py::upsert_model`, extend the `ModelConfiguration(...)` constructor (insert path only — the early-return for existing rows is what makes seeding never overwrite):

```python
                enabled=spec.enabled,
                input_cost_per_1m=spec.input_cost_per_1m,
                output_cost_per_1m=spec.output_cost_per_1m,
```

- [ ] **Step 5: Generate and fill the migration**

Run: `uv run alembic revision -m "add model catalog pricing and updated_at"` then verify `uv run alembic heads` shows exactly one head. Replace the bodies:

```python
def upgrade() -> None:
    op.add_column(
        "model_configurations",
        sa.Column("input_cost_per_1m", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "model_configurations",
        sa.Column("output_cost_per_1m", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "model_configurations",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "model_providers",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Concurrent workers could have double-seeded before the unique constraint
    # existed; keep one row per (provider_id, model_name) before adding it.
    op.execute(
        sa.text(
            "DELETE FROM model_configurations a USING model_configurations b "
            "WHERE a.provider_id = b.provider_id "
            "AND a.model_name = b.model_name AND a.id > b.id"
        )
    )
    op.create_unique_constraint(
        "uq_model_configurations_provider_model",
        "model_configurations",
        ["provider_id", "model_name"],
    )
    # Backfill prices for rows seeded before this migration. Values are
    # duplicated from the code catalog on purpose — migrations never import
    # app code.
    op.execute(
        sa.text(
            "UPDATE model_configurations "
            "SET input_cost_per_1m = 0.10, output_cost_per_1m = 0.40 "
            "WHERE model_name = 'gemini-3.5-flash-lite'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE model_configurations "
            "SET input_cost_per_1m = 0.30, output_cost_per_1m = 2.50 "
            "WHERE model_name = 'gemini-3.6-flash'"
        )
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_model_configurations_provider_model",
        "model_configurations",
        type_="unique",
    )
    op.drop_column("model_providers", "updated_at")
    op.drop_column("model_configurations", "updated_at")
    op.drop_column("model_configurations", "output_cost_per_1m")
    op.drop_column("model_configurations", "input_cost_per_1m")
```

- [ ] **Step 6: Verify the migration is reversible**

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

Expected: all three succeed. (The test DB is migrated automatically by `tests/conftest.py::pytest_configure`.)

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/llm/test_catalog_seed.py -v`
Expected: PASS (2 tests)

- [ ] **Step 8: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add pricing and updated_at to model catalog tables\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 2: Adapter registry + DB catalog snapshot module

**Files:**
- Modify: `backend/app/modules/llm/providers/__init__.py` (add `KNOWN_ADAPTERS` / `has_adapter`)
- Modify: `backend/app/modules/llm/repository.py` (add `CatalogRow`, `list_catalog_rows`)
- Create: `backend/app/modules/llm/catalog.py`
- Create: `backend/tests/llm/conftest.py` (`seeded_catalog` fixture)
- Test: `backend/tests/llm/test_catalog.py`

**Interfaces:**
- Consumes: Task 1 columns; `ModelSpec` (registry); `ModelCapability`.
- Produces (used by Tasks 3–7):
  - `providers.KNOWN_ADAPTERS: frozenset[str]`, `providers.has_adapter(provider: str) -> bool`
  - `repository.CatalogRow` (frozen dataclass: `provider_name: str`, `provider_enabled: bool`, `model_name: str`, `model_enabled: bool`, `capabilities: list[str]`, `context_window: int`, `supports_tools/supports_structured/supports_streaming: bool`, `input_cost_per_1m/output_cost_per_1m: float`), `LlmRepository.list_catalog_rows() -> list[CatalogRow]`
  - `catalog.CACHE_TTL_SECONDS: float`; `catalog.current_snapshot() -> tuple[ModelSpec, ...]` (empty when cold/expired); `catalog.put_snapshot(specs)`; `catalog.invalidate()`; `async catalog.ensure_loaded(session) -> tuple[ModelSpec, ...]`; `catalog.build_snapshot(rows) -> tuple[ModelSpec, ...]`; `catalog.list_models(*, enabled_only=True)`, `catalog.get_model(provider, model_name)`, `catalog.models_for_capability(capability, *, prefer_provider=None, prefer_model=None)` — same signatures as the registry functions they replace
  - test fixture `seeded_catalog` (pristine seeded rows + cold snapshot, restores after)

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/llm/test_catalog.py
"""Snapshot catalog: cache semantics, row conversion, query functions."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.core.db import SessionLocal
from app.modules.llm import catalog
from app.modules.llm.capabilities import ModelCapability
from app.modules.llm.models import ModelProvider
from app.modules.llm.registry import MODEL_CATALOG
from app.modules.llm.repository import CatalogRow
from sqlalchemy import select

LITE = "gemini-3.5-flash-lite"


@pytest.fixture(autouse=True)
def _fresh_snapshot() -> Iterator[None]:
    catalog.invalidate()
    yield
    catalog.invalidate()


def _row(
    *,
    provider_name: str = "gemini",
    provider_enabled: bool = True,
    model_name: str = LITE,
    model_enabled: bool = True,
    capabilities: list[str] | None = None,
) -> CatalogRow:
    return CatalogRow(
        provider_name=provider_name,
        provider_enabled=provider_enabled,
        model_name=model_name,
        model_enabled=model_enabled,
        capabilities=capabilities if capabilities is not None else ["FAST_CHAT"],
        context_window=1_000_000,
        supports_tools=True,
        supports_structured=True,
        supports_streaming=True,
        input_cost_per_1m=0.1,
        output_cost_per_1m=0.4,
    )


@pytest.mark.unit
def test_build_snapshot_computes_effective_enabled() -> None:
    specs = catalog.build_snapshot([_row(provider_enabled=False)])
    assert len(specs) == 1
    assert specs[0].enabled is False
    assert specs[0].input_cost_per_1m == 0.1


@pytest.mark.unit
def test_build_snapshot_skips_rows_without_adapter() -> None:
    specs = catalog.build_snapshot([_row(provider_name="openai"), _row()])
    assert [m.provider for m in specs] == ["gemini"]


@pytest.mark.unit
def test_build_snapshot_tolerates_unknown_capability() -> None:
    specs = catalog.build_snapshot([_row(capabilities=["FAST_CHAT", "NOT_A_CAP"])])
    assert specs[0].capabilities == frozenset({ModelCapability.FAST_CHAT})


@pytest.mark.unit
def test_snapshot_expires_after_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"now": 100.0}
    monkeypatch.setattr("app.modules.llm.catalog.monotonic", lambda: clock["now"])
    catalog.put_snapshot(MODEL_CATALOG)
    assert catalog.current_snapshot() == MODEL_CATALOG
    clock["now"] += catalog.CACHE_TTL_SECONDS + 1
    assert catalog.current_snapshot() == ()


@pytest.mark.unit
def test_cold_snapshot_reads_empty() -> None:
    assert catalog.list_models(enabled_only=False) == []
    assert catalog.get_model("gemini", LITE) is None
    assert catalog.models_for_capability(ModelCapability.FAST_CHAT) == []


@pytest.mark.unit
def test_models_for_capability_prefers_settings_model() -> None:
    catalog.put_snapshot(MODEL_CATALOG)
    matches = catalog.models_for_capability(
        ModelCapability.FAST_CHAT,
        prefer_provider="gemini",
        prefer_model="gemini-3.6-flash",
    )
    assert matches[0].model_name == "gemini-3.6-flash"
    assert len(matches) == 2


@pytest.mark.unit
def test_embedding_has_no_candidate() -> None:
    catalog.put_snapshot(MODEL_CATALOG)
    assert catalog.models_for_capability(ModelCapability.EMBEDDING) == []


@pytest.mark.unit
def test_list_models_enabled_only_filters() -> None:
    disabled = catalog.build_snapshot([_row(model_enabled=False)])
    catalog.put_snapshot(disabled)
    assert catalog.list_models() == []
    assert len(catalog.list_models(enabled_only=False)) == 1


@pytest.mark.integration
async def test_ensure_loaded_reads_seeded_rows(seeded_catalog: None) -> None:
    async with SessionLocal() as session:
        specs = await catalog.ensure_loaded(session)
    lite = catalog.get_model("gemini", LITE)
    assert lite is not None
    assert lite.enabled is True
    assert lite.input_cost_per_1m == 0.10
    assert ModelCapability.FAST_CHAT in lite.capabilities
    assert specs == catalog.current_snapshot()


@pytest.mark.integration
async def test_disabled_provider_disables_models(seeded_catalog: None) -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(ModelProvider).where(ModelProvider.name == "gemini")
        )
        result.scalar_one().enabled = False
        await session.commit()
    catalog.invalidate()
    async with SessionLocal() as session:
        await catalog.ensure_loaded(session)
    assert catalog.models_for_capability(ModelCapability.FAST_CHAT) == []
    assert catalog.list_models(enabled_only=False)  # rows still in the snapshot
```

- [ ] **Step 2: Create the shared fixture**

```python
# backend/tests/llm/conftest.py
"""Shared fixtures for DB-catalog llm tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from app.core.db import SessionLocal
from app.modules.llm import catalog
from app.modules.llm.seed import seed_llm_models
from sqlalchemy import text


async def _reset_catalog_rows() -> None:
    async with SessionLocal() as session:
        await session.execute(text("DELETE FROM model_configurations"))
        await session.execute(text("DELETE FROM model_providers"))
        await session.commit()


@pytest.fixture
async def seeded_catalog() -> AsyncIterator[None]:
    """Pristine seeded catalog rows + cold snapshot; restores both afterwards."""
    await _reset_catalog_rows()
    await seed_llm_models()
    catalog.invalidate()
    yield
    await _reset_catalog_rows()
    await seed_llm_models()
    catalog.invalidate()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/llm/test_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.modules.llm.catalog'`

- [ ] **Step 4: Add the adapter registry**

In `backend/app/modules/llm/providers/__init__.py`, add below the imports (leave `build_provider_for` alone for now — Task 3 removes it):

```python
# Provider names with a registered adapter factory. A DB catalog row for any
# other provider is unserveable and is skipped by the runtime catalog.
KNOWN_ADAPTERS: frozenset[str] = frozenset({"gemini"})


def has_adapter(provider: str) -> bool:
    """True when an adapter factory exists for this provider name."""
    return provider in KNOWN_ADAPTERS
```

- [ ] **Step 5: Add the repository read**

In `backend/app/modules/llm/repository.py`, add next to the other dataclasses:

```python
@dataclass(frozen=True, slots=True)
class CatalogRow:
    """One joined provider+model row for the runtime catalog snapshot."""

    provider_name: str
    provider_enabled: bool
    model_name: str
    model_enabled: bool
    capabilities: list[str]
    context_window: int
    supports_tools: bool
    supports_structured: bool
    supports_streaming: bool
    input_cost_per_1m: float
    output_cost_per_1m: float
```

And to `LlmRepository`:

```python
    async def list_catalog_rows(self) -> list[CatalogRow]:
        """All catalog rows, deterministically ordered (provider, model)."""
        result = await self._session.execute(
            select(ModelConfiguration, ModelProvider)
            .join(ModelProvider, ModelConfiguration.provider_id == ModelProvider.id)
            .order_by(ModelProvider.name, ModelConfiguration.model_name)
        )
        return [
            CatalogRow(
                provider_name=provider.name,
                provider_enabled=provider.enabled,
                model_name=model.model_name,
                model_enabled=model.enabled,
                capabilities=[str(c) for c in model.capabilities],
                context_window=model.context_window,
                supports_tools=model.supports_tools,
                supports_structured=model.supports_structured,
                supports_streaming=model.supports_streaming,
                input_cost_per_1m=model.input_cost_per_1m,
                output_cost_per_1m=model.output_cost_per_1m,
            )
            for model, provider in result.all()
        ]
```

- [ ] **Step 6: Implement `catalog.py`**

```python
# backend/app/modules/llm/catalog.py
"""DB-backed effective model catalog: async snapshot refresh, sync reads.

Same per-process TTL pattern as modules/runtime_config/cache.py: writers
call invalidate() so the writing process sees changes immediately; other
processes (arq worker, other API workers) converge within the TTL. Sync
readers (ModelRouter.candidates) see the last loaded snapshot; LlmService
entry points await ensure_loaded() first, so a cold cache is only ever
observable as an empty catalog — which surfaces as NoCandidateModelError,
never a crash. Upgrade path if TTL lag ever matters: Redis pub/sub calling
invalidate(); this module is the single seam for that.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from time import monotonic
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.llm.capabilities import ModelCapability
from app.modules.llm.providers import has_adapter
from app.modules.llm.registry import ModelSpec
from app.modules.llm.repository import CatalogRow, LlmRepository

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30.0

_state: dict[str, Any] = {"snapshot": None, "expires_at": 0.0}


def current_snapshot() -> tuple[ModelSpec, ...]:
    """Sync view of the effective catalog; empty when cold or expired."""
    snapshot = _state["snapshot"]
    if snapshot is None or monotonic() >= float(_state["expires_at"]):
        return ()
    return tuple(snapshot)


def put_snapshot(specs: Sequence[ModelSpec]) -> None:
    """Cache a snapshot for the TTL window (also a test hook)."""
    _state["snapshot"] = tuple(specs)
    _state["expires_at"] = monotonic() + CACHE_TTL_SECONDS


def invalidate() -> None:
    """Drop the snapshot now (every catalog write calls this; test hook)."""
    _state["snapshot"] = None
    _state["expires_at"] = 0.0


async def ensure_loaded(session: AsyncSession) -> tuple[ModelSpec, ...]:
    """Return a warm snapshot, loading from the DB when cold or expired."""
    snapshot = _state["snapshot"]
    if snapshot is not None and monotonic() < float(_state["expires_at"]):
        return tuple(snapshot)
    rows = await LlmRepository(session).list_catalog_rows()
    specs = build_snapshot(rows)
    put_snapshot(specs)
    return specs


def build_snapshot(rows: Sequence[CatalogRow]) -> tuple[ModelSpec, ...]:
    """Convert rows to specs, skipping unserveable rows (public for tests)."""
    return tuple(spec for row in rows if (spec := _to_spec(row)) is not None)


def _to_spec(row: CatalogRow) -> ModelSpec | None:
    """Row → ModelSpec; skip-with-warning when no adapter can serve it."""
    if not has_adapter(row.provider_name):
        logger.warning(
            "skipping catalog model with no adapter",
            extra={"provider": row.provider_name, "model": row.model_name},
        )
        return None
    return ModelSpec(
        provider=row.provider_name,
        model_name=row.model_name,
        capabilities=_parse_capabilities(row),
        context_window=row.context_window,
        supports_tools=row.supports_tools,
        supports_structured=row.supports_structured,
        supports_streaming=row.supports_streaming,
        enabled=row.provider_enabled and row.model_enabled,
        input_cost_per_1m=row.input_cost_per_1m,
        output_cost_per_1m=row.output_cost_per_1m,
    )


def _parse_capabilities(row: CatalogRow) -> frozenset[ModelCapability]:
    """Tolerate-and-warn on unknown capability strings (forward compat)."""
    parsed: set[ModelCapability] = set()
    for value in row.capabilities:
        try:
            parsed.add(ModelCapability(value))
        except ValueError:
            logger.warning(
                "ignoring unknown capability on catalog model",
                extra={"model": row.model_name, "capability": value},
            )
    return frozenset(parsed)


def list_models(*, enabled_only: bool = True) -> list[ModelSpec]:
    """Snapshot entries (effective-enabled only by default)."""
    snapshot = current_snapshot()
    if enabled_only:
        return [m for m in snapshot if m.enabled]
    return list(snapshot)


def get_model(provider: str, model_name: str) -> ModelSpec | None:
    """Lookup a snapshot entry."""
    for model in current_snapshot():
        if model.provider == provider and model.model_name == model_name:
            return model
    return None


def models_for_capability(
    capability: ModelCapability,
    *,
    prefer_provider: str | None = None,
    prefer_model: str | None = None,
) -> list[ModelSpec]:
    """Ordered enabled candidates for capability (preferred model first)."""
    matches = [m for m in current_snapshot() if m.enabled and capability in m.capabilities]
    if prefer_model and prefer_provider:
        preferred = [
            m for m in matches if m.provider == prefer_provider and m.model_name == prefer_model
        ]
        rest = [m for m in matches if m not in preferred]
        return preferred + rest
    if prefer_provider:
        preferred = [m for m in matches if m.provider == prefer_provider]
        rest = [m for m in matches if m not in preferred]
        return preferred + rest
    return matches
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/llm/test_catalog.py -v`
Expected: PASS (10 tests)

- [ ] **Step 8: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add DB-backed model catalog snapshot with TTL cache\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 3: Rewire the read path (router, service, chat boundary) onto the snapshot

**Files:**
- Modify: `backend/app/modules/llm/registry.py` (remove query functions; seed-only docstring)
- Modify: `backend/app/modules/llm/model_router.py` (`candidates`, `build`)
- Modify: `backend/app/modules/llm/providers/__init__.py` (remove `build_provider_for`)
- Modify: `backend/app/modules/llm/service.py` (`ensure_ready`, async `list_public_models`)
- Modify: `backend/app/modules/llm/chat_service.py` (both `ensure_enabled` call sites)
- Modify: `backend/app/modules/llm/router.py` (await `list_public_models`)
- Modify: `backend/tests/conftest.py` (autouse snapshot-warming fixture)
- Modify: `backend/tests/llm/test_registry.py` (shrink to seed-defaults tests)
- Modify: `backend/tests/llm/test_model_router.py` (`make_settings`)
- Modify: `backend/tests/llm/test_llm_telemetry.py` (import `get_model` from `catalog`)
- Test: `backend/tests/llm/test_llm_service_ready.py`

**Interfaces:**
- Consumes: all Task 2 `catalog` functions; `has_adapter`; `build_provider(ProviderBuildContext)`.
- Produces (used by Tasks 4, 7): `async LlmService.ensure_ready() -> None` (raises `LlmDisabledError` when off, `LlmConfigError` when misconfigured, `NoCandidateModelError` when no enabled catalog model); `async LlmService.list_public_models() -> ModelListResponse`; `registry.py` exports only `ModelSpec` and `MODEL_CATALOG`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/llm/test_llm_service_ready.py
"""ensure_ready: catalog emptiness degrades like llm-disabled."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from app.modules.llm import catalog
from app.modules.llm.exceptions import LlmDisabledError, NoCandidateModelError
from app.modules.llm.service import LlmService

from tests.factories import make_settings


@pytest.mark.unit
async def test_ensure_ready_passes_with_enabled_catalog() -> None:
    service = LlmService(AsyncMock(), make_settings(llm_enabled=True, gemini_api_key="k"))
    await service.ensure_ready()  # autouse fixture pre-warmed the snapshot


@pytest.mark.unit
async def test_ensure_ready_raises_when_llm_disabled() -> None:
    service = LlmService(AsyncMock(), make_settings(llm_enabled=False))
    with pytest.raises(LlmDisabledError):
        await service.ensure_ready()


@pytest.mark.unit
async def test_ensure_ready_raises_when_all_models_disabled() -> None:
    catalog.put_snapshot(())
    service = LlmService(AsyncMock(), make_settings(llm_enabled=True, gemini_api_key="k"))
    with pytest.raises(NoCandidateModelError):
        await service.ensure_ready()
```

- [ ] **Step 2: Add the autouse snapshot-warming fixture**

In `backend/tests/conftest.py`, add two imports to the existing top-of-file import block (both are env-safe — they must NOT import app code, which is why the app imports below live inside the fixture body, after the module-top env pinning has run):

```python
from collections.abc import Iterator

import pytest
```

Then append after `pytest_configure`:

```python
@pytest.fixture(autouse=True)
def _warm_model_catalog() -> Iterator[None]:
    """Pre-warm the model-catalog snapshot with the seed defaults.

    The runtime catalog is DB-backed; warming it from MODEL_CATALOG keeps
    unit tests hermetic and gives every existing test exactly the catalog it
    saw when the registry was static. DB-facing catalog tests call
    catalog.invalidate() themselves (see tests/llm/conftest.py).
    """
    from app.modules.llm import catalog
    from app.modules.llm.registry import MODEL_CATALOG

    catalog.put_snapshot(MODEL_CATALOG)
    yield
    catalog.invalidate()
```

- [ ] **Step 3: Run the new test to verify it fails**

Run: `uv run pytest tests/llm/test_llm_service_ready.py -v`
Expected: FAIL — `AttributeError: 'LlmService' object has no attribute 'ensure_ready'`

- [ ] **Step 4: Slim `registry.py` to seed-only defaults**

Replace the module docstring and delete `list_models`, `get_model`, and `models_for_capability` (everything from line 70 down). Resulting file keeps only `ModelSpec` and `MODEL_CATALOG`:

```python
"""Seed-only model catalog defaults.

The DB (model_providers / model_configurations) is the runtime source of
truth — see modules/llm/catalog.py. This tuple only defines what startup
seeding inserts when rows are missing; it never overwrites admin edits.
"""
```

- [ ] **Step 5: Rewire `model_router.py`**

Replace the imports of `build_provider_for` and the registry query with:

```python
from app.modules.llm import catalog
from app.modules.llm.providers import ProviderBuildContext, build_provider
from app.modules.llm.registry import ModelSpec
```

Replace `candidates` and `build`:

```python
    def candidates(self, capability: ModelCapability) -> list[ModelSpec]:
        """Enabled snapshot models for capability, preferred settings model first."""
        return catalog.models_for_capability(
            capability,
            prefer_provider=self._settings.llm.provider,
            prefer_model=self._settings.llm.model,
        )

    def build(self, model: ModelSpec) -> GeminiProvider:
        """Instantiate adapter for a catalog model."""
        return build_provider(ProviderBuildContext(settings=self._settings, model=model))
```

- [ ] **Step 6: Remove `build_provider_for`**

In `backend/app/modules/llm/providers/__init__.py`, delete the `build_provider_for` function and the now-unused `get_model` import (`from app.modules.llm.registry import ModelSpec` stays — `ProviderBuildContext` uses it). Verify nothing else references it: `grep -rn "build_provider_for" backend/` must return nothing.

- [ ] **Step 7: Rewire `service.py`**

Add `from app.modules.llm import catalog` and drop `list_models` from the registry import (keep `ModelSpec`). Store the session in `__init__` (first line of the body): `self._session = session`. Add after `ensure_enabled`:

```python
    async def ensure_ready(self) -> None:
        """Raise if LLM is off, misconfigured, or no catalog model is enabled."""
        self.ensure_enabled()
        await catalog.ensure_loaded(self._session)
        if not catalog.list_models(enabled_only=True):
            raise NoCandidateModelError("no enabled models in catalog")
```

Replace every `self.ensure_enabled()` call inside the six entry points (`generate_text`, `call_tools`, `stream_tools`, `generate_structured_with_model`, `stream_text`, `create_embeddings`) with `await self.ensure_ready()`. Make `list_public_models` async and snapshot-backed:

```python
    async def list_public_models(self) -> ModelListResponse:
        """Catalog for GET /api/llm/models (no secrets)."""
        await catalog.ensure_loaded(self._session)
        models = [
            ModelRead(
                provider=m.provider,
                model_name=m.model_name,
                capabilities=sorted(c.value for c in m.capabilities),
                context_window=m.context_window,
                supports_tools=m.supports_tools,
                supports_structured=m.supports_structured,
                supports_streaming=m.supports_streaming,
                enabled=m.enabled,
            )
            for m in catalog.list_models(enabled_only=False)
        ]
        return ModelListResponse(
            llm_enabled=self._settings.llm.enabled,
            default_provider=self._settings.llm.provider,
            default_model=self._settings.llm.model,
            models=models,
        )
```

In `backend/app/modules/llm/router.py::list_models`, change the return to `return await service.list_public_models()`.

- [ ] **Step 8: Move the chat boundary to `ensure_ready`**

In `backend/app/modules/llm/chat_service.py`, replace both `self._llm.ensure_enabled()` lines (in `stream_chat` and `stream_confirm`) with `await self._llm.ensure_ready()`. They stay in their current pre-`try` position — that placement is what makes an all-disabled catalog degrade exactly like `llm_enabled=false` (both raise before any SSE event; both map to 503).

- [ ] **Step 9: Update the existing tests**

Replace `backend/tests/llm/test_registry.py` entirely:

```python
"""Seed-only defaults: the code catalog defines what seeding inserts."""

from __future__ import annotations

import pytest
from app.modules.llm.capabilities import ModelCapability
from app.modules.llm.registry import MODEL_CATALOG


@pytest.mark.unit
def test_seed_defaults_include_flash_lite() -> None:
    lite = next(m for m in MODEL_CATALOG if m.model_name == "gemini-3.5-flash-lite")
    assert ModelCapability.FAST_CHAT in lite.capabilities
    assert lite.supports_tools is True
    assert lite.supports_structured is True
    assert lite.input_cost_per_1m > 0
    assert lite.output_cost_per_1m > 0


@pytest.mark.unit
def test_seed_defaults_are_enabled_with_context_windows() -> None:
    assert all(m.enabled for m in MODEL_CATALOG)
    assert all(m.context_window > 0 for m in MODEL_CATALOG)
```

In `backend/tests/llm/test_model_router.py`, replace the `_settings` helper (and its `Settings` import) with:

```python
from tests.factories import make_settings


def _settings() -> Settings:
    return make_settings(
        llm_enabled=True,
        llm_provider="gemini",
        llm_model="gemini-3.5-flash-lite",
        gemini_api_key="test-key",
    )
```

(keep `from app.core.config import Settings` for the return annotation). All router tests now read the autouse-warmed snapshot — no other changes.

In `backend/tests/llm/test_llm_telemetry.py`, change the `get_model` import from `app.modules.llm.registry` to `app.modules.llm.catalog` (the autouse fixture makes it resolve).

- [ ] **Step 10: Run the full suite to verify everything passes**

Run: `uv run pytest -m "unit or integration" -v`
Expected: PASS, including all pre-existing llm/orchestration/chat tests (the autouse fixture keeps them on the same catalog contents as before).

- [ ] **Step 11: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: serve model catalog from DB snapshot in router, service, and chat\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 4: Prove the cost path uses DB pricing (test-only)

**Files:**
- Test: `backend/tests/llm/test_catalog_cost.py`

**Interfaces:**
- Consumes: Task 2 `catalog.ensure_loaded` / `get_model` / `invalidate`; `seeded_catalog` fixture; existing `LlmTelemetry`, `TelemetryContext`, `NoOpTracer` (`modules/llm/telemetry.py`), `Usage` (`modules/llm/types.py`), `CostRecord` (`modules/llm/models.py`).
- Produces: regression proof that `cost_records.unit_cost_in/out` and `total_cost` come from the DB row used for the call (spec "Cost path audit").

- [ ] **Step 1: Write the test**

```python
# backend/tests/llm/test_catalog_cost.py
"""Repricing a model in the DB drives unit costs on new cost records."""

from __future__ import annotations

import pytest
from app.core.db import SessionLocal
from app.modules.llm import catalog
from app.modules.llm.models import CostRecord, ModelConfiguration
from app.modules.llm.telemetry import LlmTelemetry, NoOpTracer, TelemetryContext
from app.modules.llm.types import Usage
from sqlalchemy import select

LITE = "gemini-3.5-flash-lite"


@pytest.mark.integration
async def test_repriced_model_drives_cost_records(seeded_catalog: None) -> None:
    # Reprice directly in the DB (what the admin API does in Task 5).
    async with SessionLocal() as session:
        result = await session.execute(
            select(ModelConfiguration).where(ModelConfiguration.model_name == LITE)
        )
        row = result.scalar_one()
        row.input_cost_per_1m = 1.0
        row.output_cost_per_1m = 2.0
        await session.commit()
    catalog.invalidate()

    async with SessionLocal() as session:
        await catalog.ensure_loaded(session)
        model = catalog.get_model("gemini", LITE)
        assert model is not None
        assert model.input_cost_per_1m == 1.0

        telemetry = LlmTelemetry(session, NoOpTracer())
        context = TelemetryContext(task="cost-test", model=model, fallback_used=False)

        async def _call() -> tuple[str, Usage]:
            return "ok", Usage(1_000_000, 1_000_000)

        await telemetry.record_call(context, _call)

        result = await session.execute(
            select(CostRecord).order_by(CostRecord.created_at.desc()).limit(1)
        )
        record = result.scalar_one()
        assert record.unit_cost_in == 1.0
        assert record.unit_cost_out == 2.0
        assert record.total_cost == pytest.approx(3.0)
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `uv run pytest tests/llm/test_catalog_cost.py -v`
Expected: PASS immediately — the code change already happened in Task 3 (`ModelSpec` provenance). If it fails, the read path is not actually snapshot-backed; fix Task 3, don't touch telemetry.

- [ ] **Step 3: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'test: prove cost records use DB catalog pricing\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 5: Admin catalog service (list / patch / create) with typed errors

**Files:**
- Modify: `backend/app/modules/llm/exceptions.py` (4 new exceptions)
- Modify: `backend/app/modules/llm/schemas.py` (admin DTOs)
- Modify: `backend/app/modules/llm/repository.py` (provider/model lookups)
- Create: `backend/app/modules/llm/catalog_service.py`
- Test: `backend/tests/llm/test_catalog_admin_service.py`

**Interfaces:**
- Consumes: Task 1 columns; Task 2 `catalog.invalidate`, `has_adapter`; existing `LlmRepository.upsert_provider`.
- Produces (used by Task 6):
  - Exceptions: `CatalogProviderNotFoundError`, `CatalogModelNotFoundError`, `AdapterNotRegisteredError`, `DuplicateCatalogModelError` (all subclass `LlmError`)
  - Schemas: `ProviderPatch(enabled: bool)`; `ModelPatch(enabled: bool | None, input_cost_per_1m: float | None ge 0, output_cost_per_1m: float | None ge 0)`; `ModelCreate(provider, model_name, capabilities: list[ModelCapability], context_window ge 1, supports_tools=True, supports_structured=True, supports_streaming=True, enabled=True, input_cost_per_1m=0.0 ge 0, output_cost_per_1m=0.0 ge 0)`; `ModelAdminRead` (model_name, enabled, effective_enabled, capabilities, context_window, supports_*, prices, updated_at); `ProviderAdminRead(name, enabled, has_adapter, models)`; `CatalogAdminResponse(providers)`
  - `ModelCatalogAdminService(session)` with `async list_catalog() -> CatalogAdminResponse`, `async set_provider_enabled(name, *, enabled) -> ProviderAdminRead`, `async patch_model(provider_name, model_name, patch) -> ModelAdminRead`, `async create_model(data) -> ModelAdminRead`
  - Repository: `get_provider_by_name(name)`, `get_model_config(provider_id, model_name)`, `list_providers()`, `list_model_configs()`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/llm/test_catalog_admin_service.py
"""ModelCatalogAdminService: list/patch/create with snapshot invalidation."""

from __future__ import annotations

import pytest
from app.core.db import SessionLocal
from app.modules.llm import catalog
from app.modules.llm.capabilities import ModelCapability
from app.modules.llm.catalog_service import ModelCatalogAdminService
from app.modules.llm.exceptions import (
    AdapterNotRegisteredError,
    CatalogModelNotFoundError,
    CatalogProviderNotFoundError,
    DuplicateCatalogModelError,
)
from app.modules.llm.schemas import ModelCreate, ModelPatch
from pydantic import ValidationError

LITE = "gemini-3.5-flash-lite"


def _create(*, provider: str = "gemini", model_name: str = "gemini-x") -> ModelCreate:
    return ModelCreate(
        provider=provider,
        model_name=model_name,
        capabilities=[ModelCapability.FAST_CHAT],
        context_window=100_000,
        input_cost_per_1m=0.2,
        output_cost_per_1m=0.8,
    )


@pytest.mark.integration
async def test_list_catalog_shows_seeded_rows(seeded_catalog: None) -> None:
    async with SessionLocal() as session:
        listing = await ModelCatalogAdminService(session).list_catalog()
    gemini = next(p for p in listing.providers if p.name == "gemini")
    assert gemini.has_adapter is True
    lite = next(m for m in gemini.models if m.model_name == LITE)
    assert lite.effective_enabled is True
    assert lite.input_cost_per_1m == 0.10


@pytest.mark.integration
async def test_disable_provider_cascades(seeded_catalog: None) -> None:
    async with SessionLocal() as session:
        provider = await ModelCatalogAdminService(session).set_provider_enabled(
            "gemini", enabled=False
        )
        await session.commit()
    assert all(m.effective_enabled is False for m in provider.models)
    async with SessionLocal() as session:
        await catalog.ensure_loaded(session)
    assert catalog.models_for_capability(ModelCapability.FAST_CHAT) == []


@pytest.mark.integration
async def test_patch_model_reprices_and_disables(seeded_catalog: None) -> None:
    async with SessionLocal() as session:
        updated = await ModelCatalogAdminService(session).patch_model(
            "gemini", LITE, ModelPatch(enabled=False, input_cost_per_1m=1.5)
        )
        await session.commit()
    assert updated.enabled is False
    assert updated.input_cost_per_1m == 1.5
    assert updated.output_cost_per_1m == 0.40  # untouched field stays
    async with SessionLocal() as session:
        await catalog.ensure_loaded(session)
    spec = catalog.get_model("gemini", LITE)
    assert spec is not None
    assert spec.enabled is False
    assert spec.input_cost_per_1m == 1.5


@pytest.mark.integration
async def test_unknown_targets_raise(seeded_catalog: None) -> None:
    async with SessionLocal() as session:
        service = ModelCatalogAdminService(session)
        with pytest.raises(CatalogProviderNotFoundError):
            await service.patch_model("nope", LITE, ModelPatch(enabled=True))
        with pytest.raises(CatalogModelNotFoundError):
            await service.patch_model("gemini", "nope", ModelPatch(enabled=True))
        with pytest.raises(CatalogProviderNotFoundError):
            await service.set_provider_enabled("nope", enabled=False)


@pytest.mark.integration
async def test_create_model_validates_adapter_and_duplicates(seeded_catalog: None) -> None:
    async with SessionLocal() as session:
        service = ModelCatalogAdminService(session)
        with pytest.raises(AdapterNotRegisteredError):
            await service.create_model(_create(provider="openai"))
        with pytest.raises(DuplicateCatalogModelError):
            await service.create_model(_create(model_name=LITE))
        created = await service.create_model(_create(model_name="gemini-3.7-pro"))
        await session.commit()
    assert created.effective_enabled is True
    async with SessionLocal() as session:
        await catalog.ensure_loaded(session)
    assert catalog.get_model("gemini", "gemini-3.7-pro") is not None


@pytest.mark.unit
def test_model_create_rejects_unknown_capability() -> None:
    with pytest.raises(ValidationError):
        ModelCreate.model_validate(
            {
                "provider": "gemini",
                "model_name": "m",
                "capabilities": ["NOT_A_CAPABILITY"],
                "context_window": 1,
            }
        )


@pytest.mark.unit
def test_model_patch_rejects_negative_price() -> None:
    with pytest.raises(ValidationError):
        ModelPatch(input_cost_per_1m=-0.1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/llm/test_catalog_admin_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.modules.llm.catalog_service'`

- [ ] **Step 3: Add exceptions**

Append to `backend/app/modules/llm/exceptions.py`:

```python
class CatalogProviderNotFoundError(LlmError):
    """Admin referenced a provider with no catalog row."""


class CatalogModelNotFoundError(LlmError):
    """Admin referenced a model with no catalog row."""


class AdapterNotRegisteredError(LlmError):
    """Catalog write names a provider with no adapter factory."""


class DuplicateCatalogModelError(LlmError):
    """A catalog row already exists for this provider + model_name."""
```

- [ ] **Step 4: Add admin schemas**

Append to `backend/app/modules/llm/schemas.py` (add `from app.modules.llm.capabilities import ModelCapability` to the imports; `datetime` is already imported):

```python
class ProviderPatch(BaseModel):
    """PATCH /api/admin/llm/catalog/providers/{provider} body."""

    enabled: bool


class ModelPatch(BaseModel):
    """PATCH model body — only supplied fields change."""

    enabled: bool | None = None
    input_cost_per_1m: float | None = Field(default=None, ge=0)
    output_cost_per_1m: float | None = Field(default=None, ge=0)


class ModelCreate(BaseModel):
    """POST /api/admin/llm/catalog/models body."""

    provider: str = Field(min_length=1, max_length=64)
    model_name: str = Field(min_length=1, max_length=128)
    capabilities: list[ModelCapability]
    context_window: int = Field(ge=1)
    supports_tools: bool = True
    supports_structured: bool = True
    supports_streaming: bool = True
    enabled: bool = True
    input_cost_per_1m: float = Field(default=0.0, ge=0)
    output_cost_per_1m: float = Field(default=0.0, ge=0)


class ModelAdminRead(BaseModel):
    """Admin view of one catalog model (includes pricing)."""

    model_name: str
    enabled: bool
    effective_enabled: bool
    capabilities: list[str]
    context_window: int
    supports_tools: bool
    supports_structured: bool
    supports_streaming: bool
    input_cost_per_1m: float
    output_cost_per_1m: float
    updated_at: datetime


class ProviderAdminRead(BaseModel):
    """Admin view of one provider with its models."""

    name: str
    enabled: bool
    has_adapter: bool
    models: list[ModelAdminRead] = Field(default_factory=list)


class CatalogAdminResponse(BaseModel):
    """GET /api/admin/llm/catalog payload."""

    providers: list[ProviderAdminRead] = Field(default_factory=list)
```

- [ ] **Step 5: Add repository lookups**

Append to `LlmRepository` in `backend/app/modules/llm/repository.py`:

```python
    async def list_providers(self) -> list[ModelProvider]:
        """All provider rows ordered by name."""
        result = await self._session.execute(select(ModelProvider).order_by(ModelProvider.name))
        return list(result.scalars().all())

    async def list_model_configs(self) -> list[ModelConfiguration]:
        """All model rows ordered by name."""
        result = await self._session.execute(
            select(ModelConfiguration).order_by(ModelConfiguration.model_name)
        )
        return list(result.scalars().all())

    async def get_provider_by_name(self, name: str) -> ModelProvider | None:
        """Provider row by unique name."""
        result = await self._session.execute(
            select(ModelProvider).where(ModelProvider.name == name)
        )
        return result.scalar_one_or_none()

    async def get_model_config(
        self,
        provider_id: uuid.UUID,
        model_name: str,
    ) -> ModelConfiguration | None:
        """Model row by (provider_id, model_name)."""
        result = await self._session.execute(
            select(ModelConfiguration).where(
                ModelConfiguration.provider_id == provider_id,
                ModelConfiguration.model_name == model_name,
            )
        )
        return result.scalar_one_or_none()
```

- [ ] **Step 6: Implement `catalog_service.py`**

```python
# backend/app/modules/llm/catalog_service.py
"""Admin read/write operations on the DB model catalog (llm module only)."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.llm import catalog
from app.modules.llm.exceptions import (
    AdapterNotRegisteredError,
    CatalogModelNotFoundError,
    CatalogProviderNotFoundError,
    DuplicateCatalogModelError,
)
from app.modules.llm.models import ModelConfiguration, ModelProvider
from app.modules.llm.providers import has_adapter
from app.modules.llm.repository import LlmRepository
from app.modules.llm.schemas import (
    CatalogAdminResponse,
    ModelAdminRead,
    ModelCreate,
    ModelPatch,
    ProviderAdminRead,
)

logger = logging.getLogger(__name__)


class ModelCatalogAdminService:
    """Backoffice catalog management; every write invalidates the snapshot."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = LlmRepository(session)

    async def list_catalog(self) -> CatalogAdminResponse:
        """All providers + models, including unserveable (no-adapter) rows."""
        providers = await self._repo.list_providers()
        by_provider: dict[uuid.UUID, list[ModelConfiguration]] = {}
        for model in await self._repo.list_model_configs():
            by_provider.setdefault(model.provider_id, []).append(model)
        return CatalogAdminResponse(
            providers=[self._provider_read(p, by_provider.get(p.id, [])) for p in providers]
        )

    async def set_provider_enabled(self, name: str, *, enabled: bool) -> ProviderAdminRead:
        """Flip a provider; effective enablement of its models follows."""
        provider = await self._repo.get_provider_by_name(name)
        if provider is None:
            raise CatalogProviderNotFoundError(name)
        provider.enabled = enabled
        await self._session.flush()
        await self._session.refresh(provider)
        catalog.invalidate()
        logger.info("catalog provider updated", extra={"provider": name, "enabled": enabled})
        models = [
            m for m in await self._repo.list_model_configs() if m.provider_id == provider.id
        ]
        return self._provider_read(provider, models)

    async def patch_model(
        self,
        provider_name: str,
        model_name: str,
        patch: ModelPatch,
    ) -> ModelAdminRead:
        """Partial update: enabled flag and/or unit prices."""
        provider = await self._repo.get_provider_by_name(provider_name)
        if provider is None:
            raise CatalogProviderNotFoundError(provider_name)
        row = await self._repo.get_model_config(provider.id, model_name)
        if row is None:
            raise CatalogModelNotFoundError(f"{provider_name}/{model_name}")
        updates = patch.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in updates.items():
            setattr(row, field, value)
        await self._session.flush()
        await self._session.refresh(row)
        catalog.invalidate()
        logger.info(
            "catalog model updated",
            extra={"provider": provider_name, "model": model_name, "fields": sorted(updates)},
        )
        return self._model_read(provider, row)

    async def create_model(self, data: ModelCreate) -> ModelAdminRead:
        """Add a catalog row for a provider with a registered adapter."""
        if not has_adapter(data.provider):
            raise AdapterNotRegisteredError(data.provider)
        provider = await self._repo.upsert_provider(data.provider)
        if await self._repo.get_model_config(provider.id, data.model_name) is not None:
            raise DuplicateCatalogModelError(f"{data.provider}/{data.model_name}")
        row = ModelConfiguration(
            provider_id=provider.id,
            model_name=data.model_name,
            capabilities=[c.value for c in data.capabilities],
            context_window=data.context_window,
            supports_tools=data.supports_tools,
            supports_structured=data.supports_structured,
            supports_streaming=data.supports_streaming,
            enabled=data.enabled,
            input_cost_per_1m=data.input_cost_per_1m,
            output_cost_per_1m=data.output_cost_per_1m,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        catalog.invalidate()
        logger.info(
            "catalog model created",
            extra={"provider": data.provider, "model": data.model_name},
        )
        return self._model_read(provider, row)

    def _provider_read(
        self,
        provider: ModelProvider,
        models: list[ModelConfiguration],
    ) -> ProviderAdminRead:
        return ProviderAdminRead(
            name=provider.name,
            enabled=provider.enabled,
            has_adapter=has_adapter(provider.name),
            models=[self._model_read(provider, m) for m in models],
        )

    def _model_read(self, provider: ModelProvider, row: ModelConfiguration) -> ModelAdminRead:
        return ModelAdminRead(
            model_name=row.model_name,
            enabled=row.enabled,
            effective_enabled=row.enabled and provider.enabled and has_adapter(provider.name),
            capabilities=sorted(str(c) for c in row.capabilities),
            context_window=row.context_window,
            supports_tools=row.supports_tools,
            supports_structured=row.supports_structured,
            supports_streaming=row.supports_streaming,
            input_cost_per_1m=row.input_cost_per_1m,
            output_cost_per_1m=row.output_cost_per_1m,
            updated_at=row.updated_at,
        )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/llm/test_catalog_admin_service.py -v`
Expected: PASS (7 tests)

- [ ] **Step 8: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add ModelCatalogAdminService for catalog list/patch/create\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 6: Admin API router + exception mappings

**Files:**
- Create: `backend/app/modules/llm/admin_router.py`
- Modify: `backend/app/core/exceptions.py` (4 new handlers)
- Modify: `backend/app/main.py` (register router)
- Test: `backend/tests/llm/test_catalog_admin_api.py`

**Interfaces:**
- Consumes: Task 5 service, schemas, exceptions; `require_admin` / `get_db` (`core/deps.py`).
- Produces: `GET /api/admin/llm/catalog`, `PATCH /api/admin/llm/catalog/providers/{provider}`, `PATCH /api/admin/llm/catalog/models/{provider}/{model_name}`, `POST /api/admin/llm/catalog/models` (201). Error mapping: `CatalogProviderNotFoundError`/`CatalogModelNotFoundError` → 404, `AdapterNotRegisteredError` → 422, `DuplicateCatalogModelError` → 409.

- [ ] **Step 1: Write the failing tests**

The client/admin fixtures copy the established pattern from `backend/tests/runtime_config/test_admin_api.py` (dotted host for cookies, `get_db` override against the test DB, direct `User` row + JWT cookie).

```python
# backend/tests/llm/test_catalog_admin_api.py
"""Admin catalog API: authz matrix + typed errors (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from uuid import UUID

import pytest
from app.core.config import get_settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.users.models import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.dbcleanup import clear_users

# http.cookiejar drops cookies scoped to a single-label host (see test_auth_api.py).
_HOST = "test.local"
BASE = "/api/admin/llm/catalog"
LITE = "gemini-3.5-flash-lite"


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
async def client(seeded_catalog: None) -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await clear_users(conn)
    app.dependency_overrides[get_db] = _make_db_override(session_factory)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=f"http://{_HOST}") as http:
        yield http
    app.dependency_overrides.clear()
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
    user_id = await _create_user("catalog-admin", is_admin=True)
    _login(client, user_id, "catalog-admin")
    return client


@pytest.mark.integration
async def test_anonymous_gets_401(client: AsyncClient) -> None:
    assert (await client.get(BASE)).status_code == 401


@pytest.mark.integration
async def test_non_admin_gets_403(client: AsyncClient) -> None:
    user_id = await _create_user("catalog-reader", is_admin=False)
    _login(client, user_id, "catalog-reader")
    assert (await client.get(BASE)).status_code == 403
    patch = await client.patch(f"{BASE}/models/gemini/{LITE}", json={"enabled": False})
    assert patch.status_code == 403


@pytest.mark.integration
async def test_admin_lists_catalog_with_pricing(admin_client: AsyncClient) -> None:
    response = await admin_client.get(BASE)
    assert response.status_code == 200
    gemini = next(p for p in response.json()["providers"] if p["name"] == "gemini")
    assert gemini["has_adapter"] is True
    lite = next(m for m in gemini["models"] if m["model_name"] == LITE)
    assert lite["effective_enabled"] is True
    assert lite["input_cost_per_1m"] == 0.10


@pytest.mark.integration
async def test_patch_model_and_provider(admin_client: AsyncClient) -> None:
    patch = await admin_client.patch(
        f"{BASE}/models/gemini/{LITE}",
        json={"input_cost_per_1m": 0.5, "enabled": False},
    )
    assert patch.status_code == 200
    assert patch.json()["input_cost_per_1m"] == 0.5
    assert patch.json()["enabled"] is False

    provider = await admin_client.patch(f"{BASE}/providers/gemini", json={"enabled": False})
    assert provider.status_code == 200
    assert all(m["effective_enabled"] is False for m in provider.json()["models"])


@pytest.mark.integration
async def test_post_model_and_typed_errors(admin_client: AsyncClient) -> None:
    body = {
        "provider": "gemini",
        "model_name": "gemini-3.7-pro",
        "capabilities": ["FAST_CHAT", "TOOL_CALLING"],
        "context_window": 200_000,
        "input_cost_per_1m": 1.25,
        "output_cost_per_1m": 5.0,
    }
    created = await admin_client.post(f"{BASE}/models", json=body)
    assert created.status_code == 201
    assert created.json()["effective_enabled"] is True

    duplicate = await admin_client.post(f"{BASE}/models", json=body)
    assert duplicate.status_code == 409

    no_adapter = await admin_client.post(f"{BASE}/models", json={**body, "provider": "openai"})
    assert no_adapter.status_code == 422

    bad_capability = await admin_client.post(
        f"{BASE}/models",
        json={**body, "model_name": "x", "capabilities": ["NOT_A_CAP"]},
    )
    assert bad_capability.status_code == 422

    missing = await admin_client.patch(f"{BASE}/models/gemini/nope", json={"enabled": True})
    assert missing.status_code == 404
    missing_provider = await admin_client.patch(f"{BASE}/providers/nope", json={"enabled": True})
    assert missing_provider.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/llm/test_catalog_admin_api.py -v`
Expected: FAIL — 404 for `/api/admin/llm/catalog` (route missing).

- [ ] **Step 3: Implement the router**

```python
# backend/app/modules/llm/admin_router.py
"""Admin catalog CRUD (backoffice). HTTP only; logic in ModelCatalogAdminService."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_admin
from app.modules.llm.catalog_service import ModelCatalogAdminService
from app.modules.llm.schemas import (
    CatalogAdminResponse,
    ModelAdminRead,
    ModelCreate,
    ModelPatch,
    ProviderAdminRead,
    ProviderPatch,
)
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/admin/llm", tags=["admin"])


def _service(session: Annotated[AsyncSession, Depends(get_db)]) -> ModelCatalogAdminService:
    return ModelCatalogAdminService(session)


@router.get("/catalog")
async def get_catalog(
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[ModelCatalogAdminService, Depends(_service)],
) -> CatalogAdminResponse:
    """Providers + models with enabled state, adapter presence, and pricing."""
    return await service.list_catalog()


@router.patch("/catalog/providers/{provider}")
async def patch_provider(
    provider: str,
    body: ProviderPatch,
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[ModelCatalogAdminService, Depends(_service)],
) -> ProviderAdminRead:
    """Enable/disable a provider (its models follow effectively)."""
    return await service.set_provider_enabled(provider, enabled=body.enabled)


@router.patch("/catalog/models/{provider}/{model_name}")
async def patch_model(
    provider: str,
    model_name: str,
    body: ModelPatch,
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[ModelCatalogAdminService, Depends(_service)],
) -> ModelAdminRead:
    """Partially update one model (enabled, pricing)."""
    return await service.patch_model(provider, model_name, body)


@router.post("/catalog/models", status_code=201)
async def create_model(
    body: ModelCreate,
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[ModelCatalogAdminService, Depends(_service)],
) -> ModelAdminRead:
    """Add a catalog model for a provider with a registered adapter."""
    return await service.create_model(body)
```

- [ ] **Step 4: Map the exceptions**

In `backend/app/core/exceptions.py`, extend the `app.modules.llm.exceptions` import with the four new names, add `_register_llm_catalog_handlers(app)` to `register_exception_handlers`, and append:

```python
def _register_llm_catalog_handlers(app: FastAPI) -> None:
    @app.exception_handler(CatalogProviderNotFoundError)
    async def _catalog_provider_missing(
        _request: Request,
        exc: CatalogProviderNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": f"Unknown provider: {exc}"})

    @app.exception_handler(CatalogModelNotFoundError)
    async def _catalog_model_missing(
        _request: Request,
        exc: CatalogModelNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": f"Unknown model: {exc}"})

    @app.exception_handler(AdapterNotRegisteredError)
    async def _catalog_no_adapter(
        _request: Request,
        exc: AdapterNotRegisteredError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": f"No adapter registered for provider: {exc}"},
        )

    @app.exception_handler(DuplicateCatalogModelError)
    async def _catalog_duplicate(
        _request: Request,
        exc: DuplicateCatalogModelError,
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": f"Model already exists: {exc}"})
```

- [ ] **Step 5: Register the router**

In `backend/app/main.py`, add `from app.modules.llm.admin_router import router as llm_admin_router` to the imports and `app.include_router(llm_admin_router, prefix=settings.app.api_prefix)` next to the `runtime_config_router` line.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/llm/test_catalog_admin_api.py -v`
Expected: PASS (5 tests)

- [ ] **Step 7: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add admin API for LLM model catalog management\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 7: Chat-boundary failure parity + docs

**Files:**
- Test: `backend/tests/llm/test_catalog_failure.py`
- Modify: `CLAUDE.md` (runtime-config paragraph)
- Modify: `README.md` (runtime config / admin section)

**Interfaces:**
- Consumes: Task 3 `ensure_ready` chat wiring; `seeded_catalog` fixture; `make_settings`.
- Produces: the spec's failure-semantics guarantee, pinned by test.

- [ ] **Step 1: Write the tests**

```python
# backend/tests/llm/test_catalog_failure.py
"""All-models-disabled degrades exactly like llm_enabled=false at the chat boundary.

Both cases raise from `await self._llm.ensure_ready()` — before any SSE
event is yielded — and both exception types map to 503 in
core/exceptions.py (_llm_disabled, _llm_no_candidate).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from app.core.db import SessionLocal
from app.modules.llm import catalog
from app.modules.llm.chat_service import ChatService
from app.modules.llm.exceptions import LlmDisabledError, NoCandidateModelError
from sqlalchemy import text

from tests.factories import make_settings


async def _disable_all_models() -> None:
    async with SessionLocal() as session:
        await session.execute(text("UPDATE model_configurations SET enabled = false"))
        await session.commit()
    catalog.invalidate()


@pytest.mark.integration
async def test_llm_disabled_raises_before_any_event(seeded_catalog: None) -> None:
    async with SessionLocal() as session:
        service = ChatService(session, make_settings(llm_enabled=False))
        stream = service.stream_chat(uuid4(), "hello", None)
        with pytest.raises(LlmDisabledError):
            await anext(stream)


@pytest.mark.integration
async def test_all_models_disabled_raises_before_any_event(seeded_catalog: None) -> None:
    await _disable_all_models()
    async with SessionLocal() as session:
        service = ChatService(
            session, make_settings(llm_enabled=True, gemini_api_key="test-key")
        )
        stream = service.stream_chat(uuid4(), "hello", None)
        with pytest.raises(NoCandidateModelError):
            await anext(stream)


@pytest.mark.integration
async def test_all_models_disabled_blocks_confirm_resume(seeded_catalog: None) -> None:
    await _disable_all_models()
    async with SessionLocal() as session:
        service = ChatService(
            session, make_settings(llm_enabled=True, gemini_api_key="test-key")
        )
        confirm = service.stream_confirm(
            uuid4(), uuid4(), uuid4(), approved=True, values=None
        )
        with pytest.raises(NoCandidateModelError):
            await anext(confirm)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/llm/test_catalog_failure.py -v`
Expected: PASS (3 tests) — the wiring landed in Task 3; this pins the parity guarantee. If the second/third test fails, the `ensure_ready` call has drifted from its pre-`try` position in `chat_service.py`.

- [ ] **Step 3: Update CLAUDE.md**

In the config paragraph block (after the runtime-tunable settings paragraph ending "…within the 30s cache TTL."), append a new paragraph:

```markdown
The LLM model catalog is likewise DB-backed at runtime: `modules/llm/registry.py` holds seed-only defaults (inserted if missing at startup — a restart never overwrites admin edits), the effective catalog (provider/model enablement + per-1M pricing used for cost records) is served from `model_providers`/`model_configurations` through the cached snapshot in `modules/llm/catalog.py` (same 30s-TTL/invalidate pattern), and admins manage it via `/api/admin/llm/catalog`. A catalog row is only served when a registered adapter exists for its provider (`modules/llm/providers/KNOWN_ADAPTERS`); rows without one are skipped with a warning.
```

- [ ] **Step 4: Update README.md**

Find the runtime-config/admin-settings documentation section (added by the runtime-config plan; search for "admin/settings") and add a sibling subsection after it:

```markdown
### LLM model catalog (DB-backed)

Which LLM providers/models exist, whether they are enabled, and their
USD-per-1M-token prices (used for cost records) live in the
`model_providers` / `model_configurations` tables — manageable at runtime
via `GET/PATCH/POST /api/admin/llm/catalog...` (admin session required),
no redeploy needed. The code catalog in
`backend/app/modules/llm/registry.py` is only the seed default: startup
inserts missing rows and never overwrites existing ones, so admin edits
(enablement, pricing) survive restarts. Catalog reads are cached
per-process for 30 seconds; the process performing a write sees it
immediately. Disabling every model makes chat return the same 503 as
`LLM_ENABLED=false`.
```

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'test: pin catalog failure semantics; document DB-backed model catalog\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

## Self-review checklist (run after the last task)

- Spec coverage: migration+backfill (T1), snapshot read path incl. sync/async boundary (T2–3), cost provenance (T4), admin API (T5–6), failure semantics + seed semantics + docs (T1, T7).
- `grep -rn "from app.modules.llm.registry import" backend/app` → only `ModelSpec` / `MODEL_CATALOG` imports remain (seed, catalog, repository, telemetry, providers, model_router).
- `grep -rn "build_provider_for" backend/` → empty.
- Full gates green: ruff, mypy strict, `pytest -m "unit or integration"`.
