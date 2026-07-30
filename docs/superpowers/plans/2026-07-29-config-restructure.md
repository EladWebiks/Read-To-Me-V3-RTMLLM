# Config Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the flat 49-field `Settings` into composed per-group `BaseSettings` sub-models, and give every value exactly one home — dev-correct defaults in code, infra values in docker-compose, real secrets in `.env` only.

**Architecture:** Each settings group is its own `BaseSettings` subclass (fields keep the legacy flat env names via field name or `Field(validation_alias=...)`); the root `Settings` composes them with `default_factory`. Groups are extracted one task at a time (the root keeps the not-yet-moved flat fields), so every task is independently green, with strict mypy as the safety net for missed attribute renames. A shared hermetic test factory (`make_settings`) accepts legacy flat kwargs and routes them to groups by introspection, so most test call sites are migrated once (Task 1) and survive every later move untouched.

**Tech Stack:** pydantic-settings 2.x (composed `BaseSettings`, `validation_alias`), pydantic v2 `model_validator`, python-dotenv (ships with pydantic-settings), docker-compose YAML anchors + `env_file`.

**Spec:** `docs/superpowers/specs/2026-07-29-config-restructure-design.md` — its "New structure", "Attribute renames" and "Call-site inventory" sections still apply. Its **"Full field classification", "Fail-fast semantics", "Secret hygiene" and "docker-compose de-duplication" sections are superseded** by the Variable Placement table below (the spec assumed seven required vars and no secret defaults in code; that was reversed).

---

## Variable Placement (authoritative)

Every variable has exactly one home. Do not mirror a value across two homes.

| Bucket | Home | Variables |
|---|---|---|
| **Infra — compose produces** | `docker-compose.yml` `x-app-env`; **required in code, no default**; `.env.example` documents them for native dev only | `DATABASE_URL`, `REDIS_URL`, `MINIO_ENDPOINT` |
| **Infra — compose provisions** | `docker-compose.yml` `x-app-env` (interpolated) **and** dev default in code for native dev | `MINIO_PUBLIC_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` |
| **Real secrets** | `.env` **only** — no code default, **forbidden in `docker-compose.yml`** (they reach containers via `env_file`) | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `GEMINI_API_KEY` |
| **Everything else** | dev-correct default in `backend/app/core/config.py`; absent from compose and from `.env.example`; overridable by a real env var when deploying | the remaining ~40 fields, incl. `JWT_SECRET`, `ADMIN_PASSWORD`, `CORS_ORIGINS`, `COOKIE_SECURE`, `LLM_ENABLED` |
| **Runtime knobs — code only** | plain defaults in `LlmRuntimeSettings`, **no env names at all** (`LLM_MAX_TOOL_ITERS` etc. stop being read) | the 12 `llm_runtime` fields |

Consequences that drive the tasks below:

- **Exactly three required vars:** `DATABASE_URL`, `REDIS_URL`, `MINIO_ENDPOINT`. Missing ⇒ pydantic `ValidationError` at `get_settings()`.
- **One conditional:** `GEMINI_API_KEY` required iff `LLM_ENABLED=true`.
- `JWT_SECRET`/`ADMIN_PASSWORD`/`MINIO_*_KEY` keep dev defaults in code, so the `S105` per-file-ignore in `backend/pyproject.toml` **stays**.
- Compose carries **no** `${VAR:?}` guards and **no** secrets.
- MinIO credentials are the one deliberate two-home value: compose provisions the MinIO server from the same variable, so app and server must not drift.

## Global Constraints

- **Sequencing:** start ONLY after `feature/sso` is merged to `main`. Verify before Task 1: `git log --oneline main | head -20` shows the SSO work and `backend/tests/test_google_config.py` exists. Work on a new branch `feature/config-restructure` off `main`.
- Env var names never change, with one deliberate exception: the 12 `llm_runtime` knobs lose their `LLM_*` env names (they become code-only until the runtime-config layer lands — see `docs/superpowers/plans/2026-07-30-runtime-config.md`). No `env_nested_delimiter`.
- Google SSO 503 contract: `google.client_id/client_secret/redirect_uri` stay `Optional[str] = None`. No startup validation for them, ever.
- All backend gates must pass per task (run from `backend/`): `uv run ruff check . --fix && uv run ruff format .`, then `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`, `uv run pytest -m "unit or integration"`. Integration tests need Postgres/Redis/MinIO and `TEST_DATABASE_URL` pointing at a separate test DB.
- Commit with `bash scripts/git-commit-clean.sh /tmp/msg.txt` (write message to `/tmp/msg.txt` first). **Never** add `Co-authored-by`/`Made-with` trailers. Verify with `git log -1 --format=%B`.
- Ruff limits: complexity ≤10, statements ≤20, branches ≤6, returns ≤4, args ≤6. `# type: ignore[code]`/`# noqa: RULE` only with a specific code and a reason comment. mypy runs with `warn_unused_ignores` — add an ignore only when mypy actually reports the error, and remove it if mypy flags it unused.
- Behavior-preserving except for three accepted deltas: missing `DATABASE_URL`/`REDIS_URL`/`MINIO_ENDPOINT` now crashes startup; the LLM key check fires at `get_settings()` in every process (worker included) as a pydantic `ValidationError` instead of `LlmConfigError` in the API only; the 12 `llm_runtime` knobs are no longer settable via env.
- `get_settings()` stays `@lru_cache`'d with the same signature. `Depends(get_settings)` call sites untouched.
- **pydantic mypy plugin note (applies to Tasks 2–5):** the plugin synthesizes `__init__` from fields, so it may flag `Field(default_factory=GroupCls)` for groups with required fields, and it WILL flag `GroupCls(_env_file=None)`. Pattern: write the plain form first, run `uv run mypy .`, and only where it errors use `Field(default_factory=lambda: GroupCls())  # type: ignore[call-arg]  # values come from env` / `GroupCls(_env_file=None)  # type: ignore[call-arg]  # pydantic-settings runtime kwarg`.

---

### Task 1: Test scaffolding — env bootstrap + hermetic settings factory

**Files:**
- Modify: `backend/tests/conftest.py` (top-of-file env bootstrap)
- Create: `backend/tests/factories.py`
- Create: `backend/tests/test_settings_factory.py`
- Modify (migrate direct `Settings(...)` constructions to the factory): `backend/tests/test_security.py`, `backend/tests/test_storage_presign.py`, `backend/tests/test_google_config.py`, `backend/tests/test_google_oauth.py`, `backend/tests/llm/test_chat.py`, `backend/tests/llm/test_conversation_context.py`, `backend/tests/llm/test_hitl.py`, `backend/tests/llm/test_orchestration.py`, `backend/tests/llm/test_orchestration_budget.py`

**Interfaces:**
- Produces: `make_settings(**overrides: Any) -> Settings` in `tests/factories.py` — accepts **legacy flat env-style names** (`jwt_secret=...`, `llm_enabled=True`, `minio_endpoint=...`), builds a hermetic `Settings` (no dotenv), fills the three required values with safe dummies, raises `ValueError` on unknown keys. Every later task relies on this routing surviving field moves unchanged.
- Produces: conftest guarantees `REDIS_URL` and `MINIO_ENDPOINT` exist before any `app.core.config` import, and still forces `DATABASE_URL` to the test DB.

- [ ] **Step 1: Write the failing factory tests**

```python
# backend/tests/test_settings_factory.py
"""The hermetic settings factory: dummies, overrides, unknown-key rejection."""

import pytest

from tests.factories import make_settings


@pytest.mark.unit
def test_factory_builds_settings_with_dummy_required_values() -> None:
    settings = make_settings()
    # Flat access in Task 1; Task 2 moves these behind groups and updates
    # these two assertions in the same commit as the move.
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.minio_endpoint == "localhost:9000"


@pytest.mark.unit
def test_factory_override_wins() -> None:
    settings = make_settings(redis_url="redis://other:6379/1")
    assert settings.redis_url == "redis://other:6379/1"


@pytest.mark.unit
def test_factory_rejects_unknown_keys() -> None:
    with pytest.raises(ValueError, match="Unknown settings override: nope"):
        make_settings(nope=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `uv run pytest tests/test_settings_factory.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tests.factories'`

- [ ] **Step 3: Implement the factory**

The implementation is written in its FINAL generic form: it introspects the
root `Settings` for group fields (`BaseSettings`-typed) and routes flat keys
to them by `validation_alias`, falling back to the field's own name. In
Task 1 there are no groups yet, so every key falls through to the root — the
same code then absorbs Tasks 2–5 with zero factory changes.

```python
# backend/tests/factories.py
"""Hermetic `Settings` construction for tests.

`Settings` is (being) composed of per-group `BaseSettings` classes that each
read env + dotenv on their own, so `Settings(_env_file=None)` alone is not
hermetic. This factory builds every group with `_env_file=None`, fills the
required fields with safe dummies, and routes flat legacy-named overrides
(`jwt_secret=...`, `minio_endpoint=...`) to the right group.

Note: os.environ still takes part for fields NOT passed explicitly (same as
direct `Settings(...)` construction always did); conftest pins the required
vars, so results are deterministic.
"""

from __future__ import annotations

from typing import Any

from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings

from app.core.config import Settings

# Only the three vars that have no code default. Values need to be
# well-formed, not reachable — factory-built Settings never open real
# connections (DB fixtures use get_settings(), which conftest pins).
_REQUIRED_DUMMIES: dict[str, Any] = {
    "database_url": "postgresql+asyncpg://rtm:rtm@localhost:5432/rtm_test",
    "redis_url": "redis://localhost:6379/0",
    "minio_endpoint": "localhost:9000",
}


def _group_classes() -> dict[str, type[BaseSettings]]:
    """Root field name -> group class, for composed group fields."""
    groups: dict[str, type[BaseSettings]] = {}
    for name, field in Settings.model_fields.items():
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseSettings):
            groups[name] = annotation
    return groups


def _flat_key(field_name: str, field: FieldInfo) -> str:
    """Legacy flat name of a group field (its env alias, or its own name)."""
    alias = field.validation_alias
    return alias if isinstance(alias, str) else field_name


def _routing() -> dict[str, str]:
    """Legacy flat key -> root group attribute name."""
    return {
        _flat_key(field_name, field): group_name
        for group_name, cls in _group_classes().items()
        for field_name, field in cls.model_fields.items()
    }


def make_settings(**overrides: Any) -> Settings:
    """Build hermetic Settings; overrides use legacy flat env-style names."""
    values = {**_REQUIRED_DUMMIES, **overrides}
    routing = _routing()
    per_group: dict[str, dict[str, Any]] = {name: {} for name in _group_classes()}
    flat: dict[str, Any] = {}
    for key, value in values.items():
        if key in routing:
            per_group[routing[key]][key] = value
        elif key in Settings.model_fields:
            flat[key] = value
        else:
            msg = f"Unknown settings override: {key}"
            raise ValueError(msg)
    groups = {
        name: cls(_env_file=None, **per_group[name])  # type: ignore[call-arg]  # pydantic-settings runtime kwarg
        for name, cls in _group_classes().items()
    }
    return Settings(_env_file=None, **groups, **flat)  # type: ignore[call-arg]  # pydantic-settings runtime kwarg
```

- [ ] **Step 4: Extend the conftest env bootstrap**

Replace the top of `backend/tests/conftest.py` (everything above
`def _dsn_parts`) with:

```python
"""Pytest bootstrap: hermetic env for settings + isolated test database."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

# Must run before any app.core.config / alembic import.
_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
_DEFAULT_TEST_DB = "postgresql+asyncpg://rtm:rtm@localhost:5432/rtm_test"

# 1) Real dev values from the repo-root .env (if present) win over dummies,
#    so integration tests keep talking to the local stack's credentials.
if _ROOT_ENV.exists():
    for _key, _value in dotenv_values(_ROOT_ENV).items():
        if _value is not None:
            os.environ.setdefault(_key, _value)

# 2) The two remaining no-default vars, so a clean checkout (or a
#    docker-compose .env, which must not contain them) still boots.
for _key, _value in {
    "REDIS_URL": "redis://localhost:6379/0",
    "MINIO_ENDPOINT": "localhost:9000",
}.items():
    os.environ.setdefault(_key, _value)

# 3) Integration tests must never touch the app database.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_DB)
```

Keep `_dsn_parts`, `_ensure_database`, `_run_migrations`, and
`pytest_configure` exactly as they are. `dotenv` needs no new dependency —
python-dotenv is a required dependency of pydantic-settings.

- [ ] **Step 5: Migrate every direct `Settings(...)` construction to the factory**

Find them: `grep -rn "Settings(" tests/ | grep -v "make_settings\|WorkerSettings\|RedisSettings"`

Apply mechanically (import `from tests.factories import make_settings`, drop
the now-unused `Settings` import where it was only used for construction):

- `tests/test_security.py:27,38,39` — `Settings(jwt_secret="…")` → `make_settings(jwt_secret="…")`
- `tests/test_storage_presign.py:16` — `Settings(minio_endpoint=…, minio_public_endpoint=…, …)` → `make_settings(` same kwargs `)`
- `tests/test_google_config.py:9` — `Settings(_env_file=None)  # type: ignore[call-arg]` → `make_settings()`
- `tests/test_google_oauth.py` `_settings()` helper — → `make_settings(google_client_id=CLIENT_ID, google_client_secret="test-secret", google_redirect_uri="http://localhost:5173/api/auth/google/callback")`
- `tests/llm/test_chat.py:68`, `tests/llm/test_conversation_context.py:34`, `tests/llm/test_hitl.py:49`, `tests/llm/test_orchestration.py:93,131,164,195` — `Settings(llm_enabled=True, gemini_api_key="test-key", …)` → `make_settings(` same kwargs `)`
- `tests/llm/test_orchestration_budget.py:14,22,29` — `RunBudget.from_settings(Settings(llm_max_tool_iters=1))` → `RunBudget.from_settings(make_settings(llm_max_tool_iters=1))` (same for the token-cap variants). Task 4 renames these kwargs again when the knobs lose their `llm_` env names.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_settings_factory.py -v` — Expected: PASS (3 tests)
Run: `uv run pytest -m "unit or integration"` — Expected: PASS (full suite; behavior unchanged)

- [ ] **Step 7: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'test: add hermetic settings factory and env bootstrap\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 2: Infra groups — `DatabaseSettings`, `RedisSettings`, `StorageSettings`

The three required vars all land here.

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/core/db.py`, `backend/app/jobs/queue.py`, `backend/migrations/env.py`, `backend/app/core/storage.py`, plus whichever of `backend/app/modules/books/service.py`, `backend/app/modules/downloads/service.py`, `backend/app/jobs/purge_downloads.py`, `backend/app/jobs/tasks.py`, `backend/app/modules/imports/jobs.py` the Step 4 grep finds
- Modify (attribute path only): `backend/tests/test_chapter_upsert.py`, `backend/tests/llm/test_book_summaries.py`, `backend/tests/llm/test_conversation_context.py`, `backend/tests/test_users_google.py`, `backend/tests/test_google_login_service.py`, `backend/tests/test_google_auth_api.py`, `backend/tests/test_download_ttl.py`, `backend/tests/test_settings_factory.py`
- Create: `backend/tests/test_config_groups.py`

**Interfaces:**
- Consumes: `make_settings` (Task 1).
- Produces: `class _GroupSettings(BaseSettings)` shared base; `DatabaseSettings.url` (env `DATABASE_URL`, **required**); `RedisSettings.url` (env `REDIS_URL`, **required**); `StorageSettings` with `endpoint` (env `MINIO_ENDPOINT`, **required**) plus defaulted `access_key`/`secret_key`/`bucket`/`secure`/`public_endpoint`/`signed_url_expires_seconds`/`download_job_ttl_hours`; root fields `Settings.database`, `Settings.redis`, `Settings.storage`. The flat `database_url`/`redis_url`/`minio_*`/`signed_url_expires_seconds`/`download_job_ttl_hours` root fields are **gone**.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_config_groups.py
"""Grouped settings: required infra vars, dev defaults, flat env aliases."""

import pytest
from pydantic import ValidationError

from app.core.config import DatabaseSettings, RedisSettings, StorageSettings
from tests.factories import make_settings


@pytest.mark.unit
def test_infra_urls_are_required(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("DATABASE_URL", "REDIS_URL", "MINIO_ENDPOINT"):
        monkeypatch.delenv(var, raising=False)
    for cls, field in (
        (DatabaseSettings, "database_url"),
        (RedisSettings, "redis_url"),
        (StorageSettings, "minio_endpoint"),
    ):
        with pytest.raises(ValidationError) as excinfo:
            cls(_env_file=None)  # type: ignore[call-arg]  # pydantic-settings runtime kwarg
        assert field in str(excinfo.value)


@pytest.mark.unit
def test_database_url_reads_flat_env_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db:5432/x")
    settings = DatabaseSettings(_env_file=None)  # type: ignore[call-arg]  # pydantic-settings runtime kwarg
    assert settings.url == "postgresql+asyncpg://u:p@db:5432/x"


@pytest.mark.unit
def test_factory_routes_flat_names_to_groups() -> None:
    settings = make_settings(database_url="postgresql+asyncpg://u:p@h:5432/d")
    assert settings.database.url == "postgresql+asyncpg://u:p@h:5432/d"
    assert settings.redis.url == "redis://localhost:6379/0"


@pytest.mark.unit
def test_storage_dev_defaults() -> None:
    settings = make_settings(minio_public_endpoint="media.local:9000")
    assert settings.storage.access_key == "rtm"
    assert settings.storage.bucket == "rtm"
    assert settings.storage.secure is False
    assert settings.storage.public_endpoint == "media.local:9000"
    assert settings.storage.download_job_ttl_hours == 24
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config_groups.py -v`
Expected: FAIL with `ImportError: cannot import name 'DatabaseSettings'`

- [ ] **Step 3: Implement the groups and rewire the root**

In `backend/app/core/config.py`, add `Field` to the `pydantic` import and,
above `Settings`:

```python
class _GroupSettings(BaseSettings):
    """Shared loading behavior for every settings group."""

    model_config = SettingsConfigDict(
        # Repo-root `.env` (native dev / secrets) plus optional `backend/.env`.
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


class DatabaseSettings(_GroupSettings):
    """Postgres connection. Supplied by docker-compose in containers."""

    url: str = Field(validation_alias="database_url")


class RedisSettings(_GroupSettings):
    """Redis / arq connection. Supplied by docker-compose in containers."""

    url: str = Field(validation_alias="redis_url")


class StorageSettings(_GroupSettings):
    """MinIO object storage + blob retention.

    `endpoint` is compose-supplied and required. The credentials keep dev
    defaults that match the compose-provisioned MinIO server; override both
    together (compose interpolates the same two variables into the server).
    """

    endpoint: str = Field(validation_alias="minio_endpoint")
    access_key: str = Field(default="rtm", validation_alias="minio_access_key")
    secret_key: str = Field(default="rtmsecret", validation_alias="minio_secret_key")
    bucket: str = Field(default="rtm", validation_alias="minio_bucket")
    secure: bool = Field(default=False, validation_alias="minio_secure")
    # Host used inside signed URLs (browser-facing). Defaults to endpoint.
    public_endpoint: str | None = Field(default=None, validation_alias="minio_public_endpoint")
    signed_url_expires_seconds: int = 3600
    # Retention for generated MP3 jobs and MinIO objects (hours).
    download_job_ttl_hours: int = 24
```

In `Settings`: delete the flat `database_url`, `redis_url`, six `minio_*`,
`signed_url_expires_seconds` and `download_job_ttl_hours` lines; add

```python
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
```

(If `uv run mypy .` flags the `default_factory`, apply the lambda+ignore
pattern from Global Constraints.)

- [ ] **Step 4: Update every consumer**

Find them: `grep -rn "\.database_url\|\.redis_url\|\.minio_\|\.signed_url_expires_seconds\|\.download_job_ttl_hours" app tests migrations`

Mapping: `settings.database_url` → `settings.database.url`;
`settings.redis_url` → `settings.redis.url`; `settings.minio_endpoint` →
`settings.storage.endpoint`; `minio_access_key` → `storage.access_key`;
`minio_secret_key` → `storage.secret_key`; `minio_bucket` →
`storage.bucket`; `minio_secure` → `storage.secure`;
`minio_public_endpoint` → `storage.public_endpoint`;
`settings.signed_url_expires_seconds` →
`settings.storage.signed_url_expires_seconds`;
`settings.download_job_ttl_hours` → `settings.storage.download_job_ttl_hours`.

Two non-mechanical edits:

- `tests/test_download_ttl.py` — replace the `MagicMock()` settings with the factory (a MagicMock's nested attribute would no longer return `24`):

```python
    from tests.factories import make_settings

    settings = make_settings(download_job_ttl_hours=24)
    monkeypatch.setattr(downloads_service, "get_settings", lambda: settings)
```

- `tests/test_settings_factory.py` — the two Task-1 assertions become `settings.redis.url` and `settings.storage.endpoint`; delete the "Flat access in Task 1" comment.

Re-run the grep; it must return no hits outside `config.py` and
`tests/factories.py`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_config_groups.py tests/test_settings_factory.py tests/test_storage_presign.py tests/test_download_ttl.py -v` — Expected: PASS
Run: `uv run pytest -m "unit or integration"` — Expected: PASS (integration proves alembic-in-conftest still migrates the test DB via `settings.database.url`)

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'refactor: extract Database, Redis and Storage settings groups\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 3: `AuthSettings` + `GoogleSsoSettings`

Auth keeps dev defaults; Google is the `.env`-only group.

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/core/security.py`, `backend/app/core/deps.py`, `backend/app/core/bootstrap.py`, `backend/app/modules/auth/router.py`, `backend/app/modules/auth/service.py`, `backend/app/modules/auth/google.py`
- Modify: `backend/tests/test_auth_api.py`, `backend/tests/test_google_config.py`, `backend/tests/test_google_auth_api.py`, `backend/tests/test_google_login_service.py`, `backend/tests/test_config_groups.py`
- **Do not touch** `backend/pyproject.toml` — the `"app/core/config.py" = ["S105"]` per-file-ignore must stay (config.py still holds dev secret literals).

**Interfaces:**
- Consumes: `_GroupSettings`, `make_settings`.
- Produces: `AuthSettings` with `jwt_secret`, `jwt_algorithm`, `jwt_expire_days`, `cookie_secure`, `cookie_samesite`, `admin_username`, `admin_password` — **all defaulted**; `GoogleSsoSettings` with `client_id/client_secret/redirect_uri: str | None = None`; root fields `Settings.auth`, `Settings.google`. The 503-when-unset contract is untouched (`GoogleOAuthClient.__init__` still raises `GoogleNotConfiguredError` on missing values).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_config_groups.py`)

```python
from app.core.config import AuthSettings, GoogleSsoSettings  # add to imports


@pytest.mark.unit
def test_auth_boots_on_dev_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("JWT_SECRET", "ADMIN_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    auth = AuthSettings(_env_file=None)  # type: ignore[call-arg]  # pydantic-settings runtime kwarg
    assert len(auth.jwt_secret) >= 32
    assert auth.admin_username == "admin"
    assert auth.admin_password
    assert auth.cookie_samesite == "lax"


@pytest.mark.unit
def test_google_sso_has_no_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"):
        monkeypatch.delenv(var, raising=False)
    google = GoogleSsoSettings(_env_file=None)  # type: ignore[call-arg]  # pydantic-settings runtime kwarg
    assert google.client_id is None
    assert google.client_secret is None
    assert google.redirect_uri is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config_groups.py -v`
Expected: FAIL with `ImportError: cannot import name 'AuthSettings'`

- [ ] **Step 3: Implement groups + update consumers**

Add to `config.py`:

```python
class AuthSettings(_GroupSettings):
    """Session JWT, cookie flags, seeded admin account.

    Dev-correct defaults: a real deployment overrides JWT_SECRET,
    ADMIN_PASSWORD and COOKIE_SECURE through real environment variables.
    """

    jwt_secret: str = "dev-only-change-me-to-a-long-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    admin_username: str = "admin"
    admin_password: str = "changeme123"


class GoogleSsoSettings(_GroupSettings):
    """Google SSO (server-side authorization-code flow).

    `.env` only — never in docker-compose.yml. All three are required for
    login to work; the endpoints return 503 while any is unset.
    """

    client_id: str | None = Field(default=None, validation_alias="google_client_id")
    client_secret: str | None = Field(default=None, validation_alias="google_client_secret")
    # Browser-facing callback, e.g. http://localhost:5173/api/auth/google/callback
    redirect_uri: str | None = Field(default=None, validation_alias="google_redirect_uri")
```

In `Settings`: delete the flat `jwt_*`, `cookie_*`, `admin_*`, `google_*`
lines; add `auth: AuthSettings = Field(default_factory=AuthSettings)` and
`google: GoogleSsoSettings = Field(default_factory=GoogleSsoSettings)`.

Update consumers — find them:
`grep -rn "\.jwt_secret\|\.jwt_algorithm\|\.jwt_expire_days\|\.cookie_secure\|\.cookie_samesite\|\.admin_username\|\.admin_password\|\.google_client_id\|\.google_client_secret\|\.google_redirect_uri" app tests`
Mapping: `settings.jwt_*` → `settings.auth.jwt_*`, `settings.cookie_*` →
`settings.auth.cookie_*`, `settings.admin_*` → `settings.auth.admin_*`,
`settings.google_client_id` → `settings.google.client_id`,
`settings.google_client_secret` → `settings.google.client_secret`,
`settings.google_redirect_uri` → `settings.google.redirect_uri`.

Known test-specific edits:
- `tests/test_google_config.py` — assertions become `settings.google.client_id is None` (etc.).
- `tests/test_google_auth_api.py` — `monkeypatch.setattr(settings, "google_client_id", "test-client-id")` → `monkeypatch.setattr(settings.google, "client_id", "test-client-id")` (same for the other two and for the unconfigured-503 test).
- `tests/test_auth_api.py`, `tests/test_google_login_service.py` — `settings.admin_username` → `settings.auth.admin_username`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config_groups.py tests/test_security.py tests/test_auth_api.py tests/test_google_config.py tests/test_google_auth_api.py -v` — Expected: PASS
Run: `uv run pytest -m "unit or integration"` — Expected: PASS

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'refactor: extract AuthSettings and GoogleSsoSettings\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 4: `LlmSettings` + `LlmRuntimeSettings` (code-only knobs)

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py` (delete `_validate_llm_startup` and its call)
- Modify: LLM consumers — `backend/app/modules/llm/service.py`, `backend/app/modules/llm/router.py`, `backend/app/modules/llm/providers/*`, the orchestration budget module (`RunBudget.from_settings`), HITL/context/summary code, `backend/app/modules/tools/definitions/summarize_book.py` (Step 3 grep is authoritative)
- Modify: `backend/tests/llm/test_orchestration_budget.py` and any other test passing an `llm_*` runtime knob to `make_settings`
- Modify: `backend/tests/test_config_groups.py`

**Interfaces:**
- Consumes: `_GroupSettings`, `make_settings`.
- Produces: `LlmSettings` with `enabled` (env `LLM_ENABLED`), `provider` (`LLM_PROVIDER`), `model` (`LLM_MODEL`), `gemini_api_key` (`.env` only, no default), `timeout_seconds`, `max_output_tokens`, `max_retries`, `langfuse_enabled`, plus a `model_validator` enforcing the key when enabled; `LlmRuntimeSettings` with the 12 orchestration knobs as **plain defaulted fields with no `validation_alias`** — read only via `settings.llm_runtime`. Root fields `Settings.llm`, `Settings.llm_runtime`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_config_groups.py`)

```python
from app.core.config import LlmRuntimeSettings  # add to imports


@pytest.mark.unit
def test_llm_enabled_requires_gemini_key() -> None:
    with pytest.raises(ValidationError, match="GEMINI_API_KEY"):
        make_settings(llm_enabled=True, gemini_api_key=None)


@pytest.mark.unit
def test_llm_disabled_allows_missing_key() -> None:
    settings = make_settings(llm_enabled=False, gemini_api_key=None)
    assert settings.llm.enabled is False


@pytest.mark.unit
def test_llm_runtime_defaults() -> None:
    runtime = make_settings(max_tool_iters=2).llm_runtime
    assert runtime.max_tool_iters == 2
    assert runtime.max_external_calls == 3
    assert runtime.max_turn_tokens_in == 64_000
    assert runtime.max_turn_tokens_out == 8_192
    assert runtime.max_turn_cost_usd == 0.05
    assert runtime.run_deadline_seconds == 60
    assert runtime.context_recent_messages == 10
    assert runtime.summary_trigger_tokens == 12_000
    assert runtime.summary_max_output_tokens == 1_200
    assert runtime.assistant_mode == "internal_only"
    assert runtime.hitl_ttl_seconds == 900
    assert runtime.max_hitl_rounds == 3


@pytest.mark.unit
def test_llm_runtime_ignores_legacy_env_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """The 12 knobs are code-only until the runtime-config layer lands."""
    monkeypatch.setenv("LLM_MAX_TOOL_ITERS", "99")
    monkeypatch.setenv("LLM_ASSISTANT_MODE", "external_allowed")
    runtime = LlmRuntimeSettings(_env_file=None)  # type: ignore[call-arg]  # pydantic-settings runtime kwarg
    assert runtime.max_tool_iters == 6
    assert runtime.assistant_mode == "internal_only"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config_groups.py -v`
Expected: FAIL — `test_llm_enabled_requires_gemini_key` with `Failed: DID NOT RAISE` (no validator yet; flat kwargs still route to the root), the others with `ImportError` / `AttributeError: 'Settings' object has no attribute 'llm_runtime'`

- [ ] **Step 3: Implement groups + update consumers**

Add to `config.py` (`model_validator` joins the `pydantic` import):

```python
class LlmSettings(_GroupSettings):
    """LLM provider config (Milestone B). Off by default.

    GEMINI_API_KEY is `.env` only — no default, never in docker-compose.yml.
    """

    enabled: bool = Field(default=False, validation_alias="llm_enabled")
    provider: str = Field(default="gemini", validation_alias="llm_provider")
    model: str = Field(default="gemini-3.5-flash-lite", validation_alias="llm_model")
    gemini_api_key: str | None = None
    timeout_seconds: int = Field(default=30, validation_alias="llm_timeout_seconds")
    max_output_tokens: int = Field(default=2048, validation_alias="llm_max_output_tokens")
    max_retries: int = Field(default=2, validation_alias="llm_max_retries")
    langfuse_enabled: bool = False

    @model_validator(mode="after")
    def _require_key_when_enabled(self) -> "LlmSettings":
        if self.enabled and self.provider == "gemini" and not self.gemini_api_key:
            msg = "GEMINI_API_KEY is required when LLM_ENABLED=true"
            raise ValueError(msg)
        return self


class LlmRuntimeSettings(_GroupSettings):
    """Orchestration budgets and knobs (B3). Exceeding any one ends the run.

    Deliberately code-only: these have no env names, so they cannot be
    tuned per-deployment yet. They move to a DB-backed dynamic config layer
    with per-tier overrides next (see the runtime-config plan). Read them
    only via `settings.llm_runtime` so extraction stays a one-object swap.
    """

    max_tool_iters: int = 6
    max_external_calls: int = 3
    max_turn_tokens_in: int = 64_000
    max_turn_tokens_out: int = 8_192
    max_turn_cost_usd: float = 0.05
    run_deadline_seconds: int = 60
    context_recent_messages: int = 10
    summary_trigger_tokens: int = 12_000
    summary_max_output_tokens: int = 1_200
    assistant_mode: str = "internal_only"
    # HITL: how long a pending confirmation stays valid; max pauses per turn.
    hitl_ttl_seconds: int = 900
    max_hitl_rounds: int = 3
```

In `Settings`: delete all flat `llm_*`, `gemini_api_key`, `langfuse_enabled`
lines; add `llm: LlmSettings = Field(default_factory=LlmSettings)` and
`llm_runtime: LlmRuntimeSettings = Field(default_factory=LlmRuntimeSettings)`.

In `app/main.py`: delete `_validate_llm_startup` entirely and the
`_validate_llm_startup(settings)` call in `create_app` (the `LlmSettings`
validator now covers it in every process, worker included). Keep the
provider-level `LlmConfigError` checks in `modules/llm/` untouched.

Update consumers — find them:
`grep -rn "\.llm_\|\.gemini_api_key\|\.langfuse_enabled" app tests`
Mapping: provider config → `settings.llm.<name-without-llm_-prefix>`
(`llm_enabled`→`llm.enabled`, `gemini_api_key`→`llm.gemini_api_key`,
`langfuse_enabled`→`llm.langfuse_enabled`); the 12 budget knobs →
`settings.llm_runtime.<name-without-llm_-prefix>`.
`RunBudget.from_settings(settings)` keeps its signature — only its body's
attribute reads change.

Also drop the `llm_` prefix from any runtime-knob **kwarg** passed to the
factory (the fields no longer have an alias, so the factory routes them by
bare field name):
`grep -rn "make_settings(.*llm_max\|make_settings(.*llm_assistant_mode\|make_settings(.*llm_context\|make_settings(.*llm_summary\|make_settings(.*llm_hitl\|make_settings(.*llm_run_deadline" tests`
e.g. `make_settings(llm_max_tool_iters=1)` → `make_settings(max_tool_iters=1)`.
A missed one fails loudly with `ValueError: Unknown settings override`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config_groups.py tests/llm -v` — Expected: PASS
Run: `uv run pytest -m "unit or integration"` — Expected: PASS

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'refactor: extract LlmSettings and code-only LlmRuntimeSettings\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 5: `AppSettings` + `ScrapeSettings` + `AudioSettings`; finalize the root

All three are pure code-default groups. Mechanical; mypy catches misses.

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py`, `backend/app/modules/health/router.py`, `backend/app/core/fetcher.py`, `backend/app/modules/scraping/worker.py`, `backend/app/modules/audio/providers/sapi.py`
- Modify: `backend/tests/test_audio_providers.py`, `backend/tests/test_config_groups.py`

**Interfaces:**
- Produces: `AppSettings` (`name`, `env`, `debug`, `api_prefix`, `cors_origins`), `ScrapeSettings` (`timeout_seconds`, `max_bytes`, `delay_seconds`), `AudioSettings` (`sapi_proxy_enabled`); root fields `Settings.app`, `Settings.scrape`, `Settings.audio`. The root `Settings` then contains **only** the ten group fields — no flat fields remain.
- `cors_origins` gains the third localhost origin that compose used to inject, so compose no longer sets it.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_config_groups.py`)

```python
from pydantic_settings import BaseSettings  # add to imports

from app.core.config import Settings  # add to imports


@pytest.mark.unit
def test_app_scrape_audio_defaults() -> None:
    settings = make_settings(app_name="RTM test", scrape_delay_seconds=0.5)
    assert settings.app.name == "RTM test"
    assert settings.app.api_prefix == "/api"
    # The dockerized frontend origin must be covered without compose help.
    assert "http://localhost" in settings.app.cors_origins
    assert settings.scrape.timeout_seconds == 20
    assert settings.scrape.max_bytes == 2_097_152
    assert settings.scrape.delay_seconds == 0.5
    assert settings.audio.sapi_proxy_enabled is True


@pytest.mark.unit
def test_root_is_groups_only() -> None:
    for field in Settings.model_fields.values():
        annotation = field.annotation
        assert isinstance(annotation, type)
        assert issubclass(annotation, BaseSettings)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config_groups.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'app'`

- [ ] **Step 3: Implement + update consumers**

Add to `config.py` (`AppSettings` first, above `DatabaseSettings`):

```python
class AppSettings(_GroupSettings):
    """App identity and HTTP surface."""

    name: str = Field(default="RTM v3", validation_alias="app_name")
    env: str = Field(default="local", validation_alias="app_env")
    debug: bool = False
    api_prefix: str = "/api"
    # Native dev (:5173), dockerized frontend (:3000), and port-80 host.
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost",
    ]


class ScrapeSettings(_GroupSettings):
    """Outbound fetch limits (central fetch service / SSRF guard)."""

    timeout_seconds: int = Field(default=20, validation_alias="scrape_timeout_seconds")
    max_bytes: int = Field(default=2_097_152, validation_alias="scrape_max_bytes")  # 2 MB
    delay_seconds: float = Field(default=1.5, validation_alias="scrape_delay_seconds")


class AudioSettings(_GroupSettings):
    """TTS provider toggles."""

    sapi_proxy_enabled: bool = True
```

In `Settings`: delete the flat `app_name`, `app_env`, `debug`, `api_prefix`,
`cors_origins`, `scrape_*` and `sapi_proxy_enabled` lines. The finished root:

```python
class Settings(BaseSettings):
    """Runtime configuration, composed of env-loaded groups."""

    model_config = SettingsConfigDict(extra="ignore")

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    google: GoogleSsoSettings = Field(default_factory=GoogleSsoSettings)
    scrape: ScrapeSettings = Field(default_factory=ScrapeSettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    llm: LlmSettings = Field(default_factory=LlmSettings)
    llm_runtime: LlmRuntimeSettings = Field(default_factory=LlmRuntimeSettings)
```

(Apply the lambda+ignore pattern from Global Constraints only where mypy
demands it. `Settings` no longer needs `env_file` in its own config — the
groups load it; drop `_env_file=None` from the factory's root call if mypy
now flags the ignore as unused.)

Update consumers — find them:
`grep -rn "\.app_name\|\.app_env\|settings\.debug\|\.api_prefix\|\.cors_origins\|\.scrape_\|\.sapi_proxy_enabled" app tests`
- `app/main.py` — `settings.debug` → `settings.app.debug`, `settings.app_name` → `settings.app.name`, `settings.cors_origins` → `settings.app.cors_origins`, all twelve `prefix=settings.api_prefix` → `prefix=settings.app.api_prefix`
- `app/modules/health/router.py` — `settings.app_name` → `settings.app.name`
- `app/core/fetcher.py`, `app/modules/scraping/worker.py` — `settings.scrape_*` → `settings.scrape.*` (prefix dropped)
- `app/modules/audio/providers/sapi.py` — `settings.sapi_proxy_enabled` → `settings.audio.sapi_proxy_enabled`

In `tests/test_audio_providers.py`, both `MagicMock(sapi_proxy_enabled=True)`
fakes become the factory (a nested attribute on a bare MagicMock would
return a Mock, not `True`):

```python
    from tests.factories import make_settings

    monkeypatch.setattr(
        "app.modules.audio.providers.sapi.get_settings",
        lambda: make_settings(sapi_proxy_enabled=True),
    )
```

Final audit (must return **no hits** outside `config.py` aliases and
`tests/factories.py` dummy keys):
`grep -rn "\.database_url\|\.redis_url\|\.minio_\|\.jwt_secret\|\.admin_password\|\.google_client\|\.scrape_\|\.sapi_proxy\|\.llm_\|\.app_name\|\.gemini_api_key" app migrations`

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config_groups.py tests/test_settings_factory.py tests/test_audio_providers.py -v` — Expected: PASS
Run: `uv run pytest -m "unit or integration"` — Expected: PASS

- [ ] **Step 5: Native boot smoke**

```bash
uv run python -c "from app.core.config import get_settings; s = get_settings(); print(s.app.name, s.database.url.split('@')[-1])"
uv run python -c "import app.jobs.worker; print('worker imports ok')"
uv run python -c "import app.main; print('app imports ok')"
```

Expected: all three print. Alembic's `env.py` is already exercised by the
integration run (conftest migrates the test DB through it).

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'refactor: extract App, Scrape and Audio settings and finalize grouped root\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 6: docker-compose — infra values only

**Files:**
- Modify: `docker-compose.yml` (repo root)

**Interfaces:**
- Produces: a single `x-app-env` block holding **only what compose produces or provisions**, merged into `backend` and `worker`; secrets reach containers via `env_file: [.env]`; everything else comes from code defaults. No `${VAR:?}` guards — code fail-fast covers the three required vars.

- [ ] **Step 1: Add the anchor and rewrite both env blocks**

At the top of `docker-compose.yml` (before `services:`):

```yaml
# Only values compose itself produces or provisions. Everything else has a
# dev default in backend/app/core/config.py; real secrets (GOOGLE_*,
# GEMINI_API_KEY) live in .env and arrive via env_file below.
x-app-env: &app-env
  DATABASE_URL: postgresql+asyncpg://${DB_USER:-rtm}:${DB_PASSWORD:-rtm}@postgres:5432/${DB_NAME:-rtm}
  REDIS_URL: redis://redis:6379/0
  MINIO_ENDPOINT: minio:9000
  MINIO_PUBLIC_ENDPOINT: localhost:9000
  # Must match the MinIO server's root credentials, provisioned from the
  # same two variables in the `minio` service.
  MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY:-rtm}
  MINIO_SECRET_KEY: ${MINIO_SECRET_KEY:-rtmsecret}
```

Replace the `backend` service's entire `environment:` block with:

```yaml
    env_file:
      - .env
    environment:
      <<: *app-env
```

Replace the `worker` service's entire `environment:` block with the same
four lines. Everything else that used to be listed — `APP_ENV`,
`CORS_ORIGINS`, `JWT_SECRET`, `ADMIN_*`, `COOKIE_SECURE`,
`SAPI_PROXY_ENABLED`, `MINIO_BUCKET`, `MINIO_SECURE`, all `GOOGLE_*`, all
`LLM_*`, `GEMINI_API_KEY`, `LANGFUSE_ENABLED` — is **deleted**: the first
group is now code defaults, the rest arrives through `env_file`.

Leave `postgres`, `minio`, `minio-init` and `frontend` service definitions
untouched.

Two behaviors this relies on:
- `environment:` takes precedence over `env_file:`, so compose's service
  hostnames win even if a stale `DATABASE_URL` sits in `.env`.
- A missing `.env` makes compose refuse to start, which is the desired
  signal since the SSO/LLM secrets have nowhere else to come from.

- [ ] **Step 2: Validate the merge**

```bash
docker compose config > /dev/null && echo "compose config OK"
docker compose config | grep -c "MINIO_ENDPOINT"
```

Expected: `compose config OK`; the grep count is `2` (backend + worker both
inherit the shared block).

- [ ] **Step 3: Boot smoke**

```bash
docker compose up -d --build backend worker
docker compose ps
docker compose logs --tail 20 backend worker
docker compose down
```

Expected: backend reports healthy (its entrypoint auto-runs
`alembic upgrade head`, proving Alembic boots on grouped settings in the
container); worker runs with no settings `ValidationError`.

- [ ] **Step 4: Commit**

```bash
printf 'chore: reduce compose app env to infra values via x-app-env anchor\n' > /tmp/msg.txt
git add docker-compose.yml
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 7: `.env.example` + CLAUDE.md

**Files:**
- Modify: `.env.example`, `CLAUDE.md`, `README.md` (all repo root)

- [ ] **Step 1: Reduce `.env.example` to the two things that belong in `.env`**

Replace the whole file with:

```bash
# ─── Real secrets — .env ONLY ────────────────────────────────────────────
# No code defaults, and deliberately absent from docker-compose.yml (they
# reach containers through `env_file`). All optional: without them Google
# SSO endpoints return 503 and LLM features stay off.
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:5173/api/auth/google/callback
GEMINI_API_KEY=

# ─── Infra URLs — NATIVE DEV ONLY ────────────────────────────────────────
# Required, no code default. Set these ONLY when running the API, worker or
# alembic natively (uv run uvicorn / arq / alembic).
#
# FORBIDDEN when the server/worker run under docker-compose: compose supplies
# its own service-hostname values. A localhost value here is overridden
# inside the container, so leaving it in only invites confusion about which
# database you are actually talking to.
DATABASE_URL=postgresql+asyncpg://rtm:rtm@localhost:5432/rtm
REDIS_URL=redis://localhost:6379/0
MINIO_ENDPOINT=localhost:9000

# ─── Optional overrides ──────────────────────────────────────────────────
# Everything else has a dev-correct default in backend/app/core/config.py
# (JWT_SECRET, ADMIN_*, COOKIE_*, CORS_ORIGINS, MINIO_BUCKET, SCRAPE_*,
# LLM_*, …). Uncomment only to change local behavior. MinIO credentials are
# read by both the app and the compose-provisioned MinIO server, so change
# them together or not at all.
#LLM_ENABLED=true
#MINIO_ACCESS_KEY=rtm
#MINIO_SECRET_KEY=rtmsecret
#TEST_DATABASE_URL=postgresql+asyncpg://rtm:rtm@localhost:5432/rtm_test
```

Note: the 12 `llm_runtime` knobs are intentionally absent — they no longer
read env at all.

- [ ] **Step 2: Update CLAUDE.md**

In the "Full stack" section, replace:

> Config comes from root `.env` (copy `.env.example` — it's the canonical
> variable list). … When adding a setting, update `Settings`
> (pydantic-settings in `app/core/config.py`), `.env.example`, compose, and
> README together.

with:

> Every setting has exactly one home — never mirror a value across two.
> Default in the matching group class in `app/core/config.py` (dev-correct,
> flat env name via `validation_alias`) for anything tunable; `.env` only
> for real secrets (`GOOGLE_*`, `GEMINI_API_KEY` — these have no default and
> must never appear in `docker-compose.yml`); the shared `x-app-env` block in
> `docker-compose.yml` only for values compose produces or provisions
> (`DATABASE_URL`, `REDIS_URL`, `MINIO_*`). `DATABASE_URL`/`REDIS_URL`/
> `MINIO_ENDPOINT` are required with no default; set them in `.env` for
> native dev only, never when running under compose. In tests, build settings
> with `tests/factories.py::make_settings(**flat_overrides)` — never
> construct `Settings()` directly.

- [ ] **Step 3: Point the README at it**

Replace the README's env-variable bullet list with a short pointer: settings
are grouped sub-models in `backend/app/core/config.py` (`app`, `database`,
`redis`, `storage`, `auth`, `google`, `scrape`, `audio`, `llm`,
`llm_runtime`); `.env.example` documents the only two categories that belong
in `.env`; the placement rule lives in CLAUDE.md. Do not re-enumerate
variables — the group classes are the list.

- [ ] **Step 4: Fresh-checkout verification**

The whole `.env.example` reduction depends on the code defaults being
local-correct, so prove it:

```bash
cd backend && env -i PATH="$PATH" HOME="$HOME" \
  DATABASE_URL=postgresql+asyncpg://rtm:rtm@localhost:5432/rtm \
  REDIS_URL=redis://localhost:6379/0 \
  MINIO_ENDPOINT=localhost:9000 \
  uv run python -c "from app.core.config import get_settings; s=get_settings(); print(s.app.cors_origins, s.storage.bucket, s.auth.admin_username)"
```

Expected: prints without error using only the three required vars — nothing
else needed from `.env`. If any group raises, that field's default is
production-shaped rather than local-shaped; fix the default.

- [ ] **Step 5: Full final gates + commit**

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
cd .. && printf 'docs: document one-home config placement rule and trim .env.example\n' > /tmp/msg.txt
git add .env.example README.md CLAUDE.md
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```
