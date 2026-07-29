# Config Restructure (grouped Settings, fail-fast, secret hygiene) — Design

Date: 2026-07-29
Status: Proposed (requirements specified by user; produced in autonomous session)

## Goal

Restructure `backend/app/core/config.py` from one flat ~49-field
`Settings` model into logical, composed sub-models with **unchanged env var
names**, make secrets and per-environment values **fail fast at startup**
when missing (no more silent `dev-only-change-me` defaults), move all
dev-convenience values out of code into `.env.example`, and de-duplicate the
docker-compose `environment` blocks with a YAML anchor. Behavior-preserving
otherwise: no route or service behavior changes.

## Constraints (fixed)

- Existing env var names must not change (`DATABASE_URL`, `JWT_SECRET`,
  `MINIO_*`, `LLM_*`, …). Compose files and existing `.env` files keep
  working unmodified.
- No `env_nested_delimiter` (`DB__URL`-style names are forbidden).
- Google SSO contract preserved: `GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI` stay
  `Optional`; endpoints return 503 when unset. No startup requirement.
- Strict mypy + ruff gates; every task independently green.
- Sequenced **after** `feature/sso` merges (that branch adds the three
  `google_*` fields, `tests/test_google_config.py`, and env plumbing that
  this restructure reshapes).
- The DB-backed dynamic config layer is **out of scope** — this design only
  groups the runtime-tunable values so a later extraction is trivial.

## Approaches considered

1. **Composed `BaseSettings` groups (chosen).** Each group is its own
   `BaseSettings` subclass whose fields map to the existing flat env names
   (field name = env name where possible, `Field(validation_alias=...)`
   where the field is renamed). The root `Settings` composes the groups via
   `default_factory`. This is the documented pydantic-settings pattern for
   nested settings with flat env names; each group loads its own env/dotenv.
2. **Nested plain `BaseModel`s + `env_nested_delimiter`.** Rejected: changes
   every env var name (`DATABASE__URL`), breaking compose and `.env`.
3. **Nested plain `BaseModel`s + per-field aliases.** Rejected: the
   pydantic-settings env source does **not** consult aliases inside nested
   plain models — it only maps nested fields via the delimiter or a JSON
   env var. Verified against current pydantic-settings docs/source
   (`EnvSettingsSource._extract_field_info` walks top-level `BaseSettings`
   fields only).
4. **Mixin classes keeping flat attribute access.** Rejected: source-file
   grouping only; no `settings.llm_runtime` object to hand to a future
   dynamic-config layer, and no per-group construction for tests.

## New structure

One file, `backend/app/core/config.py` (config is cross-cutting; stays in
`core`). Shape:

```python
class _GroupSettings(BaseSettings):
    """Shared loading behavior for every settings group."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


class DatabaseSettings(_GroupSettings):
    url: str = Field(validation_alias="database_url")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(
        default_factory=DatabaseSettings,  # type: ignore[arg-type]  # env-sourced
    )
    redis: RedisSettings = ...
    storage: StorageSettings = ...
    auth: AuthSettings = ...
    google: GoogleSsoSettings = ...
    scrape: ScrapeSettings = ...
    audio: AudioSettings = ...
    llm: LlmSettings = ...
    llm_runtime: LlmRuntimeSettings = ...


@lru_cache
def get_settings() -> Settings:  # unchanged signature and caching
    return Settings()
```

Notes:

- **Renamed fields use `validation_alias` set to the legacy flat name**
  (case-insensitive, so `database_url` matches env `DATABASE_URL`). Fields
  whose name already equals the env name (e.g. `jwt_secret`) need no alias.
  Because `validation_alias` also governs init kwargs, groups are
  constructed in tests with the **legacy flat names**
  (`DatabaseSettings(database_url=...)`) — a deliberate ergonomic win.
- **Required fields have no default.** A missing env var raises a pydantic
  `ValidationError` naming the alias (i.e. the env var name) the moment
  `get_settings()` / module import runs — in the API, the arq worker, and
  Alembic alike.
- The pydantic mypy plugin synthesizes `__init__` with required
  alias-kwargs, so `default_factory=GroupCls` needs a
  `# type: ignore[arg-type]` (or `[call-arg]` on a lambda) with a reason
  comment — same precedent as the existing
  `Settings(_env_file=None)  # type: ignore[call-arg]`. The exact code is
  pinned during implementation; ignores must carry the specific code.
- `get_settings()` stays `@lru_cache`'d; `Depends(get_settings)` call sites
  are untouched.

### Attribute renames (old → new)

| Group (attr) | Class | Old flat attribute → new attribute |
|---|---|---|
| `settings.app` | `AppSettings` | `app_name`→`name`, `app_env`→`env`, `debug`, `api_prefix`, `cors_origins` |
| `settings.database` | `DatabaseSettings` | `database_url`→`url` |
| `settings.redis` | `RedisSettings` | `redis_url`→`url` |
| `settings.storage` | `StorageSettings` | `minio_endpoint`→`endpoint`, `minio_access_key`→`access_key`, `minio_secret_key`→`secret_key`, `minio_bucket`→`bucket`, `minio_secure`→`secure`, `minio_public_endpoint`→`public_endpoint`, `signed_url_expires_seconds`, `download_job_ttl_hours` |
| `settings.auth` | `AuthSettings` | `jwt_secret`, `jwt_algorithm`, `jwt_expire_days`, `cookie_secure`, `cookie_samesite`, `admin_username`, `admin_password` |
| `settings.google` | `GoogleSsoSettings` | `google_client_id`→`client_id`, `google_client_secret`→`client_secret`, `google_redirect_uri`→`redirect_uri` |
| `settings.scrape` | `ScrapeSettings` | `scrape_timeout_seconds`→`timeout_seconds`, `scrape_max_bytes`→`max_bytes`, `scrape_delay_seconds`→`delay_seconds` |
| `settings.audio` | `AudioSettings` | `sapi_proxy_enabled` |
| `settings.llm` | `LlmSettings` | `llm_enabled`→`enabled`, `llm_provider`→`provider`, `llm_model`→`model`, `gemini_api_key`, `llm_timeout_seconds`→`timeout_seconds`, `llm_max_output_tokens`→`max_output_tokens`, `llm_max_retries`→`max_retries`, `langfuse_enabled` |
| `settings.llm_runtime` | `LlmRuntimeSettings` | every `llm_*` orchestration budget (see table) with the `llm_` prefix dropped |

`LlmRuntimeSettings` is the future dynamic-config seam: it holds exactly
the values that will later move to a DB-backed layer with per-tier
overrides. Consumers (`RunBudget.from_settings`, orchestrator, HITL,
context/summary sizing) must read them **only** via `settings.llm_runtime`
so the extraction is a one-object swap. Do not build the DB layer now.

## Full field classification

Buckets: **R** = required, no default (missing ⇒ startup crash) ·
**C** = conditionally required · **S** = static default OK ·
**T** = runtime-tunable candidate (defaults now; future DB-backed layer).

| Env var | New location | Bucket | Default after restructure | Notes |
|---|---|---|---|---|
| `APP_NAME` | `app.name` | S | `"RTM v3"` | Display title |
| `APP_ENV` | `app.env` | S | `"local"` | Informational |
| `DEBUG` | `app.debug` | S | `False` | |
| `API_PREFIX` | `app.api_prefix` | S | `"/api"` | True constant |
| `CORS_ORIGINS` | `app.cors_origins` | S | localhost `5173`/`3000` list | Safe local default; overridden per env |
| `DATABASE_URL` | `database.url` | **R** | — | Per-environment; secret-bearing DSN |
| `REDIS_URL` | `redis.url` | **R** | — | Per-environment |
| `MINIO_ENDPOINT` | `storage.endpoint` | **R** | — | Per-environment (`localhost:9000` vs `minio:9000`); silent default is exactly the failure mode to kill |
| `MINIO_ACCESS_KEY` | `storage.access_key` | **R** | — | Credential |
| `MINIO_SECRET_KEY` | `storage.secret_key` | **R** | — | Credential |
| `MINIO_BUCKET` | `storage.bucket` | S | `"rtm"` | |
| `MINIO_SECURE` | `storage.secure` | S | `False` | |
| `MINIO_PUBLIC_ENDPOINT` | `storage.public_endpoint` | S | `None` (falls back to `endpoint`) | Optional override by design |
| `SIGNED_URL_EXPIRES_SECONDS` | `storage.signed_url_expires_seconds` | S | `3600` | |
| `DOWNLOAD_JOB_TTL_HOURS` | `storage.download_job_ttl_hours` | S | `24` | |
| `JWT_SECRET` | `auth.jwt_secret` | **R** | — | Secret; today defaults to `dev-only-change-me…` in code |
| `JWT_ALGORITHM` | `auth.jwt_algorithm` | S | `"HS256"` | Constant |
| `JWT_EXPIRE_DAYS` | `auth.jwt_expire_days` | S | `7` | |
| `COOKIE_SECURE` | `auth.cookie_secure` | S | `False` | Prod hardening documented in README |
| `COOKIE_SAMESITE` | `auth.cookie_samesite` | S | `"lax"` | |
| `ADMIN_USERNAME` | `auth.admin_username` | S | `"admin"` | Not a secret; anchors SSO admin-claim rule |
| `ADMIN_PASSWORD` | `auth.admin_password` | **R** | — | Secret; today defaults to `changeme123` in code |
| `GOOGLE_CLIENT_ID` | `google.client_id` | C | `None` | 503-when-unset contract (SSO design) — never startup-required |
| `GOOGLE_CLIENT_SECRET` | `google.client_secret` | C | `None` | Same |
| `GOOGLE_REDIRECT_URI` | `google.redirect_uri` | C | `None` | Same |
| `SCRAPE_TIMEOUT_SECONDS` | `scrape.timeout_seconds` | S | `20` | |
| `SCRAPE_MAX_BYTES` | `scrape.max_bytes` | S | `2_097_152` | |
| `SCRAPE_DELAY_SECONDS` | `scrape.delay_seconds` | S | `1.5` | |
| `SAPI_PROXY_ENABLED` | `audio.sapi_proxy_enabled` | S | `True` | |
| `LLM_ENABLED` | `llm.enabled` | S | `False` | Gate for the C rule below |
| `LLM_PROVIDER` | `llm.provider` | S | `"gemini"` | Config-as-data |
| `LLM_MODEL` | `llm.model` | S | `"gemini-3.5-flash-lite"` | Config-as-data |
| `GEMINI_API_KEY` | `llm.gemini_api_key` | C | `None` | **Required iff `LLM_ENABLED=true`** — `model_validator` on `LlmSettings` |
| `LLM_TIMEOUT_SECONDS` | `llm.timeout_seconds` | S | `30` | |
| `LLM_MAX_OUTPUT_TOKENS` | `llm.max_output_tokens` | S | `2048` | Per-call cap (not a turn budget) |
| `LLM_MAX_RETRIES` | `llm.max_retries` | S | `2` | |
| `LANGFUSE_ENABLED` | `llm.langfuse_enabled` | S | `False` | |
| `LLM_MAX_TOOL_ITERS` | `llm_runtime.max_tool_iters` | T | `6` | Loop bound |
| `LLM_MAX_EXTERNAL_CALLS` | `llm_runtime.max_external_calls` | T | `3` | Safety counter, separate from token budget |
| `LLM_MAX_TURN_TOKENS_IN` | `llm_runtime.max_turn_tokens_in` | T | `64_000` | |
| `LLM_MAX_TURN_TOKENS_OUT` | `llm_runtime.max_turn_tokens_out` | T | `8_192` | |
| `LLM_MAX_TURN_COST_USD` | `llm_runtime.max_turn_cost_usd` | T | `0.05` | |
| `LLM_RUN_DEADLINE_SECONDS` | `llm_runtime.run_deadline_seconds` | T | `60` | Wall clock |
| `LLM_CONTEXT_RECENT_MESSAGES` | `llm_runtime.context_recent_messages` | T | `10` | |
| `LLM_SUMMARY_TRIGGER_TOKENS` | `llm_runtime.summary_trigger_tokens` | T | `12_000` | |
| `LLM_SUMMARY_MAX_OUTPUT_TOKENS` | `llm_runtime.summary_max_output_tokens` | T | `1_200` | |
| `LLM_ASSISTANT_MODE` | `llm_runtime.assistant_mode` | T | `"internal_only"` | Per-tier candidate |
| `LLM_HITL_TTL_SECONDS` | `llm_runtime.hitl_ttl_seconds` | T | `900` | |
| `LLM_MAX_HITL_ROUNDS` | `llm_runtime.max_hitl_rounds` | T | `3` | |

Totals: 7 required · 4 conditional · 12 runtime-tunable · 26 static.

## Conditional validation

`LlmSettings` gets:

```python
@model_validator(mode="after")
def _require_key_when_enabled(self) -> "LlmSettings":
    if self.enabled and self.provider == "gemini" and not self.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is required when LLM_ENABLED=true")
    return self
```

This **replaces** `_validate_llm_startup` in `app/main.py` (delete it). Net
behavior change, accepted: the check now fires at `get_settings()` in every
process — including the arq worker, which today skips it — and surfaces as
a pydantic `ValidationError` instead of `LlmConfigError`. The
defense-in-depth checks inside `modules/llm/providers` and `llm/service.py`
stay. Google SSO fields get **no** validator — the 503 contract is the
design.

## Fail-fast semantics

- `app/core/db.py` builds its engine from `get_settings()` at import time —
  missing `DATABASE_URL` already crashes any process at import. The other
  six required vars crash at first `get_settings()` (also import time via
  `db.py`). This is the desired behavior: a missed variable is a loud
  `ValidationError` naming the env var, not a silent dev credential.
- The worker (`arq app.jobs.worker.WorkerSettings`) imports app modules →
  same fail-fast. **Consequence:** the worker container must now receive
  `JWT_SECRET`/`ADMIN_PASSWORD` (it currently doesn't) — handled by the
  shared compose anchor below.
- Alembic (`migrations/env.py`) calls `get_settings()` → same fail-fast;
  reads `settings.database.url` after the rename.

## Test strategy

Two shared pieces, then mechanical call-site updates:

1. **Env bootstrap in `backend/tests/conftest.py`** (runs before any app
   import, extending the existing `DATABASE_URL` override):
   - Load the repo-root `.env` (if present) with
     `dotenv_values` (python-dotenv ships with pydantic-settings) and
     `os.environ.setdefault` each value — preserves real dev values for
     integration tests.
   - `os.environ.setdefault` safe dummies for every required var
     (`REDIS_URL`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`,
     `JWT_SECRET` ≥32 chars, `ADMIN_PASSWORD`) so the suite passes on a
     clean checkout with no `.env`.
   - Keep forcing `DATABASE_URL` to `TEST_DATABASE_URL` (never the app DB).
2. **Settings factory `backend/tests/factories.py`** —
   `make_settings(**overrides: Any) -> Settings`. Accepts **legacy flat
   names** (`make_settings(llm_enabled=True, gemini_api_key="test-key")`),
   routes each override to its group by introspecting group
   `model_fields` aliases, constructs every group with `_env_file=None`
   plus dummy required values, and raises on unknown keys. Existing direct
   constructions migrate to it:
   - `Settings(jwt_secret=...)` (test_security) → `make_settings(jwt_secret=...)`
   - `Settings(llm_max_tool_iters=1)` (orchestration/budget/chat/hitl/
     conversation-context tests) → same names via factory
   - `Settings(minio_*)` (test_storage_presign) → factory
   - `Settings(_env_file=None)` / SSO-branch tests (test_google_config,
     test_google_oauth) → factory; `monkeypatch.setattr(settings,
     "google_client_id", ...)` (test_google_auth_api) →
     `monkeypatch.setattr(settings.google, "client_id", ...)`.

   Rationale for the factory over raw construction: `_env_file=None` on the
   root no longer isolates groups (each group reads its own dotenv), so
   hermetic tests need per-group construction — exactly what the factory
   centralizes.

## Call-site inventory (attribute path updates only)

Strict mypy is the safety net — every missed site is a type error.

- `core/`: `db.py` (`database.url`), `storage.py` (`storage.*`),
  `security.py` (`auth.jwt_*`), `deps.py` (auth), `bootstrap.py`
  (`auth.admin_*`), `fetcher.py` (`scrape.*`), `logging.py` via `main.py`.
- `main.py`: `app.name`, `app.debug`, `app.api_prefix`, `app.cors_origins`;
  delete `_validate_llm_startup`.
- `jobs/`: `queue.py` (`redis.url`), `purge_downloads.py`, `tasks.py`.
- `modules/`: `auth` (router/service: `auth.*`, `google.*` — includes the
  merged SSO `google.py` client), `books` + `downloads`
  (`storage.signed_url_expires_seconds`, `storage.download_job_ttl_hours`),
  `audio/providers/sapi.py` (`audio.sapi_proxy_enabled`),
  `scraping/worker.py` (`scrape.delay_seconds`), `health/router.py`,
  `imports/jobs.py`, `llm/*` + `orchestration` + `tools/definitions`
  (`llm.*`, `llm_runtime.*`).
- `migrations/env.py` (`database.url`).

## Secret hygiene

- `.env.example` stays the canonical variable list; it already carries dev
  values for all seven required vars. Annotate the required ones with a
  `# REQUIRED — no code default; app refuses to start without it` comment.
  Local dev flow is unchanged: copy `.env.example` → `.env`.
- Remove `"app/core/config.py" = ["S105"]` from
  `[tool.ruff.lint.per-file-ignores]` in `backend/pyproject.toml` once no
  secret literals remain in code (ruff must stay clean after removal).

## docker-compose de-duplication

Top-level extension field merged into both app services:

```yaml
x-app-env: &app-env
  APP_ENV: local
  DATABASE_URL: postgresql+asyncpg://${DB_USER:-rtm}:${DB_PASSWORD:-rtm}@postgres:5432/${DB_NAME:-rtm}
  REDIS_URL: redis://redis:6379/0
  MINIO_ENDPOINT: minio:9000
  MINIO_PUBLIC_ENDPOINT: localhost:9000
  MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY:?set in .env}
  MINIO_SECRET_KEY: ${MINIO_SECRET_KEY:?set in .env}
  MINIO_BUCKET: ${MINIO_BUCKET:-rtm}
  MINIO_SECURE: "false"
  JWT_SECRET: ${JWT_SECRET:?set in .env}
  ADMIN_USERNAME: ${ADMIN_USERNAME:-admin}
  ADMIN_PASSWORD: ${ADMIN_PASSWORD:?set in .env}
  CORS_ORIGINS: '["http://localhost:5173","http://localhost:3000","http://localhost"]'
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

services:
  backend:
    environment:
      <<: *app-env
  worker:
    environment:
      <<: *app-env
```

- One block, both services — the "keep backend and worker in sync by hand"
  rule collapses to "add it to `x-app-env`". A variable still only reaches
  a container if present in the (now shared) env block.
- Secrets switch from insecure fallbacks (`${JWT_SECRET:-dev-only…}`) to
  compose-level required syntax (`${VAR:?message}`) — `docker compose up`
  without a populated `.env` fails immediately with a clear message instead
  of booting with dev credentials. Non-secrets keep benign fallbacks.
  Postgres/MinIO infra-service credentials keep their `:-rtm` fallbacks
  (internal-only; `.env` from `.env.example` overrides them), and
  `minio-init` is untouched.
- The union of today's backend block and worker block is intentional: the
  worker gains `JWT_SECRET`/`ADMIN_*`/`CORS_ORIGINS`/`COOKIE_SECURE`
  (needed to boot now that they're required; the extras are harmless), and
  nothing is dropped from either service.

## Documentation updates

- `README.md` config section: document the group structure, the
  required-vs-optional split (the R/C rows above), and the new fail-fast
  behavior (what the error looks like, fix = set the variable).
- `CLAUDE.md`: update the "when adding a setting" rule — now: add the field
  to the right group in `Settings`, `.env.example`, the single `x-app-env`
  block, and README.
- `.env.example`: required-variable annotations (above).

## Testing (per quality gates)

- **Unit:** per-group tests — required field missing ⇒ `ValidationError`
  naming the env var (with `monkeypatch.delenv` + `_env_file=None`); alias
  mapping (env `DATABASE_URL` populates `database.url`); LLM conditional
  validator (enabled+no key ⇒ error; disabled+no key ⇒ ok); Google fields
  stay `None` without error; factory routes flat overrides and rejects
  unknown keys.
- **Integration:** existing suite stays green (it exercises every consumer
  path); Alembic `upgrade head` against the test DB still works (conftest
  already runs it).
- **Smoke (manual, in-plan):** `uv run uvicorn app.main:app` boots with
  `.env`; fails with a clear error when a required var is unset;
  `uv run arq app.jobs.worker.WorkerSettings` boots; `docker compose up`
  backend + worker healthy; compose fails fast with `:?` message when
  `.env` is missing a secret.
- Gates per task: `ruff check` + `format --check`, strict `mypy`,
  `pytest -m "unit or integration"`.

## Out of scope

- DB-backed dynamic config layer, per-tier overrides, admin UI for budgets
  (`LlmRuntimeSettings` is deliberately shaped for that later work).
- Any route/service behavior change; frontend changes; new env vars.
- Rotating the dev secrets themselves (`.env.example` keeps dev values).

## Accepted risks

- **~40 mechanical call-site edits** across app + tests. Mitigated by
  strict mypy (every miss is a type error) and per-task green gates.
- **Startup now crashes where it previously limped** on missing env — this
  is the point, but it changes ops behavior: a container with an incomplete
  env block goes unhealthy instead of running with dev secrets. README
  documents the error shape.
- **Worker now validates LLM config** (it previously skipped
  `_validate_llm_startup`): `LLM_ENABLED=true` without `GEMINI_API_KEY`
  stops the worker too. Consistent fail-fast, called out in README.
- Direct `Settings()` construction outside the factory becomes awkward
  (required groups). Accepted: production code only uses `get_settings()`;
  tests use the factory.
