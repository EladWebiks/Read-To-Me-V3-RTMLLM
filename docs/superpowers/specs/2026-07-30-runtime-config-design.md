# DB-backed Runtime Config Layer (`app_settings` overrides) — Design

Date: 2026-07-30
Status: Proposed (core decisions fixed by owner; produced in autonomous session)

## Goal

Add a DB-backed dynamic configuration layer so operational tunables (LLM
orchestration budgets, assistant mode, HITL limits, scrape throttles,
download TTLs, feature flags) can change at runtime without a restart. This
delivers the storage, layering (env base + sparse DB overrides), typed
validation, per-process caching with invalidation, an admin CRUD API, and
one real consumer wired end-to-end. The backoffice UI and per-tier
membership overrides are later plans that consume this machinery.

## Owner decisions (fixed)

1. **Override model, not replacement.** Env `Settings` remain the base; the
   DB stores sparse overrides only. Effective config = env value unless a DB
   override exists for that key. **Empty table ⇒ behavior identical to
   today.**
2. **Strict whitelist.** Only runtime-tunable fields can carry DB overrides.
   Secrets, credentials, and infrastructure endpoints (`DATABASE_URL`,
   `REDIS_URL`, MinIO endpoint/credentials, JWT, Google OAuth,
   `GEMINI_API_KEY`) are NEVER DB-overridable — a DB compromise must not be
   able to redirect infrastructure, and the DB config layer cannot configure
   the DB connection itself. The whitelist is derived FROM the pydantic
   sub-models (introspection for fully-tunable groups, an explicit registry
   validated against the models for partially-tunable groups) so a new
   tunable field cannot silently miss validation.
3. **Typed validation on write.** An override is validated against the exact
   pydantic field type **and constraints** it overrides before storing.
   Unknown keys and type mismatches are rejected at the API boundary with
   typed 4xx errors.
4. **Caching:** per-process in-memory cache with a ~30s TTL, plus immediate
   invalidation in the writing process. No Redis pub/sub now (documented
   upgrade path below).

## Sequencing (hard dependencies)

Start ONLY after both of these are merged to `main`:

1. **Config restructure** (`2026-07-29-config-restructure`) — provides the
   grouped sub-models (`settings.llm_runtime`, `settings.scrape`,
   `settings.storage`, `settings.audio`), the runtime-tunable
   classification, and the `tests/factories.py::make_settings` hermetic
   factory this design builds on.
2. **Authorization rework** (`2026-07-29-authorization-rework`) — provides
   `require_admin` in `app/core/deps.py`, `users.is_admin`, and the 403
   `NotAuthorizedError` mapping the admin API depends on.

Independent of the llm_executions user_id migration.

## Architecture

```
                    ┌──────────────────────────────────────────┐
                    │ modules/runtime_config                    │
 env (.env) ──────► │  registry.py   whitelist + TypeAdapters   │
 get_settings()     │  models.py     app_settings, _audit       │
        │           │  repository.py DB access (this module)    │
        │           │  service.py    RuntimeConfigService       │
        ▼           │  cache.py      per-process TTL cache      │
 base Settings ───► │  router.py     /api/admin/settings CRUD   │
                    └──────────────┬───────────────────────────┘
                                   │ effective_settings()
                                   ▼
   core/deps.get_effective_settings ──► consumers (chat router → …
                                        → RunBudget.from_settings)
```

- `router → service → repository → DB`; no other module touches
  `app_settings*` tables. Consumers use `RuntimeConfigService` (or the
  `get_effective_settings` dependency) only.
- `core/deps.py` imports `RuntimeConfigService` — the same established
  precedent as its existing `AuthService` import.
- The worker (arq) has no request cycle: it constructs
  `RuntimeConfigService(session, get_settings())` with a `SessionLocal()`
  session directly — no `Depends` anywhere in the service.

## Data model

Two tables in **one reversible migration**. (The original goal sketched one
table; a second, append-only audit table is required because
`clear_override` deletes the override row — without an audit row the
deletion and its actor would be unattributable. This follows the existing
append-only audit precedent, `tool_calls`.)

### `app_settings` — current overrides (sparse; empty = no behavior change)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `uuid4` default |
| `key` | `varchar(128)` | unique, indexed; e.g. `llm_runtime.max_turn_cost_usd` |
| `value` | JSONB | the raw JSON value (scalar or list) |
| `updated_by` | UUID FK → `users.id` | NOT NULL, indexed — every change attributable |
| `created_at` / `updated_at` | timestamptz | `now()` defaults, `onupdate` |

### `app_settings_audit` — append-only history (never updated/deleted)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `key` | `varchar(128)` | indexed (non-unique) |
| `action` | `varchar(16)` | `"set"` or `"clear"` |
| `old_value` | JSONB nullable | value before the write (`NULL` on first set) |
| `new_value` | JSONB nullable | value after the write (`NULL` on clear) |
| `actor_id` | UUID FK → `users.id` | NOT NULL, indexed |
| `created_at` | timestamptz | |

**Deliberate deviation from the soft-delete convention:** `app_settings`
rows are hard-deleted on `clear_override`. A soft-deleted row would break
the unique `key` constraint on re-set (requiring a partial index) and would
duplicate what the audit table already preserves. History and attribution
live in `app_settings_audit`; the overrides table stays a clean
"current state" set where *absence of a row means env value* — the property
the whole layering model rests on.

## Whitelist registry (`modules/runtime_config/registry.py`)

Keys are `"<section>.<field>"` where `section` is the attribute name on the
root `Settings` and `field` is the attribute on the group model.

- **Fully-tunable sections (derived by introspection — every field of the
  group is tunable, and a new field added to the group is automatically
  tunable *and* automatically validated):**
  - `llm_runtime` → `LlmRuntimeSettings` (all 12 fields: `max_tool_iters`,
    `max_external_calls`, `max_turn_tokens_in`, `max_turn_tokens_out`,
    `max_turn_cost_usd`, `run_deadline_seconds`, `context_recent_messages`,
    `summary_trigger_tokens`, `summary_max_output_tokens`,
    `assistant_mode`, `hitl_ttl_seconds`, `max_hitl_rounds`)
- **Partially-tunable sections (explicit field lists; a typo'd or renamed
  field fails at import time because the registry resolves
  `model_fields[name]` eagerly, and unit tests pin the exact contents):**
  - `scrape` → `timeout_seconds`, `max_bytes`, `delay_seconds`
  - `storage` → `download_job_ttl_hours`, `signed_url_expires_seconds`
  - `audio` → `sapi_proxy_enabled`

Everything else — `database`, `redis`, `auth`, `google`, `app`, `llm`
(provider config incl. `gemini_api_key` and `enabled`), and the storage
endpoint/credential fields — is **not in the registry and can never be
overridden**. `llm.enabled` is deliberately excluded even though it looks
like a feature flag: it participates in the startup `GEMINI_API_KEY`
validator and gates provider secrets; flipping it belongs to deploy config.

> **Classification note:** the config-restructure spec's field table marks
> only the 12 `llm_runtime` fields as bucket T. The owner's directive for
> this plan explicitly names scrape throttles, download TTLs, and feature
> flags as runtime-tunable, so this registry extends that bucket with the
> `scrape`/`storage`/`audio` entries above. **This registry is now the
> canonical runtime-tunable classification**; the restructure spec's table
> is historical.

Each registry entry carries a `pydantic.TypeAdapter` built from the field's
annotation *and* its `FieldInfo` (`TypeAdapter(Annotated[annotation,
field_info])`), so type **and** declared constraints (`ge`, `gt`,
`Literal[...]`) are enforced identically on write and on read.

### Field constraints (added by this plan)

"Validated against the field's constraints" is only meaningful if the
tunable fields declare constraints. Today they don't (an override of
`max_tool_iters = -5` would type-check). This plan adds bounds to the
tunable fields in `core/config.py`:

| Field | Constraint |
|---|---|
| `llm_runtime.max_tool_iters`, `max_turn_tokens_in`, `max_turn_tokens_out`, `run_deadline_seconds`, `context_recent_messages`, `summary_trigger_tokens`, `summary_max_output_tokens`, `hitl_ttl_seconds` | `ge=1` |
| `llm_runtime.max_external_calls`, `max_hitl_rounds` | `ge=0` |
| `llm_runtime.max_turn_cost_usd` | `gt=0` |
| `llm_runtime.assistant_mode` | `Literal["internal_only", "external_allowed"]` (matches the `Mode` StrEnum) |
| `scrape.timeout_seconds` | `ge=1` |
| `scrape.max_bytes` | `ge=1024` |
| `scrape.delay_seconds` | `ge=0` |
| `storage.download_job_ttl_hours` | `ge=1` |
| `storage.signed_url_expires_seconds` | `ge=60` |

These also harden env config (a nonsense `.env` value now fails fast), which
is consistent with the restructure's fail-fast direction.

## Service API (`RuntimeConfigService`)

Constructed as `RuntimeConfigService(session: AsyncSession, settings:
Settings)` — usable from FastAPI (via `get_db`) and from arq jobs (via
`SessionLocal()`) identically.

- `async get_effective(group_cls: type[GroupT]) -> GroupT` — one settings
  group with overrides applied (`base.model_copy(update=...)`); typed by
  the group class (e.g. `await svc.get_effective(LlmRuntimeSettings)`).
  This realizes the goal's `get_effective(settings_section)` with the
  section identified by its group class instead of a string, so consumers
  get static typing for free.
- `async effective_settings() -> Settings` — a full `Settings` clone with
  every tunable section replaced by its effective version; returns the base
  object untouched when no overrides exist. This is what the FastAPI
  dependency returns, so a consumer switches from static to effective
  settings by swapping `Depends(get_settings)` →
  `Depends(get_effective_settings)` — one call site at a time, no other
  code changes.
- `async list_overrides() -> list[OverrideRead]` — current DB overrides.
- `async list_effective() -> list[EffectiveSettingRead]` — every
  whitelisted key with `effective_value`, `env_value`, `overridden`, and
  attribution (`updated_by`/`updated_at`) when overridden (feeds the admin
  GET).
- `async set_override(key, value, updated_by) -> OverrideRead` — validate
  via the registry adapter → upsert → audit row (`set`, old→new) → cache
  invalidate → log **key and actor only**.
- `async clear_override(key, updated_by) -> None` — delete → audit row
  (`clear`, old→NULL) → cache invalidate → log key and actor only.
  Clearing a key with no stored override raises `OverrideNotFoundError`
  (explicit 404 beats silent idempotency for a backoffice UI).

Writes run in the caller's session/transaction (`get_db` commits on
success), so the override row and its audit row commit atomically.

### Read-path robustness

`get_effective`/`effective_settings` re-validate stored JSON through the
same adapter. A row that no longer validates (e.g. a field's type or
constraint changed in a later release) or whose key left the whitelist is
**skipped with a warning log (key only)** — fail-open to the env value.
A bad row must never take down chat or the worker.

## Caching & invalidation (decided)

- One module-level cache entry per process: the validated overrides mapping
  (`dict[key, value]`), loaded with a single `SELECT` over `app_settings`
  (the table is small by construction — it holds only admin-set overrides).
- TTL: `CACHE_TTL_SECONDS = 30.0` (module constant — not itself
  env-tunable; YAGNI). Expiry via `time.monotonic()`.
- Every write calls `invalidate()` → the writing process (the API serving
  the backoffice) sees the change immediately.
- Other processes (the arq **worker**, other API workers) converge within
  the TTL. **Plainly: a budget/throttle change may take up to 30 seconds to
  reach the worker.** This is accepted for operational tunables.
- Warm-cache `get_effective` performs **zero DB queries** — cheap enough to
  call per-request / per-turn.
- **Upgrade path (do NOT build now):** if TTL lag ever matters, add Redis
  pub/sub — writers PUBLISH the changed key on an `app_settings` channel;
  every process SUBSCRIBEs and calls `invalidate()` on message. The cache
  module is the single seam where that lands.
- Benign race: two coroutines may both find the cache cold and both load —
  last write wins with identical data. No locking needed on a single event
  loop.

## FastAPI dependency (`core/deps.py`)

```python
async def get_effective_settings(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Settings:
    """Settings with DB overrides applied to runtime-tunable sections."""
    return await RuntimeConfigService(session, settings).effective_settings()
```

Lives alongside `get_settings`; consumers migrate one `Depends` at a time.

### Proof consumer (wired in this plan)

`_chat_service` in `modules/llm/router.py` switches its settings dependency
to `get_effective_settings`. That single swap makes the whole chain —
`ChatService → OrchestrationService → RunBudget.from_settings` (which reads
`settings.llm_runtime.max_turn_cost_usd` and the other budget caps) — read
effective values, covering both `run` and `resume_confirm`. An integration
test proves an override to `llm_runtime.max_turn_cost_usd` changes budget
enforcement in the same process without a restart, and a unit test pins the
dependency wiring itself. `_llm_service` and other call sites stay on
`get_settings` — they migrate later, one at a time, as needed.

## Admin API (`/api/admin/settings`, all behind `require_admin`)

| Endpoint | Behavior |
|---|---|
| `GET /api/admin/settings` | `{"settings": [EffectiveSettingRead, …]}` — every whitelisted key, its effective + env value, `overridden` flag, attribution. |
| `PUT /api/admin/settings/{key}` | Body `{"value": <json>}`. Validates and upserts; returns `OverrideRead`. |
| `DELETE /api/admin/settings/{key}` | Clears the override; `204`. |

`updated_by` always comes from the authenticated admin's server session
(`require_admin` → `UserRead.id`) — never from the request body.

Typed errors (module `exceptions.py`, mapped centrally in
`core/exceptions.py`):

| Exception | Status | When |
|---|---|---|
| `UnknownSettingKeyError` | 404 | key not in the whitelist registry (unknown and non-whitelisted are indistinguishable by design — the registry IS the key space) |
| `OverrideNotFoundError` | 404 | DELETE for a whitelisted key with no stored override |
| `SettingValueInvalidError` | 422 | value fails the field's type/constraint validation (detail carries the pydantic error message; nothing is logged) |

Anonymous → 401, authenticated non-admin → 403 (existing auth/authz
handlers). No frontend in this plan — the backoffice plan consumes these
endpoints.

## Module layout

```
backend/app/modules/runtime_config/
  __init__.py
  models.py       # AppSetting, AppSettingAudit (this module's tables only)
  registry.py     # whitelist + TypeAdapters (imports core/config groups)
  schemas.py      # OverrideRead, EffectiveSettingRead, SettingValueWrite, SettingsListResponse
  repository.py   # AppSettingsRepository (+ AuditEntry dataclass)
  service.py      # RuntimeConfigService
  cache.py        # per-process TTL cache (get_cached / put / invalidate)
  exceptions.py   # typed domain exceptions
  router.py       # admin CRUD, thin, authz via require_admin
```

Name `runtime_config` avoids colliding with `core/config.py`. Registered in
`core/orm.py` (model import) and `main.py` (router).

## Logging rules

- Writes log `{"key": …, "actor": str(user_id)}` at INFO. **Override values
  are never logged** — a future tunable could be sensitive.
- Read-path skips log the offending key only, at WARNING.
- The 422 response body may echo the pydantic message to the admin who sent
  the value (response ≠ log).

## Testing

- **Unit:** registry contents (llm_runtime introspection completeness;
  partial lists exist on their models; forbidden prefixes/fields absent);
  adapter type + constraint enforcement; new config constraints reject
  out-of-range env/factory values; cache TTL/put/invalidate semantics
  (monkeypatched `monotonic`); dependency-wiring pin for `_chat_service`.
- **Integration (Postgres):** migration round-trip; set/clear/list with
  audit rows and attribution; unique-key upsert; effective layering (env
  base, override wins, clear restores env, unknown/invalid rows skipped);
  admin API matrix (401 anon / 403 non-admin / 200 admin), 404 unknown key,
  404 clear-nothing, 422 invalid value; the no-restart proof (override →
  `get_effective_settings` → `RunBudget` enforces the new cap in the same
  process).
- Gates per task: `ruff check` + `format --check`, strict `mypy`,
  `pytest -m "unit or integration"`.

## Out of scope

- Backoffice frontend (consumes the admin API later).
- Per-tier membership overrides (layers on `get_effective` later).
- Redis pub/sub invalidation (documented upgrade path only).
- Migrating consumers beyond the one proof call site.
- New env vars (`CACHE_TTL_SECONDS` is a code constant).

## Accepted risks

- **Up to 30s staleness in non-writing processes** (worker, other API
  workers). Accepted per owner decision; upgrade path documented.
- **Two tables where the goal sketched one.** Accepted: attribution of
  `clear` operations is otherwise lost; matches the `tool_calls` audit
  precedent.
- **`model_copy(update=...)` bypasses model-level validators** on the
  effective object. Safe today: per-field adapters enforce field
  types/constraints, and no tunable group has a model-level validator
  (`LlmSettings`' key validator is in a non-tunable group). If a tunable
  group ever gains a `model_validator`, the effective path must switch to
  full-model revalidation.
- **Constraint tightening can break exotic `.env` values** (e.g.
  `SCRAPE_DELAY_SECONDS=-1` previously "worked"). Intended fail-fast;
  release note in README.
