# Config Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the flat 49-field `Settings` into composed per-group `BaseSettings` sub-models with unchanged env var names, fail-fast required secrets/per-env values, no secret defaults in code, and a de-duplicated docker-compose env block.

**Architecture:** Each settings group is its own `BaseSettings` subclass (fields keep the legacy flat env names via field name or `Field(validation_alias=...)`); the root `Settings` composes them with `default_factory`. Groups are extracted one at a time (root keeps the not-yet-moved flat fields), so every task is independently green. A shared hermetic test factory (`make_settings`) accepts legacy flat kwargs and routes them to groups by introspection, so most test call sites are migrated once (Task 1) and survive every later move untouched.

**Tech Stack:** pydantic-settings 2.x (composed `BaseSettings`, `validation_alias`), pydantic v2 `model_validator`, python-dotenv (ships with pydantic-settings), docker-compose YAML anchors.

**Spec:** `docs/superpowers/specs/2026-07-29-config-restructure-design.md` (full field classification table lives there).

## Global Constraints

- **Sequencing:** start ONLY after `feature/sso` is merged to `main`. Verify before Task 1: `git log --oneline main | head -20` shows the SSO work and `backend/tests/test_google_config.py` exists. Work on a new branch `feature/config-restructure` off `main`.
- Env var names never change: `DATABASE_URL`, `REDIS_URL`, `MINIO_*`, `JWT_SECRET`, `ADMIN_*`, `GOOGLE_*`, `SCRAPE_*`, `SAPI_PROXY_ENABLED`, `SIGNED_URL_EXPIRES_SECONDS`, `DOWNLOAD_JOB_TTL_HOURS`, `LLM_*`, `GEMINI_API_KEY`, `LANGFUSE_ENABLED`, `APP_*`, `DEBUG`, `API_PREFIX`, `CORS_ORIGINS`, `COOKIE_*`, `JWT_ALGORITHM`, `JWT_EXPIRE_DAYS`. No `env_nested_delimiter`.
- Google SSO 503 contract: `google.client_id/client_secret/redirect_uri` stay `Optional[str] = None`. No startup validation for them, ever.
- All backend gates must pass per task (run from `backend/`): `uv run ruff check . --fix && uv run ruff format .`, then `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`, `uv run pytest -m "unit or integration"`. Integration tests need Postgres/Redis/MinIO and `TEST_DATABASE_URL` pointing at a separate test DB.
- Commit with `bash scripts/git-commit-clean.sh /tmp/msg.txt` (write message to `/tmp/msg.txt` first). **Never** add `Co-authored-by`/`Made-with` trailers. Verify with `git log -1 --format=%B`.
- Ruff limits: complexity ≤10, statements ≤20, branches ≤6, returns ≤4, args ≤6. `# type: ignore[code]`/`# noqa: RULE` only with a specific code and a reason comment. mypy runs with `warn_unused_ignores` — add an ignore only when mypy actually reports the error, and remove it if mypy flags it unused.
- Behavior-preserving: no route/service behavior changes. The only accepted behavior deltas (per spec): missing required env now crashes startup; the LLM key check fires at `get_settings()` in every process (worker included) as a pydantic `ValidationError` instead of `LlmConfigError` in the API only.
- `get_settings()` stays `@lru_cache`'d with the same signature. `Depends(get_settings)` call sites untouched.
- **pydantic mypy plugin note (applies to Tasks 2–7):** the plugin synthesizes `__init__` from fields, so it may flag `Field(default_factory=GroupCls)` for groups with required fields, and it WILL flag `GroupCls(_env_file=None)`. Pattern: write the plain form first, run `uv run mypy .`, and only where it errors use `Field(default_factory=lambda: GroupCls())  # type: ignore[call-arg]  # values come from env` / `GroupCls(_env_file=None)  # type: ignore[call-arg]  # pydantic-settings runtime kwarg`.

---

### Task 1: Test scaffolding — env bootstrap + hermetic settings factory

**Files:**
- Modify: `backend/tests/conftest.py` (top-of-file env bootstrap)
- Create: `backend/tests/factories.py`
- Create: `backend/tests/test_settings_factory.py`
- Modify (migrate direct `Settings(...)` constructions to the factory): `backend/tests/test_security.py`, `backend/tests/test_storage_presign.py`, `backend/tests/test_google_config.py`, `backend/tests/test_google_oauth.py`, `backend/tests/llm/test_chat.py`, `backend/tests/llm/test_conversation_context.py`, `backend/tests/llm/test_hitl.py`, `backend/tests/llm/test_orchestration.py`, `backend/tests/llm/test_orchestration_budget.py`

**Interfaces:**
- Produces: `make_settings(**overrides: Any) -> Settings` in `tests/factories.py` — accepts **legacy flat env-style names** (`jwt_secret=...`, `llm_max_tool_iters=1`, `minio_endpoint=...`), builds a hermetic `Settings` (no dotenv), fills required values with safe dummies, raises `ValueError` on unknown keys. Every later task relies on this routing surviving field moves unchanged.
- Produces: conftest guarantees the seven required env vars exist before any `app.core.config` import (root `.env` values first, then dummies), and still forces `DATABASE_URL` to the test DB.

- [ ] **Step 1: Write the failing factory tests**

```python
# backend/tests/test_settings_factory.py
"""The hermetic settings factory: dummies, overrides, unknown-key rejection."""

import pytest

from tests.factories import make_settings


@pytest.mark.unit
def test_factory_builds_settings_with_dummy_required_values() -> None:
    settings = make_settings()
    # Flat access in Task 1; later tasks move these behind groups and
    # update these assertions in the same commit as the move.
    assert settings.jwt_secret == "test-secret-with-enough-length-32b"
    assert settings.minio_access_key == "rtm"


@pytest.mark.unit
def test_factory_override_wins() -> None:
    settings = make_settings(jwt_secret="another-secret-with-enough-len-32")
    assert settings.jwt_secret == "another-secret-with-enough-len-32"


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
to them by `validation_alias`. In Task 1 there are no groups yet, so every
key falls through to the root — the same code then absorbs Tasks 2–7 with
zero factory changes.

```python
# backend/tests/factories.py
"""Hermetic `Settings` construction for tests.

`Settings` is (being) composed of per-group `BaseSettings` classes that each
read env + dotenv on their own, so `Settings(_env_file=None)` alone is not
hermetic. This factory builds every group with `_env_file=None`, fills
required fields with safe dummies, and routes flat legacy-named overrides
(`jwt_secret=...`, `llm_max_tool_iters=...`) to the right group.

Note: os.environ still takes part for fields NOT passed explicitly (same as
direct `Settings(...)` construction always did); conftest pins the required
vars, so results are deterministic.
"""

from __future__ import annotations

from typing import Any

from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings

from app.core.config import Settings

# Values only need to be well-formed; factory-built Settings never open
# real connections (DB fixtures use get_settings(), which conftest pins).
_REQUIRED_DUMMIES: dict[str, Any] = {
    "database_url": "postgresql+asyncpg://rtm:rtm@localhost:5432/rtm_test",
    "redis_url": "redis://localhost:6379/0",
    "minio_endpoint": "localhost:9000",
    "minio_access_key": "rtm",
    "minio_secret_key": "rtmsecret",
    "jwt_secret": "test-secret-with-enough-length-32b",
    "admin_password": "test-admin-password",
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

# 2) Safe dummies so required settings exist on a clean checkout (no .env).
_TEST_ENV_DEFAULTS = {
    "REDIS_URL": "redis://localhost:6379/0",
    "MINIO_ENDPOINT": "localhost:9000",
    "MINIO_ACCESS_KEY": "rtm",
    "MINIO_SECRET_KEY": "rtmsecret",
    "JWT_SECRET": "test-secret-with-enough-length-32b",
    "ADMIN_PASSWORD": "test-admin-password",
}
for _key, _value in _TEST_ENV_DEFAULTS.items():
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
- `tests/test_storage_presign.py:16` — `Settings(minio_endpoint=…, minio_public_endpoint=…, minio_access_key=…, minio_secret_key=…, minio_bucket=…, minio_secure=…)` → `make_settings(` same kwargs `)`
- `tests/test_google_config.py:9` — `Settings(_env_file=None)  # type: ignore[call-arg]` → `make_settings()` (keeps asserting the three google fields are `None` — dummies never set them)
- `tests/test_google_oauth.py` `_settings()` helper — `Settings(_env_file=None, google_client_id=…, …)` → `make_settings(google_client_id=CLIENT_ID, google_client_secret="test-secret", google_redirect_uri="http://localhost:5173/api/auth/google/callback")`
- `tests/llm/test_chat.py:68`, `tests/llm/test_conversation_context.py:34`, `tests/llm/test_hitl.py:49`, `tests/llm/test_orchestration.py:93,131,164,195` — `Settings(llm_enabled=True, gemini_api_key="test-key", …)` → `make_settings(` same kwargs `)`
- `tests/llm/test_orchestration_budget.py:14,22,29` — `RunBudget.from_settings(Settings(llm_max_tool_iters=1))` → `RunBudget.from_settings(make_settings(llm_max_tool_iters=1))` (same for the token-cap variants)

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

### Task 2: `DatabaseSettings` + `RedisSettings` (first fail-fast groups)

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/core/db.py`, `backend/app/jobs/queue.py`, `backend/migrations/env.py`
- Modify (attribute path only): `backend/tests/test_chapter_upsert.py`, `backend/tests/llm/test_book_summaries.py`, `backend/tests/llm/test_conversation_context.py`, plus the SSO-branch test fixtures that read `get_settings().database_url` (`tests/test_users_google.py`, `tests/test_google_login_service.py`, `tests/test_google_auth_api.py`)
- Create: `backend/tests/test_config_groups.py`

**Interfaces:**
- Consumes: `make_settings` (Task 1).
- Produces: `class _GroupSettings(BaseSettings)` shared base; `DatabaseSettings.url: str` (env `DATABASE_URL`, **required**); `RedisSettings.url: str` (env `REDIS_URL`, **required**); root fields `Settings.database`, `Settings.redis`. Flat `database_url`/`redis_url` root fields are **gone**.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_config_groups.py
"""Grouped settings: fail-fast required fields + flat env-name aliases."""

import pytest
from pydantic import ValidationError

from app.core.config import DatabaseSettings, RedisSettings
from tests.factories import make_settings


@pytest.mark.unit
def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError) as excinfo:
        DatabaseSettings(_env_file=None)  # type: ignore[call-arg]  # pydantic-settings runtime kwarg
    assert "database_url" in str(excinfo.value)


@pytest.mark.unit
def test_database_url_reads_flat_env_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db:5432/x")
    settings = DatabaseSettings(_env_file=None)  # type: ignore[call-arg]  # pydantic-settings runtime kwarg
    assert settings.url == "postgresql+asyncpg://u:p@db:5432/x"


@pytest.mark.unit
def test_redis_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    with pytest.raises(ValidationError) as excinfo:
        RedisSettings(_env_file=None)  # type: ignore[call-arg]  # pydantic-settings runtime kwarg
    assert "redis_url" in str(excinfo.value)


@pytest.mark.unit
def test_factory_routes_flat_names_to_groups() -> None:
    settings = make_settings(database_url="postgresql+asyncpg://u:p@h:5432/d")
    assert settings.database.url == "postgresql+asyncpg://u:p@h:5432/d"
    assert settings.redis.url == "redis://localhost:6379/0"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config_groups.py -v`
Expected: FAIL with `ImportError: cannot import name 'DatabaseSettings'`

- [ ] **Step 3: Implement the groups and rewire the root**

In `backend/app/core/config.py`, add imports (`Field` from `pydantic`) and,
above `Settings`:

```python
class _GroupSettings(BaseSettings):
    """Shared loading behavior for every settings group."""

    model_config = SettingsConfigDict(
        # Repo-root `.env` (compose / local) plus optional `backend/.env` override.
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


class DatabaseSettings(_GroupSettings):
    """Postgres connection (core/db, alembic)."""

    url: str = Field(validation_alias="database_url")


class RedisSettings(_GroupSettings):
    """Redis / arq connection."""

    url: str = Field(validation_alias="redis_url")
```

In `Settings`: delete the flat `database_url` and `redis_url` lines and add
(where they were):

```python
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
```

(If `uv run mypy .` flags the `default_factory`, apply the lambda+ignore
pattern from Global Constraints.)

- [ ] **Step 4: Update every consumer**

Find them: `grep -rn "\.database_url\|\.redis_url" app tests migrations`

- `app/core/db.py` — `settings.database_url` → `settings.database.url`
- `app/jobs/queue.py:17` — `get_settings().redis_url` → `get_settings().redis.url`
- `migrations/env.py:38` — `settings.database_url` → `settings.database.url`
- Every test fixture hit (`tests/test_chapter_upsert.py`, `tests/llm/test_book_summaries.py`, `tests/llm/test_conversation_context.py`, `tests/test_users_google.py`, `tests/test_google_login_service.py`, `tests/test_google_auth_api.py`) — `get_settings().database_url` → `get_settings().database.url`

Re-run the grep; it must return no hits outside `config.py`/`factories.py`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_config_groups.py -v` — Expected: PASS (4 tests)
Run: `uv run pytest -m "unit or integration"` — Expected: PASS (integration proves alembic-in-conftest still migrates the test DB via `settings.database.url`)

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'refactor: extract DatabaseSettings and RedisSettings (fail-fast, no defaults)\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 3: `StorageSettings` (MinIO + blob retention)

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/core/storage.py`, `backend/app/modules/books/service.py`, `backend/app/modules/downloads/service.py`, `backend/app/jobs/purge_downloads.py`, `backend/app/jobs/tasks.py`, `backend/app/modules/imports/jobs.py` (whichever of these read the fields — the grep in Step 3 is authoritative)
- Modify: `backend/tests/test_download_ttl.py`
- Modify: `backend/tests/test_config_groups.py` (add cases)

**Interfaces:**
- Consumes: `_GroupSettings`, `make_settings`.
- Produces: `StorageSettings` with `endpoint: str` (env `MINIO_ENDPOINT`, **required**), `access_key: str` (env `MINIO_ACCESS_KEY`, **required**), `secret_key: str` (env `MINIO_SECRET_KEY`, **required**), `bucket: str = "rtm"` (env `MINIO_BUCKET`), `secure: bool = False` (env `MINIO_SECURE`), `public_endpoint: str | None = None` (env `MINIO_PUBLIC_ENDPOINT`), `signed_url_expires_seconds: int = 3600`, `download_job_ttl_hours: int = 24`; root field `Settings.storage`. Flat `minio_*`/`signed_url_expires_seconds`/`download_job_ttl_hours` are gone.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_config_groups.py`)

```python
from app.core.config import StorageSettings  # add to existing imports


@pytest.mark.unit
def test_storage_requires_endpoint_and_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for var in ("MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(ValidationError) as excinfo:
        StorageSettings(_env_file=None)  # type: ignore[call-arg]  # pydantic-settings runtime kwarg
    message = str(excinfo.value)
    assert "minio_endpoint" in message
    assert "minio_access_key" in message
    assert "minio_secret_key" in message


@pytest.mark.unit
def test_storage_defaults_and_routing() -> None:
    settings = make_settings(minio_public_endpoint="media.local:9000")
    assert settings.storage.bucket == "rtm"
    assert settings.storage.secure is False
    assert settings.storage.public_endpoint == "media.local:9000"
    assert settings.storage.download_job_ttl_hours == 24
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config_groups.py -v`
Expected: FAIL with `ImportError: cannot import name 'StorageSettings'`

- [ ] **Step 3: Implement group + update consumers**

Add to `config.py` (below `RedisSettings`):

```python
class StorageSettings(_GroupSettings):
    """MinIO object storage + blob retention."""

    endpoint: str = Field(validation_alias="minio_endpoint")
    access_key: str = Field(validation_alias="minio_access_key")
    secret_key: str = Field(validation_alias="minio_secret_key")
    bucket: str = Field(default="rtm", validation_alias="minio_bucket")
    secure: bool = Field(default=False, validation_alias="minio_secure")
    # Host used inside signed URLs (browser-facing). Defaults to endpoint.
    public_endpoint: str | None = Field(default=None, validation_alias="minio_public_endpoint")
    signed_url_expires_seconds: int = 3600
    # Retention for generated MP3 jobs and MinIO objects (hours).
    download_job_ttl_hours: int = 24
```

In `Settings`: delete the six flat `minio_*` lines plus
`signed_url_expires_seconds` and `download_job_ttl_hours`; add
`storage: StorageSettings = Field(default_factory=StorageSettings)`.

Update consumers — find them:
`grep -rn "\.minio_\|\.signed_url_expires_seconds\|\.download_job_ttl_hours" app tests`
Mapping: `settings.minio_endpoint` → `settings.storage.endpoint`,
`minio_access_key` → `storage.access_key`, `minio_secret_key` →
`storage.secret_key`, `minio_bucket` → `storage.bucket`, `minio_secure` →
`storage.secure`, `minio_public_endpoint` → `storage.public_endpoint`,
`settings.signed_url_expires_seconds` → `settings.storage.signed_url_expires_seconds`,
`settings.download_job_ttl_hours` → `settings.storage.download_job_ttl_hours`.

In `tests/test_download_ttl.py`, replace the `MagicMock()` settings with the
factory (a MagicMock's nested attribute would not return `24` anymore):

```python
    from tests.factories import make_settings

    settings = make_settings(download_job_ttl_hours=24)
    monkeypatch.setattr(downloads_service, "get_settings", lambda: settings)
```

`tests/test_storage_presign.py` needs no construction change (factory kwargs
keep the legacy names) — only fix any direct attribute reads the grep finds.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config_groups.py tests/test_storage_presign.py tests/test_download_ttl.py -v` — Expected: PASS
Run: `uv run pytest -m "unit or integration"` — Expected: PASS

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'refactor: extract StorageSettings with required MinIO endpoint and credentials\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 4: `AuthSettings` + `GoogleSsoSettings`; drop dev secret defaults; remove S105 ignore

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/core/security.py`, `backend/app/core/deps.py`, `backend/app/core/bootstrap.py`, `backend/app/modules/auth/router.py`, `backend/app/modules/auth/service.py`, `backend/app/modules/auth/google.py`
- Modify: `backend/pyproject.toml` (remove the `"app/core/config.py" = ["S105"]` per-file-ignore)
- Modify: `backend/tests/test_auth_api.py`, `backend/tests/test_google_config.py`, `backend/tests/test_google_auth_api.py`, `backend/tests/test_google_login_service.py`
- Modify: `backend/tests/test_config_groups.py` (add cases)

**Interfaces:**
- Consumes: `_GroupSettings`, `make_settings`.
- Produces: `AuthSettings` with `jwt_secret: str` (**required**), `jwt_algorithm: str = "HS256"`, `jwt_expire_days: int = 7`, `cookie_secure: bool = False`, `cookie_samesite: Literal["lax", "strict", "none"] = "lax"`, `admin_username: str = "admin"`, `admin_password: str` (**required**); `GoogleSsoSettings` with `client_id/client_secret/redirect_uri: str | None = None` (envs `GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI`); root fields `Settings.auth`, `Settings.google`. The 503-when-unset contract is untouched (`GoogleOAuthClient.__init__` still raises `GoogleNotConfiguredError` on missing values).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_config_groups.py`)

```python
from app.core.config import AuthSettings, GoogleSsoSettings  # add to imports


@pytest.mark.unit
def test_auth_requires_jwt_secret_and_admin_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    with pytest.raises(ValidationError) as excinfo:
        AuthSettings(_env_file=None)  # type: ignore[call-arg]  # pydantic-settings runtime kwarg
    message = str(excinfo.value)
    assert "jwt_secret" in message
    assert "admin_password" in message


@pytest.mark.unit
def test_google_sso_stays_optional(monkeypatch: pytest.MonkeyPatch) -> None:
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
    """Session JWT, cookie flags, seeded admin account."""

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    admin_username: str = "admin"
    admin_password: str


class GoogleSsoSettings(_GroupSettings):
    """Google SSO (server-side authorization-code flow). All three are
    required for login to work; endpoints return 503 when unset."""

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

Remove from `backend/pyproject.toml` `[tool.ruff.lint.per-file-ignores]`:

```toml
"app/core/config.py" = ["S105"]  # local defaults are not production secrets
```

(config.py no longer contains any secret string literal — the required
fields have no defaults and `gemini_api_key` defaults to `None`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config_groups.py tests/test_security.py tests/test_auth_api.py -v` — Expected: PASS
Run: `uv run pytest -m "unit or integration"` — Expected: PASS

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'refactor: extract AuthSettings and GoogleSsoSettings, drop dev secret defaults\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 5: `ScrapeSettings` + `AudioSettings`

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/core/fetcher.py`, `backend/app/modules/scraping/worker.py`, `backend/app/modules/audio/providers/sapi.py`
- Modify: `backend/tests/test_audio_providers.py`
- Modify: `backend/tests/test_config_groups.py` (add cases)

**Interfaces:**
- Consumes: `_GroupSettings`, `make_settings`.
- Produces: `ScrapeSettings` with `timeout_seconds: int = 20` (env `SCRAPE_TIMEOUT_SECONDS`), `max_bytes: int = 2_097_152` (env `SCRAPE_MAX_BYTES`), `delay_seconds: float = 1.5` (env `SCRAPE_DELAY_SECONDS`); `AudioSettings` with `sapi_proxy_enabled: bool = True`; root fields `Settings.scrape`, `Settings.audio`.

- [ ] **Step 1: Write the failing test** (append to `tests/test_config_groups.py`)

```python
@pytest.mark.unit
def test_scrape_and_audio_defaults() -> None:
    settings = make_settings(scrape_delay_seconds=0.5, sapi_proxy_enabled=False)
    assert settings.scrape.timeout_seconds == 20
    assert settings.scrape.max_bytes == 2_097_152
    assert settings.scrape.delay_seconds == 0.5
    assert settings.audio.sapi_proxy_enabled is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config_groups.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'scrape'`

- [ ] **Step 3: Implement groups + update consumers**

Add to `config.py`:

```python
class ScrapeSettings(_GroupSettings):
    """Outbound fetch limits (central fetch service / SSRF guard)."""

    timeout_seconds: int = Field(default=20, validation_alias="scrape_timeout_seconds")
    max_bytes: int = Field(default=2_097_152, validation_alias="scrape_max_bytes")  # 2 MB
    delay_seconds: float = Field(default=1.5, validation_alias="scrape_delay_seconds")


class AudioSettings(_GroupSettings):
    """TTS provider toggles."""

    sapi_proxy_enabled: bool = True
```

In `Settings`: delete the flat `scrape_*` and `sapi_proxy_enabled` lines;
add `scrape: ScrapeSettings = Field(default_factory=ScrapeSettings)` and
`audio: AudioSettings = Field(default_factory=AudioSettings)`.

Update consumers — find them:
`grep -rn "\.scrape_timeout_seconds\|\.scrape_max_bytes\|\.scrape_delay_seconds\|\.sapi_proxy_enabled" app tests`
Mapping: `settings.scrape_*` → `settings.scrape.*` (prefix dropped),
`settings.sapi_proxy_enabled` → `settings.audio.sapi_proxy_enabled`.

In `tests/test_audio_providers.py`, both `MagicMock(sapi_proxy_enabled=True)`
fakes become the factory (nested attribute on a bare MagicMock would return
a Mock, not `True`):

```python
    from tests.factories import make_settings

    monkeypatch.setattr(
        "app.modules.audio.providers.sapi.get_settings",
        lambda: make_settings(sapi_proxy_enabled=True),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config_groups.py tests/test_audio_providers.py -v` — Expected: PASS
Run: `uv run pytest -m "unit or integration"` — Expected: PASS

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'refactor: extract ScrapeSettings and AudioSettings\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 6: `LlmSettings` + `LlmRuntimeSettings` + conditional GEMINI_API_KEY validation

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py` (delete `_validate_llm_startup` and its call)
- Modify: LLM consumers — `backend/app/modules/llm/service.py`, `backend/app/modules/llm/router.py`, `backend/app/modules/llm/providers/*`, the orchestration budget module (`RunBudget.from_settings`), HITL/context/summary code, `backend/app/modules/tools/definitions/summarize_book.py` (Step 3 grep is authoritative)
- Modify: `backend/tests/test_config_groups.py` (add cases)

**Interfaces:**
- Consumes: `_GroupSettings`, `make_settings`.
- Produces: `LlmSettings` with `enabled: bool = False` (env `LLM_ENABLED`), `provider: str = "gemini"` (env `LLM_PROVIDER`), `model: str = "gemini-3.5-flash-lite"` (env `LLM_MODEL`), `gemini_api_key: str | None = None`, `timeout_seconds: int = 30` (env `LLM_TIMEOUT_SECONDS`), `max_output_tokens: int = 2048` (env `LLM_MAX_OUTPUT_TOKENS`), `max_retries: int = 2` (env `LLM_MAX_RETRIES`), `langfuse_enabled: bool = False`, plus a `model_validator` enforcing the key when enabled; `LlmRuntimeSettings` with the 12 orchestration knobs (`max_tool_iters=6`, `max_external_calls=3`, `max_turn_tokens_in=64_000`, `max_turn_tokens_out=8_192`, `max_turn_cost_usd=0.05`, `run_deadline_seconds=60`, `context_recent_messages=10`, `summary_trigger_tokens=12_000`, `summary_max_output_tokens=1_200`, `assistant_mode="internal_only"`, `hitl_ttl_seconds=900`, `max_hitl_rounds=3`), each aliased to its legacy `llm_*` env name; root fields `Settings.llm`, `Settings.llm_runtime`. **`settings.llm_runtime` is the future DB-backed dynamic-config seam — consumers must read the knobs only through it.**

- [ ] **Step 1: Write the failing tests** (append to `tests/test_config_groups.py`)

```python
@pytest.mark.unit
def test_llm_enabled_requires_gemini_key() -> None:
    with pytest.raises(ValidationError, match="GEMINI_API_KEY"):
        make_settings(llm_enabled=True, gemini_api_key=None)


@pytest.mark.unit
def test_llm_disabled_allows_missing_key() -> None:
    settings = make_settings(llm_enabled=False, gemini_api_key=None)
    assert settings.llm.enabled is False


@pytest.mark.unit
def test_llm_runtime_group_holds_all_budgets() -> None:
    settings = make_settings(llm_max_tool_iters=2, llm_assistant_mode="external_allowed")
    runtime = settings.llm_runtime
    assert runtime.max_tool_iters == 2
    assert runtime.max_external_calls == 3
    assert runtime.max_turn_tokens_in == 64_000
    assert runtime.max_turn_tokens_out == 8_192
    assert runtime.max_turn_cost_usd == 0.05
    assert runtime.run_deadline_seconds == 60
    assert runtime.context_recent_messages == 10
    assert runtime.summary_trigger_tokens == 12_000
    assert runtime.summary_max_output_tokens == 1_200
    assert runtime.assistant_mode == "external_allowed"
    assert runtime.hitl_ttl_seconds == 900
    assert runtime.max_hitl_rounds == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config_groups.py -v`
Expected: FAIL — `test_llm_enabled_requires_gemini_key` with `Failed: DID NOT RAISE` (no validator exists yet; the flat kwargs still route to the root), the other two with `AttributeError: 'Settings' object has no attribute 'llm'` / `'llm_runtime'`

- [ ] **Step 3: Implement groups + update consumers**

Add to `config.py` (`model_validator` joins the `pydantic` import):

```python
class LlmSettings(_GroupSettings):
    """LLM provider config (Milestone B). Off by default."""

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

    Future dynamic-config seam: these values will later move to a DB-backed
    config layer with per-tier overrides. Read them only via
    `settings.llm_runtime` so that extraction stays a one-object swap.
    """

    max_tool_iters: int = Field(default=6, validation_alias="llm_max_tool_iters")
    max_external_calls: int = Field(default=3, validation_alias="llm_max_external_calls")
    max_turn_tokens_in: int = Field(default=64_000, validation_alias="llm_max_turn_tokens_in")
    max_turn_tokens_out: int = Field(default=8_192, validation_alias="llm_max_turn_tokens_out")
    max_turn_cost_usd: float = Field(default=0.05, validation_alias="llm_max_turn_cost_usd")
    run_deadline_seconds: int = Field(default=60, validation_alias="llm_run_deadline_seconds")
    context_recent_messages: int = Field(default=10, validation_alias="llm_context_recent_messages")
    summary_trigger_tokens: int = Field(default=12_000, validation_alias="llm_summary_trigger_tokens")
    summary_max_output_tokens: int = Field(default=1_200, validation_alias="llm_summary_max_output_tokens")
    assistant_mode: str = Field(default="internal_only", validation_alias="llm_assistant_mode")
    # HITL: how long a pending confirmation stays valid; max pauses per turn.
    hitl_ttl_seconds: int = Field(default=900, validation_alias="llm_hitl_ttl_seconds")
    max_hitl_rounds: int = Field(default=3, validation_alias="llm_max_hitl_rounds")
```

In `Settings`: delete all flat `llm_*`, `gemini_api_key`, `langfuse_enabled`
lines; add `llm: LlmSettings = Field(default_factory=LlmSettings)` and
`llm_runtime: LlmRuntimeSettings = Field(default_factory=LlmRuntimeSettings)`.

In `app/main.py`: delete `_validate_llm_startup` entirely and the
`_validate_llm_startup(settings)` call in `create_app` (the `LlmSettings`
validator now covers it in every process, worker included). Keep the
provider-level `LlmConfigError` checks in `modules/llm/` untouched.

Update consumers — find them:
`grep -rn "\.llm_enabled\|\.llm_provider\|\.llm_model\|\.gemini_api_key\|\.llm_timeout_seconds\|\.llm_max_output_tokens\|\.llm_max_retries\|\.langfuse_enabled\|\.llm_max_tool_iters\|\.llm_max_external_calls\|\.llm_max_turn_tokens_in\|\.llm_max_turn_tokens_out\|\.llm_max_turn_cost_usd\|\.llm_run_deadline_seconds\|\.llm_context_recent_messages\|\.llm_summary_trigger_tokens\|\.llm_summary_max_output_tokens\|\.llm_assistant_mode\|\.llm_hitl_ttl_seconds\|\.llm_max_hitl_rounds" app tests`
Mapping: provider config → `settings.llm.<name-without-llm_-prefix>`
(`llm_enabled`→`llm.enabled`, `gemini_api_key`→`llm.gemini_api_key`,
`langfuse_enabled`→`llm.langfuse_enabled`); the 12 budget knobs →
`settings.llm_runtime.<name-without-llm_-prefix>` per the Interfaces list.
`RunBudget.from_settings(settings)` keeps its signature — only its body's
attribute reads change.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config_groups.py tests/llm -v` — Expected: PASS (LLM tests were factory-migrated in Task 1, so their flat kwargs route automatically)
Run: `uv run pytest -m "unit or integration"` — Expected: PASS

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'refactor: extract LlmSettings and LlmRuntimeSettings with conditional key check\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 7: `AppSettings` + finalize the root

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py`, `backend/app/modules/health/router.py`
- Modify: `backend/tests/test_settings_factory.py`, `backend/tests/test_config_groups.py`

**Interfaces:**
- Consumes: `_GroupSettings`, `make_settings`.
- Produces: `AppSettings` with `name: str = "RTM v3"` (env `APP_NAME`), `env: str = "local"` (env `APP_ENV`), `debug: bool = False`, `api_prefix: str = "/api"`, `cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]`; root field `Settings.app`. The root `Settings` now contains **only** the ten group fields (`app`, `database`, `redis`, `storage`, `auth`, `google`, `scrape`, `audio`, `llm`, `llm_runtime`) — no flat fields remain.

- [ ] **Step 1: Write the failing test** (append to `tests/test_config_groups.py`)

```python
from pydantic_settings import BaseSettings  # add to imports

from app.core.config import Settings  # add to imports


@pytest.mark.unit
def test_app_group_and_fully_grouped_root() -> None:
    settings = make_settings(app_name="RTM test")
    assert settings.app.name == "RTM test"
    assert settings.app.api_prefix == "/api"
    # Root is groups-only: every field is a BaseSettings subclass.
    for field in Settings.model_fields.values():
        annotation = field.annotation
        assert isinstance(annotation, type)
        assert issubclass(annotation, BaseSettings)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config_groups.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'app'` (`app_name` is still a flat root field, so the override routes — the group doesn't exist)

- [ ] **Step 3: Implement + update consumers**

Add to `config.py` (first group, above `DatabaseSettings`):

```python
class AppSettings(_GroupSettings):
    """App identity and HTTP surface."""

    name: str = Field(default="RTM v3", validation_alias="app_name")
    env: str = Field(default="local", validation_alias="app_env")
    debug: bool = False
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
```

In `Settings`: delete the flat `app_name`, `app_env`, `debug`, `api_prefix`,
`cors_origins` lines; add `app: AppSettings = Field(default_factory=AppSettings)`
as the first field. The finished root:

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
`grep -rn "\.app_name\|\.app_env\|settings\.debug\|\.api_prefix\|\.cors_origins" app tests`
- `app/main.py` — `settings.debug` → `settings.app.debug`, `settings.app_name` → `settings.app.name`, `settings.cors_origins` → `settings.app.cors_origins`, all twelve `prefix=settings.api_prefix` → `prefix=settings.app.api_prefix`
- `app/modules/health/router.py` — `settings.app_name` → `settings.app.name`

Update `tests/test_settings_factory.py` Task-1 assertions to the final
paths: `settings.jwt_secret` → `settings.auth.jwt_secret` (both tests),
`settings.minio_access_key` → `settings.storage.access_key`, and delete the
"Flat access in Task 1" comment.

Final audit (must return **no hits** outside `config.py` aliases and
`tests/factories.py` dummy keys):
`grep -rn "\.database_url\|\.redis_url\|\.minio_\|\.jwt_secret\|\.admin_password\|\.google_client\|\.scrape_\|\.sapi_proxy\|\.llm_\|\.app_name\|\.gemini_api_key" app migrations`

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config_groups.py tests/test_settings_factory.py -v` — Expected: PASS
Run: `uv run pytest -m "unit or integration"` — Expected: PASS

- [ ] **Step 5: Native boot smoke**

```bash
uv run python -c "from app.core.config import get_settings; s = get_settings(); print(s.app.name, s.database.url.split('@')[-1])"
uv run python -c "import app.jobs.worker; print('worker imports ok')"
uv run python -c "import app.main; print('app imports ok')"
```

Expected: all three print (settings resolve from `.env`; worker and app
import without error). Alembic's `env.py` is already exercised by the
integration run (conftest migrates the test DB through it).

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'refactor: extract AppSettings and finalize grouped Settings root\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 8: docker-compose de-duplication (`x-app-env` anchor) + container smoke

**Files:**
- Modify: `docker-compose.yml` (repo root)

**Interfaces:**
- Consumes: nothing from code — env var names are unchanged by design.
- Produces: a single `x-app-env` block merged into both `backend` and `worker`; secrets use compose-required `${VAR:?}` syntax. The worker now receives `JWT_SECRET`/`ADMIN_*`/`CORS_ORIGINS`/`COOKIE_SECURE` (required for boot since Task 4).

- [ ] **Step 1: Add the anchor and rewrite both env blocks**

At the top of `docker-compose.yml` (before `services:`):

```yaml
x-app-env: &app-env
  APP_ENV: local
  DATABASE_URL: postgresql+asyncpg://${DB_USER:-rtm}:${DB_PASSWORD:-rtm}@postgres:5432/${DB_NAME:-rtm}
  REDIS_URL: redis://redis:6379/0
  MINIO_ENDPOINT: minio:9000
  MINIO_PUBLIC_ENDPOINT: localhost:9000
  MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY:?MINIO_ACCESS_KEY must be set in .env}
  MINIO_SECRET_KEY: ${MINIO_SECRET_KEY:?MINIO_SECRET_KEY must be set in .env}
  MINIO_BUCKET: ${MINIO_BUCKET:-rtm}
  MINIO_SECURE: "false"
  CORS_ORIGINS: '["http://localhost:5173","http://localhost:3000","http://localhost"]'
  JWT_SECRET: ${JWT_SECRET:?JWT_SECRET must be set in .env}
  ADMIN_USERNAME: ${ADMIN_USERNAME:-admin}
  ADMIN_PASSWORD: ${ADMIN_PASSWORD:?ADMIN_PASSWORD must be set in .env}
  COOKIE_SECURE: "false"
  SAPI_PROXY_ENABLED: "true"
  GOOGLE_CLIENT_ID: ${GOOGLE_CLIENT_ID:-}
  GOOGLE_CLIENT_SECRET: ${GOOGLE_CLIENT_SECRET:-}
  GOOGLE_REDIRECT_URI: ${GOOGLE_REDIRECT_URI:-http://localhost:3000/api/auth/google/callback}
  LLM_ENABLED: ${LLM_ENABLED:-false}
  LLM_PROVIDER: ${LLM_PROVIDER:-gemini}
  LLM_MODEL: ${LLM_MODEL:-gemini-3.5-flash-lite}
  GEMINI_API_KEY: ${GEMINI_API_KEY:-}
  LLM_TIMEOUT_SECONDS: ${LLM_TIMEOUT_SECONDS:-30}
  LLM_MAX_OUTPUT_TOKENS: ${LLM_MAX_OUTPUT_TOKENS:-2048}
  LLM_MAX_RETRIES: ${LLM_MAX_RETRIES:-2}
  LANGFUSE_ENABLED: ${LANGFUSE_ENABLED:-false}
  LLM_ASSISTANT_MODE: ${LLM_ASSISTANT_MODE:-internal_only}
  LLM_HITL_TTL_SECONDS: ${LLM_HITL_TTL_SECONDS:-900}
  LLM_MAX_HITL_ROUNDS: ${LLM_MAX_HITL_ROUNDS:-3}
```

Replace the `backend` service's entire `environment:` block with:

```yaml
    environment:
      <<: *app-env
```

Replace the `worker` service's entire `environment:` block with the same
two lines. Leave `postgres`, `minio`, `minio-init`, and `frontend` service
definitions untouched (infra fallbacks `:-rtm` are intentional; `.env`
overrides them).

- [ ] **Step 2: Validate the merge**

```bash
docker compose config > /dev/null && echo "compose config OK"
docker compose config | grep -c "JWT_SECRET"
```

Expected: `compose config OK`; the grep count is `2` (backend + worker both
inherit the shared block).

- [ ] **Step 3: Fail-fast check without .env values**

```bash
docker compose --env-file /dev/null config > /dev/null
```

Expected: FAILS with `JWT_SECRET must be set in .env` (or whichever `:?`
var it hits first). If your shell exports these vars globally the check is
inconclusive — note it and move on.

- [ ] **Step 4: Boot smoke**

```bash
docker compose up -d --build backend worker
docker compose ps
docker compose logs --tail 20 backend worker
docker compose down
```

Expected: backend reports healthy (its entrypoint auto-runs
`alembic upgrade head`, proving Alembic boots on grouped settings in the
container); worker runs without a settings `ValidationError` (it now gets
`JWT_SECRET`/`ADMIN_PASSWORD` from the shared block).

- [ ] **Step 5: Commit**

```bash
printf 'chore: de-duplicate compose app env via x-app-env anchor, require secrets\n' > /tmp/msg.txt
git add docker-compose.yml
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 9: Documentation — `.env.example`, README, CLAUDE.md

**Files:**
- Modify: `.env.example`, `README.md`, `CLAUDE.md` (all repo root)

**Interfaces:**
- Consumes: the final group structure (Task 7) and compose anchor (Task 8).
- Produces: docs matching reality; `.env.example` remains the canonical variable list and copying it still yields a working local dev env.

- [ ] **Step 1: Annotate `.env.example`**

Keep every variable and dev value exactly as-is (local dev must keep
working by copying the file). Add a `# REQUIRED` marker line above each of
the seven required vars. Example for the auth block:

```bash
# Auth (single local admin; password is hashed at rest)
# REQUIRED — no code default; the app refuses to start without it.
JWT_SECRET=dev-only-change-me-to-a-long-random-secret
ADMIN_USERNAME=admin
# REQUIRED — no code default; the app refuses to start without it.
ADMIN_PASSWORD=changeme123
```

Apply the same marker to `DATABASE_URL`, `REDIS_URL`, `MINIO_ENDPOINT`,
`MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`. Add one header note under the
`# Application` block:

```bash
# Variables marked REQUIRED have no in-code default: a missing value stops
# startup (API, worker, alembic) with a pydantic error naming the variable.
```

- [ ] **Step 2: Update the README config section**

In the configuration/env section (the bullet list around "PostgreSQL / …
/ HTTP/auth"), document:

- Settings are grouped sub-models in `backend/app/core/config.py`
  (`app`, `database`, `redis`, `storage`, `auth`, `google`, `scrape`,
  `audio`, `llm`, `llm_runtime`); env var names are unchanged and flat.
- The seven REQUIRED variables (`DATABASE_URL`, `REDIS_URL`,
  `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `JWT_SECRET`,
  `ADMIN_PASSWORD`): missing ⇒ startup crash with a pydantic
  `ValidationError` naming the variable; fix = set it in `.env`.
- Conditional: `GEMINI_API_KEY` required iff `LLM_ENABLED=true` (now
  enforced in every process, worker included); `GOOGLE_CLIENT_ID/SECRET/
  REDIRECT_URI` optional — SSO endpoints return 503 until set.
- `docker compose up` fails fast with `VAR must be set in .env` when a
  required secret is missing (the `x-app-env` `${VAR:?}` guard).
- The LLM orchestration budgets live in the `llm_runtime` group, slated to
  move to a DB-backed dynamic config layer later.

- [ ] **Step 3: Update CLAUDE.md**

Replace the sentence in the "Full stack" section:

> When adding a setting, update `Settings` (pydantic-settings in
> `app/core/config.py`), `.env.example`, compose, and README together.

with:

> When adding a setting, update the matching group class in `Settings`
> (pydantic-settings in `app/core/config.py` — flat env names via
> `validation_alias`, secrets/per-env values REQUIRED with no default),
> `.env.example`, the shared `x-app-env` block in `docker-compose.yml`
> (one block feeds backend and worker), and README together. In tests,
> build settings with `tests/factories.py::make_settings(**flat_overrides)`
> — never construct `Settings()` directly.

- [ ] **Step 4: Full final gates**

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -m "unit or integration"
```

Expected: all clean/green.

- [ ] **Step 5: Commit**

```bash
printf 'docs: document grouped settings, required env vars, and shared compose env\n' > /tmp/msg.txt
git add .env.example README.md CLAUDE.md
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```
