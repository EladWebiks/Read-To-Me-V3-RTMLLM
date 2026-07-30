# DB-backed Runtime Config Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Runtime-tunable settings (LLM budgets, assistant mode, HITL limits, scrape throttles, download TTLs, feature flags) become editable at runtime via DB-backed sparse overrides layered on the env `Settings`, with a whitelist registry, typed validation, a 30s per-process cache, an admin CRUD API, and one consumer (the chat budget chain) wired end-to-end.

**Architecture:** New module `modules/runtime_config` owns two tables (`app_settings` overrides + `app_settings_audit` append-only history). A registry derives the whitelisted keys from the pydantic settings groups and carries a per-field `TypeAdapter` (type + constraints) used on write and read. `RuntimeConfigService.effective_settings()` returns a `Settings` clone with overrides applied (`model_copy`), exposed as the `get_effective_settings` FastAPI dependency; consumers switch from `get_settings` one `Depends` at a time. Cache is a module-level dict with `time.monotonic()` TTL, invalidated on every write.

**Tech Stack:** SQLAlchemy async + JSONB, Alembic, pydantic v2 `TypeAdapter`, pydantic-settings groups (from the config restructure), FastAPI dependencies, `require_admin` (from the authorization rework).

**Spec:** `docs/superpowers/specs/2026-07-30-runtime-config-design.md`.

## Global Constraints

- **Sequencing:** start ONLY after BOTH `feature/config-restructure` and the authorization rework are merged to `main`. Verify before Task 1 (from `backend/`): `uv run python -c "from app.core.config import get_settings; print(get_settings().llm_runtime.max_tool_iters)"` prints `6`; `uv run python -c "from app.core.deps import require_admin; print('ok')"` prints `ok`; `uv run alembic heads` shows exactly one head; `backend/tests/factories.py` exists. Work on a new branch `feature/runtime-config` off `main`.
- All backend gates must pass per task (run from `backend/`): `uv run ruff check . --fix && uv run ruff format .`, then `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`, `uv run pytest -m "unit or integration"`. Integration tests need Postgres/Redis/MinIO and `TEST_DATABASE_URL` pointing at a separate test DB — never the app DB. The test conftest applies Alembic migrations to the test DB automatically.
- Commit with `bash scripts/git-commit-clean.sh /tmp/msg.txt` (write the message to `/tmp/msg.txt` first). **Never** add `Co-authored-by`/`Made-with` trailers. Verify with `git log -1 --format=%B`.
- Ruff limits: complexity ≤10, statements ≤20, branches ≤6, args ≤6. `# type: ignore[code]`/`# noqa: RULE` only with a specific error code and a reason comment; mypy runs with `warn_unused_ignores`.
- **Never log override values** — log keys and actor ids only. (A future tunable could be sensitive.)
- Module boundaries: only `modules/runtime_config` touches `app_settings`/`app_settings_audit`. Consumers use `RuntimeConfigService` or `get_effective_settings`. `core/deps.py` importing the service follows its existing `AuthService` precedent.
- The service must be constructible without FastAPI (`RuntimeConfigService(session, settings)`) so arq jobs can use it with a `SessionLocal()` session.
- Post-restructure attribute paths are canonical: `settings.llm_runtime.max_turn_cost_usd`, `settings.scrape.delay_seconds`, `settings.storage.download_job_ttl_hours`, `settings.audio.sapi_proxy_enabled`. Tests build settings with `tests/factories.py::make_settings(**legacy_flat_names)`.
- **mypy note for the registry:** the dynamic `Annotated[annotation, info]` expression may trip mypy's special-form checks. Pattern: assign `annotation: Any = info.annotation` first; only if mypy still errors add `# type: ignore[valid-type]  # dynamic Annotated for TypeAdapter` on that line.

---

### Task 1: Models + reversible Alembic migration + ORM registration

**Files:**
- Create: `backend/app/modules/runtime_config/__init__.py` (empty)
- Create: `backend/app/modules/runtime_config/models.py`
- Modify: `backend/app/core/orm.py` (register the new models)
- Create: `backend/migrations/versions/<generated>_add_app_settings_and_audit_tables.py`
- Test: `backend/tests/runtime_config/test_models.py`

**Interfaces:**
- Produces: `AppSetting` (table `app_settings`: `id`, `key` unique+indexed, `value` JSONB, `updated_by` FK→users NOT NULL, `created_at`, `updated_at`) and `AppSettingAudit` (table `app_settings_audit`: `id`, `key` indexed, `action`, `old_value`/`new_value` JSONB nullable, `actor_id` FK→users NOT NULL, `created_at`). Tasks 5–7 persist through these.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/runtime_config/test_models.py
"""Integration tests for app_settings tables (needs Postgres)."""

from collections.abc import AsyncIterator

import pytest
from app.core.config import get_settings
from app.modules.runtime_config.models import AppSetting, AppSettingAudit
from app.modules.users.models import User
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


async def _wipe(session: AsyncSession) -> None:
    await session.execute(text("DELETE FROM app_settings_audit"))
    await session.execute(text("DELETE FROM app_settings"))
    await session.execute(text("DELETE FROM users"))
    await session.commit()


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as sess:
        await _wipe(sess)
        yield sess
        await sess.rollback()
    async with factory() as cleanup:
        await _wipe(cleanup)
    await engine.dispose()


async def _make_admin(session: AsyncSession) -> User:
    user = User(
        username="cfg-admin",
        email="cfg-admin@example.com",
        password_hash=None,
        google_sub="cfg-admin-sub",
        is_admin=True,
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.integration
async def test_setting_and_audit_round_trip(session: AsyncSession) -> None:
    admin = await _make_admin(session)
    session.add(AppSetting(key="llm_runtime.max_tool_iters", value=4, updated_by=admin.id))
    session.add(
        AppSettingAudit(
            key="llm_runtime.max_tool_iters",
            action="set",
            old_value=None,
            new_value=4,
            actor_id=admin.id,
        )
    )
    await session.commit()

    row = (await session.execute(select(AppSetting))).scalar_one()
    assert row.value == 4
    assert row.updated_by == admin.id
    assert row.created_at is not None
    audit = (await session.execute(select(AppSettingAudit))).scalar_one()
    assert audit.action == "set"
    assert audit.new_value == 4


@pytest.mark.integration
async def test_key_is_unique(session: AsyncSession) -> None:
    admin = await _make_admin(session)
    session.add(AppSetting(key="scrape.delay_seconds", value=1.0, updated_by=admin.id))
    await session.flush()
    session.add(AppSetting(key="scrape.delay_seconds", value=2.0, updated_by=admin.id))
    with pytest.raises(IntegrityError):
        await session.flush()
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `uv run pytest tests/runtime_config/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.modules.runtime_config'`

- [ ] **Step 3: Implement the models**

```python
# backend/app/modules/runtime_config/models.py
"""SQLAlchemy models for DB-backed runtime config overrides."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AppSetting(Base):
    """One sparse override for a whitelisted runtime-tunable setting.

    Absence of a row means the env value applies. Rows are hard-deleted on
    clear; history and attribution live in `app_settings_audit`.
    """

    __tablename__ = "app_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    value: Mapped[Any] = mapped_column(JSONB)
    updated_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AppSettingAudit(Base):
    """Append-only history row for every override write (set or clear)."""

    __tablename__ = "app_settings_audit"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(16))  # "set" | "clear"
    old_value: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

Create `backend/app/modules/runtime_config/__init__.py` as an empty file.

In `backend/app/core/orm.py`, add to `import_all_models` (alphabetical spot, after `reader`):

```python
    from app.modules.runtime_config import models as runtime_config_models
```

and add `runtime_config_models,` to the `_ = (...)` tuple.

- [ ] **Step 4: Generate and fill the migration**

Run: `uv run alembic revision -m "add app settings and audit tables"`
Verify `uv run alembic heads` shows exactly one head. Replace the generated bodies:

```python
def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_app_settings_key"), "app_settings", ["key"], unique=True)
    op.create_index(op.f("ix_app_settings_updated_by"), "app_settings", ["updated_by"])
    op.create_table(
        "app_settings_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_app_settings_audit_key"), "app_settings_audit", ["key"])
    op.create_index(op.f("ix_app_settings_audit_actor_id"), "app_settings_audit", ["actor_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_app_settings_audit_actor_id"), table_name="app_settings_audit")
    op.drop_index(op.f("ix_app_settings_audit_key"), table_name="app_settings_audit")
    op.drop_table("app_settings_audit")
    op.drop_index(op.f("ix_app_settings_updated_by"), table_name="app_settings")
    op.drop_index(op.f("ix_app_settings_key"), table_name="app_settings")
    op.drop_table("app_settings")
```

(Add `from sqlalchemy.dialects import postgresql` to the migration imports if the template didn't.)

- [ ] **Step 5: Verify the migration is reversible**

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

Expected: all three succeed against the dev DB.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/runtime_config/test_models.py -v` — Expected: PASS (2 tests; conftest migrates the test DB through the new revision)

- [ ] **Step 7: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add app_settings override and audit tables\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 2: Constraints on the runtime-tunable settings fields

**Files:**
- Modify: `backend/app/core/config.py` (`LlmRuntimeSettings`, `ScrapeSettings`, `StorageSettings`)
- Test: `backend/tests/test_config_constraints.py`

**Interfaces:**
- Consumes: the grouped settings classes from the config restructure; `make_settings` factory.
- Produces: every runtime-tunable field declares bounds (see table in the spec); `assistant_mode` becomes `Literal["internal_only", "external_allowed"]`. Task 3's adapters inherit these constraints automatically.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_config_constraints.py
"""Runtime-tunable fields reject out-of-range values (env AND future overrides)."""

import pytest
from pydantic import ValidationError

from tests.factories import make_settings


@pytest.mark.unit
def test_llm_runtime_bounds() -> None:
    with pytest.raises(ValidationError):
        make_settings(llm_max_tool_iters=0)
    with pytest.raises(ValidationError):
        make_settings(llm_max_turn_cost_usd=0)
    with pytest.raises(ValidationError):
        make_settings(llm_max_external_calls=-1)
    assert make_settings(llm_max_hitl_rounds=0).llm_runtime.max_hitl_rounds == 0


@pytest.mark.unit
def test_assistant_mode_is_constrained() -> None:
    with pytest.raises(ValidationError):
        make_settings(llm_assistant_mode="freeform")
    settings = make_settings(llm_assistant_mode="external_allowed")
    assert settings.llm_runtime.assistant_mode == "external_allowed"


@pytest.mark.unit
def test_scrape_and_storage_bounds() -> None:
    with pytest.raises(ValidationError):
        make_settings(scrape_timeout_seconds=0)
    with pytest.raises(ValidationError):
        make_settings(scrape_max_bytes=100)
    with pytest.raises(ValidationError):
        make_settings(scrape_delay_seconds=-0.1)
    with pytest.raises(ValidationError):
        make_settings(download_job_ttl_hours=0)
    with pytest.raises(ValidationError):
        make_settings(signed_url_expires_seconds=30)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config_constraints.py -v`
Expected: FAIL — every `pytest.raises(ValidationError)` block with `Failed: DID NOT RAISE` (values currently unconstrained)

- [ ] **Step 3: Add the constraints**

In `backend/app/core/config.py`, update the field declarations (keep every
`validation_alias` exactly as-is; only add the bound kwargs / change the
annotation):

`LlmRuntimeSettings`:

```python
    max_tool_iters: int = Field(default=6, ge=1, validation_alias="llm_max_tool_iters")
    max_external_calls: int = Field(default=3, ge=0, validation_alias="llm_max_external_calls")
    max_turn_tokens_in: int = Field(default=64_000, ge=1, validation_alias="llm_max_turn_tokens_in")
    max_turn_tokens_out: int = Field(default=8_192, ge=1, validation_alias="llm_max_turn_tokens_out")
    max_turn_cost_usd: float = Field(default=0.05, gt=0, validation_alias="llm_max_turn_cost_usd")
    run_deadline_seconds: int = Field(default=60, ge=1, validation_alias="llm_run_deadline_seconds")
    context_recent_messages: int = Field(
        default=10, ge=1, validation_alias="llm_context_recent_messages"
    )
    summary_trigger_tokens: int = Field(
        default=12_000, ge=1, validation_alias="llm_summary_trigger_tokens"
    )
    summary_max_output_tokens: int = Field(
        default=1_200, ge=1, validation_alias="llm_summary_max_output_tokens"
    )
    assistant_mode: Literal["internal_only", "external_allowed"] = Field(
        default="internal_only", validation_alias="llm_assistant_mode"
    )
    # HITL: how long a pending confirmation stays valid; max pauses per turn.
    hitl_ttl_seconds: int = Field(default=900, ge=1, validation_alias="llm_hitl_ttl_seconds")
    max_hitl_rounds: int = Field(default=3, ge=0, validation_alias="llm_max_hitl_rounds")
```

`ScrapeSettings`:

```python
    timeout_seconds: int = Field(default=20, ge=1, validation_alias="scrape_timeout_seconds")
    max_bytes: int = Field(default=2_097_152, ge=1024, validation_alias="scrape_max_bytes")  # 2 MB
    delay_seconds: float = Field(default=1.5, ge=0, validation_alias="scrape_delay_seconds")
```

`StorageSettings` (only these two fields change):

```python
    signed_url_expires_seconds: int = Field(default=3600, ge=60)
    # Retention for generated MP3 jobs and MinIO objects (hours).
    download_job_ttl_hours: int = Field(default=24, ge=1)
```

(`Literal` is already imported in `config.py` for `cookie_samesite`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config_constraints.py -v` — Expected: PASS (3 tests)
Run: `uv run pytest -m "unit or integration"` — Expected: PASS (no existing test uses an out-of-range value; if one does, it was relying on nonsense input — fix the test's value, not the constraint)

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add validation bounds to runtime-tunable settings fields\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 3: Whitelist registry with per-field TypeAdapters

**Files:**
- Create: `backend/app/modules/runtime_config/registry.py`
- Test: `backend/tests/runtime_config/test_registry.py`

**Interfaces:**
- Consumes: the settings group classes (`LlmRuntimeSettings`, `ScrapeSettings`, `StorageSettings`, `AudioSettings`) and their constraints (Task 2).
- Produces (used by Tasks 5–7):
  - `@dataclass(frozen=True) TunableField`: `key: str`, `section: str`, `field_name: str`, `group_cls: type[BaseSettings]`, `adapter: TypeAdapter[Any]`
  - `TUNABLE_FIELDS: dict[str, TunableField]` — key → entry, the ONLY overridable key space
  - `section_of(group_cls: type[BaseSettings]) -> str` — raises `KeyError` for non-tunable groups

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/runtime_config/test_registry.py
"""The whitelist registry: coverage, exclusions, and typed validation."""

import pytest
from pydantic import ValidationError

from app.core.config import LlmRuntimeSettings, ScrapeSettings, Settings
from app.modules.runtime_config.registry import TUNABLE_FIELDS, section_of

FORBIDDEN_PREFIXES = ("database.", "redis.", "auth.", "google.", "llm.", "app.")
FORBIDDEN_KEYS = {
    "storage.endpoint",
    "storage.access_key",
    "storage.secret_key",
    "storage.bucket",
    "storage.secure",
    "storage.public_endpoint",
}


@pytest.mark.unit
def test_every_llm_runtime_field_is_tunable() -> None:
    expected = {f"llm_runtime.{name}" for name in LlmRuntimeSettings.model_fields}
    actual = {key for key in TUNABLE_FIELDS if key.startswith("llm_runtime.")}
    assert actual == expected  # a new LlmRuntimeSettings field auto-registers


@pytest.mark.unit
def test_partial_sections_pin_exact_contents() -> None:
    non_llm = {key for key in TUNABLE_FIELDS if not key.startswith("llm_runtime.")}
    assert non_llm == {
        "scrape.timeout_seconds",
        "scrape.max_bytes",
        "scrape.delay_seconds",
        "storage.download_job_ttl_hours",
        "storage.signed_url_expires_seconds",
        "audio.sapi_proxy_enabled",
    }


@pytest.mark.unit
def test_registry_matches_the_pydantic_models() -> None:
    for field in TUNABLE_FIELDS.values():
        assert Settings.model_fields[field.section].annotation is field.group_cls
        assert field.field_name in field.group_cls.model_fields
        assert field.key == f"{field.section}.{field.field_name}"


@pytest.mark.unit
def test_infrastructure_and_secrets_are_never_tunable() -> None:
    for key in TUNABLE_FIELDS:
        assert not key.startswith(FORBIDDEN_PREFIXES), key
        assert key not in FORBIDDEN_KEYS, key


@pytest.mark.unit
def test_adapters_enforce_type_and_constraints() -> None:
    iters = TUNABLE_FIELDS["llm_runtime.max_tool_iters"].adapter
    assert iters.validate_python(4) == 4
    with pytest.raises(ValidationError):
        iters.validate_python("many")
    with pytest.raises(ValidationError):
        iters.validate_python(0)  # ge=1 from Task 2
    mode = TUNABLE_FIELDS["llm_runtime.assistant_mode"].adapter
    assert mode.validate_python("external_allowed") == "external_allowed"
    with pytest.raises(ValidationError):
        mode.validate_python("freeform")


@pytest.mark.unit
def test_section_of_resolves_tunable_groups_only() -> None:
    assert section_of(LlmRuntimeSettings) == "llm_runtime"
    assert section_of(ScrapeSettings) == "scrape"
    with pytest.raises(KeyError):
        section_of(Settings)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/runtime_config/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.modules.runtime_config.registry'`

- [ ] **Step 3: Implement the registry**

```python
# backend/app/modules/runtime_config/registry.py
"""Whitelist of runtime-tunable settings — the ONLY DB-overridable keys.

Secrets, credentials, and infrastructure endpoints are excluded by
construction: their groups/fields simply never appear here. Each entry
carries a TypeAdapter built from the field's annotation AND FieldInfo, so
type and declared constraints are enforced identically on write and read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import TypeAdapter
from pydantic_settings import BaseSettings

from app.core.config import (
    AudioSettings,
    LlmRuntimeSettings,
    ScrapeSettings,
    StorageSettings,
)

# Sections where EVERY field is tunable (derived by introspection, so a new
# field in the group is automatically overridable and validated).
_FULL_SECTIONS: dict[str, type[BaseSettings]] = {
    "llm_runtime": LlmRuntimeSettings,
}

# Sections where only the listed fields are tunable. An unknown field name
# fails at import time (model_fields lookup below), so the list cannot drift.
_PARTIAL_SECTIONS: dict[str, tuple[type[BaseSettings], tuple[str, ...]]] = {
    "scrape": (ScrapeSettings, ("timeout_seconds", "max_bytes", "delay_seconds")),
    "storage": (StorageSettings, ("download_job_ttl_hours", "signed_url_expires_seconds")),
    "audio": (AudioSettings, ("sapi_proxy_enabled",)),
}


@dataclass(frozen=True)
class TunableField:
    """One whitelisted override target."""

    key: str  # "llm_runtime.max_tool_iters"
    section: str  # attribute on the root Settings
    field_name: str  # attribute on the group model
    group_cls: type[BaseSettings]
    adapter: TypeAdapter[Any]  # validates type AND field constraints


def _field_adapter(group_cls: type[BaseSettings], field_name: str) -> TypeAdapter[Any]:
    info = group_cls.model_fields[field_name]
    annotation: Any = info.annotation
    return TypeAdapter(Annotated[annotation, info])


def _entry(section: str, group_cls: type[BaseSettings], field_name: str) -> TunableField:
    return TunableField(
        key=f"{section}.{field_name}",
        section=section,
        field_name=field_name,
        group_cls=group_cls,
        adapter=_field_adapter(group_cls, field_name),
    )


def _build_registry() -> dict[str, TunableField]:
    entries: list[TunableField] = []
    for section, group_cls in _FULL_SECTIONS.items():
        entries.extend(_entry(section, group_cls, name) for name in group_cls.model_fields)
    for section, (group_cls, names) in _PARTIAL_SECTIONS.items():
        entries.extend(_entry(section, group_cls, name) for name in names)
    return {entry.key: entry for entry in entries}


TUNABLE_FIELDS: dict[str, TunableField] = _build_registry()

_SECTION_BY_GROUP: dict[type[BaseSettings], str] = {
    **{cls: section for section, cls in _FULL_SECTIONS.items()},
    **{cls: section for section, (cls, _names) in _PARTIAL_SECTIONS.items()},
}


def section_of(group_cls: type[BaseSettings]) -> str:
    """Root Settings attribute for a tunable group; KeyError if not tunable."""
    return _SECTION_BY_GROUP[group_cls]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/runtime_config/test_registry.py -v` — Expected: PASS (6 tests)

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add runtime-tunable whitelist registry with typed adapters\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 4: Per-process TTL cache

**Files:**
- Create: `backend/app/modules/runtime_config/cache.py`
- Test: `backend/tests/runtime_config/test_cache.py`

**Interfaces:**
- Produces (used by Task 5): `CACHE_TTL_SECONDS: float = 30.0`, `get_cached() -> dict[str, Any] | None` (None when cold/expired), `put(overrides: dict[str, Any]) -> None`, `invalidate() -> None` (called by every write; also the test hook).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/runtime_config/test_cache.py
"""TTL cache semantics: warm hit, expiry, explicit invalidation."""

import pytest

from app.modules.runtime_config import cache


@pytest.fixture(autouse=True)
def _fresh() -> None:
    cache.invalidate()


@pytest.mark.unit
def test_cold_cache_returns_none() -> None:
    assert cache.get_cached() is None


@pytest.mark.unit
def test_put_then_get_returns_copy() -> None:
    cache.put({"llm_runtime.max_tool_iters": 4})
    first = cache.get_cached()
    assert first == {"llm_runtime.max_tool_iters": 4}
    assert first is not None
    first["llm_runtime.max_tool_iters"] = 999  # mutating the copy is harmless
    assert cache.get_cached() == {"llm_runtime.max_tool_iters": 4}


@pytest.mark.unit
def test_entries_expire_after_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"now": 100.0}
    monkeypatch.setattr(cache, "monotonic", lambda: clock["now"])
    cache.put({"scrape.delay_seconds": 0.5})
    clock["now"] = 100.0 + cache.CACHE_TTL_SECONDS - 0.01
    assert cache.get_cached() is not None
    clock["now"] = 100.0 + cache.CACHE_TTL_SECONDS + 0.01
    assert cache.get_cached() is None


@pytest.mark.unit
def test_invalidate_drops_immediately() -> None:
    cache.put({"scrape.delay_seconds": 0.5})
    cache.invalidate()
    assert cache.get_cached() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/runtime_config/test_cache.py -v`
Expected: FAIL with `ImportError`/`ModuleNotFoundError` for `app.modules.runtime_config.cache`

- [ ] **Step 3: Implement the cache**

```python
# backend/app/modules/runtime_config/cache.py
"""Per-process TTL cache for validated override values.

One entry per process: the full validated overrides mapping. Writers call
`invalidate()` so the writing process sees changes immediately; other
processes (arq worker, other API workers) converge within the TTL.
Upgrade path if TTL lag ever matters: Redis pub/sub calling invalidate()
on message — this module is the single seam for that.
"""

from __future__ import annotations

from time import monotonic
from typing import Any

CACHE_TTL_SECONDS = 30.0

_state: dict[str, Any] = {"overrides": None, "expires_at": 0.0}


def get_cached() -> dict[str, Any] | None:
    """Return a copy of the cached overrides, or None when cold/expired."""
    overrides = _state["overrides"]
    if overrides is None or monotonic() >= float(_state["expires_at"]):
        return None
    return dict(overrides)


def put(overrides: dict[str, Any]) -> None:
    """Cache validated overrides for the TTL window."""
    _state["overrides"] = dict(overrides)
    _state["expires_at"] = monotonic() + CACHE_TTL_SECONDS


def invalidate() -> None:
    """Drop the cache now (every write path calls this; also a test hook)."""
    _state["overrides"] = None
    _state["expires_at"] = 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/runtime_config/test_cache.py -v` — Expected: PASS (4 tests)

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add per-process TTL cache for runtime config overrides\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 5: Repository, schemas, exceptions, and RuntimeConfigService

**Files:**
- Create: `backend/app/modules/runtime_config/exceptions.py`
- Create: `backend/app/modules/runtime_config/schemas.py`
- Create: `backend/app/modules/runtime_config/repository.py`
- Create: `backend/app/modules/runtime_config/service.py`
- Test: `backend/tests/runtime_config/test_service.py`

**Interfaces:**
- Consumes: models (Task 1), registry (Task 3), cache (Task 4).
- Produces (used by Tasks 6–7):
  - `RuntimeConfigService(session: AsyncSession, settings: Settings)` with:
    - `async get_effective(group_cls: type[GroupT]) -> GroupT`
    - `async effective_settings() -> Settings`
    - `async list_overrides() -> list[OverrideRead]`
    - `async list_effective() -> list[EffectiveSettingRead]`
    - `async set_override(key: str, value: Any, updated_by: UUID) -> OverrideRead`
    - `async clear_override(key: str, updated_by: UUID) -> None`
  - Exceptions: `RuntimeConfigError` (base), `UnknownSettingKeyError(key)`, `OverrideNotFoundError(key)`, `SettingValueInvalidError(key, message)` — all carry `.key`
  - Schemas: `OverrideRead {key, value, updated_by, updated_at}` (from_attributes), `EffectiveSettingRead {key, effective_value, env_value, overridden, updated_by|None, updated_at|None}`, `SettingValueWrite {value}`, `SettingsListResponse {settings: list[EffectiveSettingRead]}`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/runtime_config/test_service.py
"""Integration tests for override writes, auditing, and effective layering."""

from collections.abc import AsyncIterator

import pytest
from app.core.config import LlmRuntimeSettings, get_settings
from app.modules.runtime_config import cache
from app.modules.runtime_config.exceptions import (
    OverrideNotFoundError,
    SettingValueInvalidError,
    UnknownSettingKeyError,
)
from app.modules.runtime_config.models import AppSetting, AppSettingAudit
from app.modules.runtime_config.registry import TUNABLE_FIELDS
from app.modules.runtime_config.service import RuntimeConfigService
from app.modules.users.models import User
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from tests.factories import make_settings


async def _wipe(session: AsyncSession) -> None:
    await session.execute(text("DELETE FROM app_settings_audit"))
    await session.execute(text("DELETE FROM app_settings"))
    await session.execute(text("DELETE FROM users"))
    await session.commit()


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    cache.invalidate()


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as sess:
        await _wipe(sess)
        yield sess
        await sess.rollback()
    async with factory() as cleanup:
        await _wipe(cleanup)
    await engine.dispose()


@pytest.fixture
async def admin(session: AsyncSession) -> User:
    user = User(
        username="cfg-admin",
        email="cfg-admin@example.com",
        password_hash=None,
        google_sub="cfg-admin-sub",
        is_admin=True,
    )
    session.add(user)
    await session.flush()
    return user


def _service(session: AsyncSession) -> RuntimeConfigService:
    return RuntimeConfigService(session, make_settings())


@pytest.mark.integration
async def test_empty_table_means_env_values(session: AsyncSession) -> None:
    service = _service(session)
    runtime = await service.get_effective(LlmRuntimeSettings)
    assert runtime.max_tool_iters == 6
    effective = await service.effective_settings()
    assert effective.llm_runtime.max_turn_cost_usd == 0.05


@pytest.mark.integration
async def test_set_override_wins_and_clear_restores(
    session: AsyncSession, admin: User
) -> None:
    service = _service(session)
    override = await service.set_override("llm_runtime.max_tool_iters", 2, admin.id)
    assert override.value == 2
    assert override.updated_by == admin.id
    runtime = await service.get_effective(LlmRuntimeSettings)
    assert runtime.max_tool_iters == 2
    effective = await service.effective_settings()
    assert effective.llm_runtime.max_tool_iters == 2
    assert effective.llm_runtime.max_hitl_rounds == 3  # untouched fields keep env values

    await service.clear_override("llm_runtime.max_tool_iters", admin.id)
    runtime = await service.get_effective(LlmRuntimeSettings)
    assert runtime.max_tool_iters == 6


@pytest.mark.integration
async def test_set_override_upserts_single_row(session: AsyncSession, admin: User) -> None:
    service = _service(session)
    await service.set_override("scrape.delay_seconds", 0.5, admin.id)
    await service.set_override("scrape.delay_seconds", 2.5, admin.id)
    rows = list((await session.execute(select(AppSetting))).scalars())
    assert len(rows) == 1
    assert rows[0].value == 2.5
    assert len(await service.list_overrides()) == 1


@pytest.mark.integration
async def test_every_write_is_audited(session: AsyncSession, admin: User) -> None:
    service = _service(session)
    await service.set_override("llm_runtime.max_tool_iters", 2, admin.id)
    await service.set_override("llm_runtime.max_tool_iters", 3, admin.id)
    await service.clear_override("llm_runtime.max_tool_iters", admin.id)
    audits = list(
        (await session.execute(select(AppSettingAudit).order_by(AppSettingAudit.created_at)))
        .scalars()
    )
    assert [(a.action, a.old_value, a.new_value) for a in audits] == [
        ("set", None, 2),
        ("set", 2, 3),
        ("clear", 3, None),
    ]
    assert all(a.actor_id == admin.id for a in audits)


@pytest.mark.integration
async def test_write_rejections(session: AsyncSession, admin: User) -> None:
    service = _service(session)
    with pytest.raises(UnknownSettingKeyError):
        await service.set_override("auth.jwt_secret", "evil", admin.id)
    with pytest.raises(UnknownSettingKeyError):
        await service.set_override("nope.nope", 1, admin.id)
    with pytest.raises(SettingValueInvalidError):
        await service.set_override("llm_runtime.max_tool_iters", "many", admin.id)
    with pytest.raises(SettingValueInvalidError):
        await service.set_override("llm_runtime.max_tool_iters", 0, admin.id)  # ge=1
    with pytest.raises(OverrideNotFoundError):
        await service.clear_override("llm_runtime.max_tool_iters", admin.id)


@pytest.mark.integration
async def test_invalid_stored_row_falls_back_to_env(
    session: AsyncSession, admin: User
) -> None:
    # Simulate a stale row (written before a type/whitelist change).
    session.add(AppSetting(key="llm_runtime.max_tool_iters", value="stale", updated_by=admin.id))
    session.add(AppSetting(key="ghost.key", value=1, updated_by=admin.id))
    await session.flush()
    runtime = await _service(session).get_effective(LlmRuntimeSettings)
    assert runtime.max_tool_iters == 6  # skipped, env value applies


@pytest.mark.integration
async def test_list_effective_reports_overrides(session: AsyncSession, admin: User) -> None:
    service = _service(session)
    await service.set_override("llm_runtime.max_turn_cost_usd", 0.01, admin.id)
    entries = {e.key: e for e in await service.list_effective()}
    assert set(entries) == set(TUNABLE_FIELDS)  # every whitelisted key is listed
    cost = entries["llm_runtime.max_turn_cost_usd"]
    assert cost.overridden is True
    assert cost.effective_value == 0.01
    assert cost.env_value == 0.05
    assert cost.updated_by == admin.id
    iters = entries["llm_runtime.max_tool_iters"]
    assert iters.overridden is False
    assert iters.effective_value == 6
    assert iters.updated_by is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/runtime_config/test_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.modules.runtime_config.service'`

- [ ] **Step 3: Implement exceptions and schemas**

```python
# backend/app/modules/runtime_config/exceptions.py
"""Typed domain exceptions for the runtime config module."""


class RuntimeConfigError(Exception):
    """Base for runtime config errors."""


class UnknownSettingKeyError(RuntimeConfigError):
    """Key is not in the runtime-tunable whitelist."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"Unknown or non-overridable setting: {key}")


class OverrideNotFoundError(RuntimeConfigError):
    """No stored override exists for a whitelisted key."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"No override stored for setting: {key}")


class SettingValueInvalidError(RuntimeConfigError):
    """Value fails the field's type/constraint validation."""

    def __init__(self, key: str, message: str) -> None:
        self.key = key
        super().__init__(f"Invalid value for {key}: {message}")
```

```python
# backend/app/modules/runtime_config/schemas.py
"""Pydantic DTOs for runtime config overrides."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OverrideRead(BaseModel):
    """One stored override row."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    value: Any
    updated_by: UUID
    updated_at: datetime


class EffectiveSettingRead(BaseModel):
    """One whitelisted key with its effective and env values."""

    key: str
    effective_value: Any
    env_value: Any
    overridden: bool
    updated_by: UUID | None = None
    updated_at: datetime | None = None


class SettingsListResponse(BaseModel):
    """GET /admin/settings payload."""

    settings: list[EffectiveSettingRead]


class SettingValueWrite(BaseModel):
    """PUT /admin/settings/{key} body."""

    value: Any
```

- [ ] **Step 4: Implement the repository**

```python
# backend/app/modules/runtime_config/repository.py
"""DB access for app_settings / app_settings_audit (this module only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.runtime_config.models import AppSetting, AppSettingAudit


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Fields for one append-only audit insert."""

    key: str
    action: str  # "set" | "clear"
    old_value: Any
    new_value: Any
    actor_id: UUID


class AppSettingsRepository:
    """CRUD for override rows + audit appends."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[AppSetting]:
        """All override rows, ordered by key."""
        result = await self._session.execute(select(AppSetting).order_by(AppSetting.key))
        return list(result.scalars().all())

    async def get_by_key(self, key: str) -> AppSetting | None:
        """One override row by key."""
        result = await self._session.execute(select(AppSetting).where(AppSetting.key == key))
        return result.scalar_one_or_none()

    async def upsert(self, key: str, value: Any, updated_by: UUID) -> AppSetting:
        """Insert or update the override row for a key."""
        row = await self.get_by_key(key)
        if row is None:
            row = AppSetting(key=key, value=value, updated_by=updated_by)
            self._session.add(row)
        else:
            row.value = value
            row.updated_by = updated_by
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def delete(self, row: AppSetting) -> None:
        """Hard-delete an override row (history lives in the audit table)."""
        await self._session.delete(row)
        await self._session.flush()

    async def add_audit(self, entry: AuditEntry) -> None:
        """Append one audit row."""
        self._session.add(
            AppSettingAudit(
                key=entry.key,
                action=entry.action,
                old_value=entry.old_value,
                new_value=entry.new_value,
                actor_id=entry.actor_id,
            )
        )
        await self._session.flush()
```

- [ ] **Step 5: Implement the service**

```python
# backend/app/modules/runtime_config/service.py
"""Effective-settings resolution (env base + DB overrides) and admin writes."""

from __future__ import annotations

import logging
from typing import Any, TypeVar, cast
from uuid import UUID

from pydantic import ValidationError
from pydantic_settings import BaseSettings
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.runtime_config import cache
from app.modules.runtime_config.exceptions import (
    OverrideNotFoundError,
    SettingValueInvalidError,
    UnknownSettingKeyError,
)
from app.modules.runtime_config.models import AppSetting
from app.modules.runtime_config.registry import TUNABLE_FIELDS, TunableField, section_of
from app.modules.runtime_config.repository import AppSettingsRepository, AuditEntry
from app.modules.runtime_config.schemas import EffectiveSettingRead, OverrideRead

logger = logging.getLogger(__name__)

GroupT = TypeVar("GroupT", bound=BaseSettings)


class RuntimeConfigService:
    """Layered runtime config: env Settings base + sparse DB overrides.

    Constructible without FastAPI — arq jobs pass a SessionLocal() session.
    Warm-cache reads perform zero DB queries.
    """

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._repo = AppSettingsRepository(session)
        self._settings = settings

    async def get_effective(self, group_cls: type[GroupT]) -> GroupT:
        """One settings group with any DB overrides applied."""
        section = section_of(group_cls)
        updates = (await self._per_section()).get(section)
        base = getattr(self._settings, section)
        model = base.model_copy(update=updates) if updates else base
        return cast("GroupT", model)

    async def effective_settings(self) -> Settings:
        """Full Settings clone with overrides applied to tunable sections."""
        per_section = await self._per_section()
        if not per_section:
            return self._settings
        updates = {
            section: getattr(self._settings, section).model_copy(update=fields)
            for section, fields in per_section.items()
        }
        return self._settings.model_copy(update=updates)

    async def list_overrides(self) -> list[OverrideRead]:
        """Current DB overrides."""
        return [OverrideRead.model_validate(row) for row in await self._repo.list_all()]

    async def list_effective(self) -> list[EffectiveSettingRead]:
        """Every whitelisted key with effective/env values and attribution."""
        rows = {row.key: row for row in await self._repo.list_all()}
        overrides = await self._validated_overrides()
        return [
            self._effective_entry(field, rows.get(key), overrides)
            for key, field in sorted(TUNABLE_FIELDS.items())
        ]

    async def set_override(self, key: str, value: Any, updated_by: UUID) -> OverrideRead:
        """Validate → upsert → audit → invalidate. Never logs the value."""
        field = self._require_field(key)
        try:
            validated = field.adapter.validate_python(value)
        except ValidationError as exc:
            raise SettingValueInvalidError(key, exc.errors()[0]["msg"]) from exc
        stored = field.adapter.dump_python(validated, mode="json")
        existing = await self._repo.get_by_key(key)
        old_value = existing.value if existing else None
        row = await self._repo.upsert(key, stored, updated_by)
        await self._repo.add_audit(AuditEntry(key, "set", old_value, stored, updated_by))
        cache.invalidate()
        logger.info("app setting override set", extra={"key": key, "actor": str(updated_by)})
        return OverrideRead.model_validate(row)

    async def clear_override(self, key: str, updated_by: UUID) -> None:
        """Delete → audit → invalidate. Env value applies again."""
        self._require_field(key)
        existing = await self._repo.get_by_key(key)
        if existing is None:
            raise OverrideNotFoundError(key)
        old_value = existing.value
        await self._repo.delete(existing)
        await self._repo.add_audit(AuditEntry(key, "clear", old_value, None, updated_by))
        cache.invalidate()
        logger.info("app setting override cleared", extra={"key": key, "actor": str(updated_by)})

    def _require_field(self, key: str) -> TunableField:
        field = TUNABLE_FIELDS.get(key)
        if field is None:
            raise UnknownSettingKeyError(key)
        return field

    async def _per_section(self) -> dict[str, dict[str, Any]]:
        """Validated overrides grouped by Settings section attribute."""
        per_section: dict[str, dict[str, Any]] = {}
        for key, value in (await self._validated_overrides()).items():
            field = TUNABLE_FIELDS[key]
            per_section.setdefault(field.section, {})[field.field_name] = value
        return per_section

    async def _validated_overrides(self) -> dict[str, Any]:
        """Load-and-validate overrides, served from the process cache when warm."""
        cached = cache.get_cached()
        if cached is not None:
            return cached
        validated: dict[str, Any] = {}
        for row in await self._repo.list_all():
            self._absorb_row(row, validated)
        cache.put(validated)
        return validated

    def _absorb_row(self, row: AppSetting, validated: dict[str, Any]) -> None:
        """Fail-open per row: unknown or invalid rows are skipped with a warning."""
        field = TUNABLE_FIELDS.get(row.key)
        if field is None:
            logger.warning("ignoring unknown app_settings row", extra={"key": row.key})
            return
        try:
            validated[row.key] = field.adapter.validate_python(row.value)
        except ValidationError:
            logger.warning("ignoring invalid app_settings override", extra={"key": row.key})

    def _effective_entry(
        self,
        field: TunableField,
        row: AppSetting | None,
        overrides: dict[str, Any],
    ) -> EffectiveSettingRead:
        env_value = getattr(getattr(self._settings, field.section), field.field_name)
        overridden = field.key in overrides
        return EffectiveSettingRead(
            key=field.key,
            effective_value=overrides[field.key] if overridden else env_value,
            env_value=env_value,
            overridden=overridden,
            updated_by=row.updated_by if row is not None else None,
            updated_at=row.updated_at if row is not None else None,
        )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/runtime_config/test_service.py -v` — Expected: PASS (7 tests)

- [ ] **Step 7: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add RuntimeConfigService with layered effective settings and audit\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 6: Admin API (`/api/admin/settings`) behind `require_admin`

**Files:**
- Create: `backend/app/modules/runtime_config/router.py`
- Modify: `backend/app/core/exceptions.py` (new handler group)
- Modify: `backend/app/main.py` (include the router)
- Test: `backend/tests/runtime_config/test_admin_api.py`

**Interfaces:**
- Consumes: `RuntimeConfigService` + schemas + exceptions (Task 5); `require_admin` from `app.core.deps` (authorization rework).
- Produces:
  - `GET /api/admin/settings` → 200 `SettingsListResponse`
  - `PUT /api/admin/settings/{key}` body `{"value": <json>}` → 200 `OverrideRead`
  - `DELETE /api/admin/settings/{key}` → 204
  - `UnknownSettingKeyError`/`OverrideNotFoundError` → 404, `SettingValueInvalidError` → 422; anon → 401, non-admin → 403 via existing handlers.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/runtime_config/test_admin_api.py
"""Admin settings API: authz matrix, typed errors, set/clear flows (needs Postgres)."""

from collections.abc import AsyncIterator, Callable
from uuid import UUID

import pytest
from app.core.config import get_settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_access_token
from app.main import app
from app.modules.runtime_config import cache
from app.modules.users.models import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


async def _wipe(session: AsyncSession) -> None:
    await session.execute(text("DELETE FROM app_settings_audit"))
    await session.execute(text("DELETE FROM app_settings"))
    await session.execute(text("DELETE FROM users"))
    await session.commit()


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


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    cache.invalidate()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as sess:
        await _wipe(sess)
    app.dependency_overrides[get_db] = _make_db_override(session_factory)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()
    async with session_factory() as sess:
        await _wipe(sess)
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
    client.cookies.set(COOKIE_NAME, token)


@pytest.fixture
async def admin_client(client: AsyncClient) -> AsyncClient:
    user_id = await _create_user("cfg-admin", is_admin=True)
    _login(client, user_id, "cfg-admin")
    return client


@pytest.mark.integration
async def test_anonymous_gets_401(client: AsyncClient) -> None:
    assert (await client.get("/api/admin/settings")).status_code == 401


@pytest.mark.integration
async def test_non_admin_gets_403(client: AsyncClient) -> None:
    user_id = await _create_user("cfg-reader", is_admin=False)
    _login(client, user_id, "cfg-reader")
    assert (await client.get("/api/admin/settings")).status_code == 403
    put = await client.put(
        "/api/admin/settings/llm_runtime.max_tool_iters", json={"value": 2}
    )
    assert put.status_code == 403


@pytest.mark.integration
async def test_set_get_clear_flow(admin_client: AsyncClient) -> None:
    put = await admin_client.put(
        "/api/admin/settings/llm_runtime.max_tool_iters", json={"value": 2}
    )
    assert put.status_code == 200
    assert put.json()["value"] == 2

    listing = await admin_client.get("/api/admin/settings")
    assert listing.status_code == 200
    entries = {e["key"]: e for e in listing.json()["settings"]}
    assert entries["llm_runtime.max_tool_iters"]["overridden"] is True
    assert entries["llm_runtime.max_tool_iters"]["effective_value"] == 2
    assert entries["llm_runtime.max_hitl_rounds"]["overridden"] is False

    delete = await admin_client.delete("/api/admin/settings/llm_runtime.max_tool_iters")
    assert delete.status_code == 204
    listing = await admin_client.get("/api/admin/settings")
    entries = {e["key"]: e for e in listing.json()["settings"]}
    assert entries["llm_runtime.max_tool_iters"]["overridden"] is False


@pytest.mark.integration
async def test_unknown_key_is_404(admin_client: AsyncClient) -> None:
    put = await admin_client.put("/api/admin/settings/auth.jwt_secret", json={"value": "x"})
    assert put.status_code == 404
    delete = await admin_client.delete("/api/admin/settings/nope.nope")
    assert delete.status_code == 404


@pytest.mark.integration
async def test_clear_without_override_is_404(admin_client: AsyncClient) -> None:
    delete = await admin_client.delete("/api/admin/settings/llm_runtime.max_tool_iters")
    assert delete.status_code == 404


@pytest.mark.integration
async def test_invalid_value_is_422(admin_client: AsyncClient) -> None:
    bad_type = await admin_client.put(
        "/api/admin/settings/llm_runtime.max_tool_iters", json={"value": "many"}
    )
    assert bad_type.status_code == 422
    out_of_range = await admin_client.put(
        "/api/admin/settings/llm_runtime.max_tool_iters", json={"value": 0}
    )
    assert out_of_range.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/runtime_config/test_admin_api.py -v`
Expected: FAIL — 404 for `/api/admin/settings` on every request (route not mounted)

- [ ] **Step 3: Implement the router**

```python
# backend/app/modules/runtime_config/router.py
"""Admin CRUD for runtime config overrides. HTTP only; logic in the service."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.deps import get_db, require_admin
from app.modules.runtime_config.schemas import (
    OverrideRead,
    SettingsListResponse,
    SettingValueWrite,
)
from app.modules.runtime_config.service import RuntimeConfigService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/admin/settings", tags=["admin"])


def _service(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RuntimeConfigService:
    return RuntimeConfigService(session, settings)


@router.get("")
async def list_settings(
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[RuntimeConfigService, Depends(_service)],
) -> SettingsListResponse:
    """Every whitelisted key: effective value, env value, override status."""
    return SettingsListResponse(settings=await service.list_effective())


@router.put("/{key}")
async def put_override(
    key: str,
    body: SettingValueWrite,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[RuntimeConfigService, Depends(_service)],
) -> OverrideRead:
    """Set or replace one override; attributed to the authenticated admin."""
    return await service.set_override(key, body.value, updated_by=admin.id)


@router.delete("/{key}", status_code=204)
async def delete_override(
    key: str,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[RuntimeConfigService, Depends(_service)],
) -> None:
    """Remove one override; the env value applies again."""
    await service.clear_override(key, updated_by=admin.id)
```

(If the authorization rework named its dependency differently than
`require_admin` or placed the admin id elsewhere on `UserRead`, follow the
merged code — the contract is: an admin-only dependency yielding the
authenticated user whose `.id` becomes `updated_by`.)

- [ ] **Step 4: Register exception handlers and the router**

In `backend/app/core/exceptions.py`, add the import:

```python
from app.modules.runtime_config.exceptions import (
    OverrideNotFoundError,
    SettingValueInvalidError,
    UnknownSettingKeyError,
)
```

add `_register_runtime_config_handlers(app)` to `register_exception_handlers`, and append:

```python
def _register_runtime_config_handlers(app: FastAPI) -> None:
    @app.exception_handler(UnknownSettingKeyError)
    async def _unknown_setting(
        _request: Request,
        exc: UnknownSettingKeyError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(OverrideNotFoundError)
    async def _override_missing(
        _request: Request,
        exc: OverrideNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(SettingValueInvalidError)
    async def _setting_invalid(
        _request: Request,
        exc: SettingValueInvalidError,
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})
```

In `backend/app/main.py`, add the import
`from app.modules.runtime_config.router import router as runtime_config_router`
and (next to the other `include_router` lines):

```python
    app.include_router(runtime_config_router, prefix=settings.app.api_prefix)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/runtime_config/test_admin_api.py -v` — Expected: PASS (7 tests)

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add admin settings API for runtime config overrides\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 7: `get_effective_settings` dependency + wire the chat budget chain

**Files:**
- Modify: `backend/app/core/deps.py`
- Modify: `backend/app/modules/llm/router.py` (`_chat_service` only)
- Test: `backend/tests/runtime_config/test_effective_dependency.py`

**Interfaces:**
- Consumes: `RuntimeConfigService.effective_settings()` (Task 5).
- Produces: `async get_effective_settings(session, settings) -> Settings` in `core/deps.py`. The chat chain (`_chat_service → ChatService → OrchestrationService → RunBudget.from_settings`) reads effective values; every other call site stays on `get_settings` and migrates later, one `Depends` at a time.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/runtime_config/test_effective_dependency.py
"""get_effective_settings: layering proof + chat-router wiring pin."""

import inspect
from collections.abc import AsyncIterator

import pytest
from app.core.config import get_settings
from app.modules.orchestration.budget import RunBudget
from app.modules.orchestration.exceptions import BudgetExceededError
from app.modules.llm.types import Usage
from app.modules.runtime_config import cache
from app.modules.runtime_config.service import RuntimeConfigService
from app.modules.users.models import User
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


@pytest.mark.unit
def test_chat_service_dependency_uses_effective_settings() -> None:
    from app.core.deps import get_effective_settings
    from app.modules.llm import router as llm_router

    parameter = inspect.signature(llm_router._chat_service).parameters["settings"]
    depends = parameter.annotation.__metadata__[0]
    assert depends.dependency is get_effective_settings


async def _wipe(session: AsyncSession) -> None:
    await session.execute(text("DELETE FROM app_settings_audit"))
    await session.execute(text("DELETE FROM app_settings"))
    await session.execute(text("DELETE FROM users"))
    await session.commit()


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    cache.invalidate()


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as sess:
        await _wipe(sess)
        yield sess
        await sess.rollback()
    async with factory() as cleanup:
        await _wipe(cleanup)
    await engine.dispose()


@pytest.mark.integration
async def test_override_changes_budget_enforcement_without_restart(
    session: AsyncSession,
) -> None:
    from app.core.deps import get_effective_settings

    base = get_settings()
    original_cap = base.llm_runtime.max_turn_cost_usd
    new_cap = original_cap / 2

    admin = User(
        username="cfg-admin",
        email="cfg-admin@example.com",
        password_hash=None,
        google_sub="cfg-admin-sub",
        is_admin=True,
    )
    session.add(admin)
    await session.flush()
    await RuntimeConfigService(session, base).set_override(
        "llm_runtime.max_turn_cost_usd", new_cap, admin.id
    )

    effective = await get_effective_settings(session, base)
    budget = RunBudget.from_settings(effective)
    assert budget.max_cost_usd == new_cap
    with pytest.raises(BudgetExceededError):
        budget.add_usage(Usage(1, 1), cost_usd=new_cap * 1.5)

    # Same process, no restart: the env-backed base is untouched, and a
    # budget built from it still enforces the original cap.
    assert base.llm_runtime.max_turn_cost_usd == original_cap
    assert RunBudget.from_settings(base).max_cost_usd == original_cap
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/runtime_config/test_effective_dependency.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_effective_settings'` (both tests)

- [ ] **Step 3: Add the dependency**

In `backend/app/core/deps.py`, add the import (next to the existing
`AuthService` import — same core→module precedent):

```python
from app.modules.runtime_config.service import RuntimeConfigService
```

and append:

```python
async def get_effective_settings(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Settings:
    """Settings with DB overrides applied to runtime-tunable sections.

    Drop-in for `get_settings` — consumers migrate one Depends at a time.
    Cheap when the per-process cache is warm (no DB query).
    """
    return await RuntimeConfigService(session, settings).effective_settings()
```

- [ ] **Step 4: Switch the chat call site**

In `backend/app/modules/llm/router.py`, extend the deps import:

```python
from app.core.deps import get_current_user, get_db, get_effective_settings
```

and change **only** `_chat_service`:

```python
def _chat_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_effective_settings)],
) -> ChatService:
    return ChatService(session, settings)
```

(`_llm_service` stays on `get_settings` — provider config is not tunable.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/runtime_config/test_effective_dependency.py -v` — Expected: PASS (2 tests)
Run: `uv run pytest tests/llm -v` — Expected: PASS (chat/orchestration/HITL tests construct services directly with factory settings, so the dependency swap does not disturb them)

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add get_effective_settings and wire chat budgets to runtime config\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 8: Documentation + final verification

**Files:**
- Modify: `README.md`, `CLAUDE.md` (repo root)

**Interfaces:**
- Consumes: everything above. No new env vars — `.env.example` and docker-compose are untouched by design.

- [ ] **Step 1: README — new "Runtime configuration overrides" subsection**

Add under the configuration section (after the env-var documentation):

- Admins can override runtime-tunable settings at runtime via
  `GET/PUT/DELETE /api/admin/settings[/{key}]` (admin session required).
  Keys are `section.field`, e.g. `llm_runtime.max_turn_cost_usd`,
  `scrape.delay_seconds`, `storage.download_job_ttl_hours`,
  `audio.sapi_proxy_enabled`. The whitelist lives in
  `backend/app/modules/runtime_config/registry.py`; secrets and
  infrastructure endpoints (DB/Redis/MinIO/JWT/Google) can never be
  overridden.
- Effective value = env value unless an override exists; deleting the
  override restores the env value. Every change is attributed and recorded
  in `app_settings_audit`.
- **Propagation:** each process caches overrides for 30 seconds. The
  process that takes the write sees it immediately; the arq worker and any
  other process converge within 30 seconds — a budget or throttle change
  can take up to 30s to reach running jobs.
- Values are validated against the same pydantic types/bounds as the env
  vars; since this release, out-of-range env values (e.g.
  `SCRAPE_TIMEOUT_SECONDS=0`) also fail startup.
- Worker/jobs usage snippet:

```python
from app.core.config import LlmRuntimeSettings, get_settings
from app.core.db import SessionLocal
from app.modules.runtime_config.service import RuntimeConfigService

async with SessionLocal() as session:
    service = RuntimeConfigService(session, get_settings())
    runtime = await service.get_effective(LlmRuntimeSettings)
```

- [ ] **Step 2: CLAUDE.md — extend the settings rule**

Append to the "when adding a setting" guidance:

> Runtime-tunable settings (safe to change without redeploy) additionally
> register in `backend/app/modules/runtime_config/registry.py` — whole
> groups via `_FULL_SECTIONS`, single fields via `_PARTIAL_SECTIONS` — and
> should declare pydantic bounds (`ge`/`gt`/`Literal`). Never register
> secrets, credentials, or infrastructure endpoints. Consumers read
> overrides via `get_effective_settings` (FastAPI) or
> `RuntimeConfigService` (jobs); overrides propagate to other processes
> within the 30s cache TTL.

- [ ] **Step 3: Full final gates + boot smoke**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
uv run python -c "import app.main; import app.jobs.worker; print('imports ok')"
```

Expected: all green; `imports ok`.

- [ ] **Step 4: Commit**

```bash
printf 'docs: document runtime config overrides, whitelist, and cache TTL\n' > /tmp/msg.txt
git add README.md CLAUDE.md
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```
