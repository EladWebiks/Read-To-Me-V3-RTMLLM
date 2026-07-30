# DB-backed Runtime LLM Model Catalog — Design

Date: 2026-07-30
Status: Proposed (core decisions fixed by owner; produced in autonomous session)

## Goal

Make the database the runtime source of truth for the LLM model catalog so
providers and models can be enabled, disabled, added, and re-priced from the
backoffice without a deploy. Today `model_providers` /
`model_configurations` are seeded at startup and never read back — the DB
`enabled` flags do nothing, pricing lives only in code, and
`models_for_capability()` reads a static tuple. This plan completes the
repo's existing golden rule: *"Model/provider config is data, never
hardcoded."*

## Current state (verified)

- `modules/llm/registry.py` holds a static `MODEL_CATALOG:
  tuple[ModelSpec, ...]`; `list_models()`, `get_model()`, and
  `models_for_capability()` read ONLY it.
- `modules/llm/seed.py` upserts the catalog into `model_providers` /
  `model_configurations` at startup (insert-if-missing already), but nothing
  reads those tables back — dead data.
- `model_configurations` has NO pricing columns and no `updated_at`;
  pricing (`input_cost_per_1m` / `output_cost_per_1m`) exists only on the
  in-code `ModelSpec`.
- `ModelRouter.candidates()` (sync) orders candidates preferring
  `settings.llm.provider` / `settings.llm.model`.
- `providers/__init__.py::build_provider_for` re-looks-up the spec in the
  static registry even though callers already hold a `ModelSpec`.

## Owner decisions (fixed)

1. **DB is runtime truth; the code catalog becomes seed-only defaults.**
   `registry.py` survives only as the definition of what seeding inserts.
   Runtime capability lookup, enabled filtering, and pricing all come from
   the DB.
2. **Seed is insert-if-missing, never overwrite.** A restart must NEVER
   clobber admin edits (enabled flags, pricing). New provider/model rows in
   the code catalog are added; existing rows are left untouched. A model
   *removed* from the code catalog is left alone in the DB — the admin
   disables it if desired.
3. **Catalog reads are cached** with the same short-TTL in-process pattern
   as `modules/runtime_config/cache.py` (~30s TTL + `invalidate()` on write
   in the writing process; the worker converges within the TTL; no Redis
   pub/sub). The router must not hit the DB per call when the cache is warm.
4. **Preferred default model stays OUT of this plan.**
   `settings.llm.provider` / `settings.llm.model` still select the
   *preferred* model; this plan owns what EXISTS and is ENABLED. The
   `prefer_provider` / `prefer_model` ordering logic is kept, fed from
   settings as today.
5. **Provider enablement ≠ adapter existence.** A DB row can only be served
   if a registered adapter factory exists for its provider. Validate on
   write (reject a catalog row for a provider with no adapter) AND on read
   (skip-with-warning, never crash, if an adapter disappears).

## Sequencing

- Requires the authorization rework (`require_admin` in `core/deps.py`) —
  **merged**.
- Reuses the caching pattern from the runtime-config plan — **landed**
  (`modules/runtime_config/cache.py`); this plan copies the pattern (module
  seam, TTL constant, `invalidate()`), not the code. If a third TTL cache
  ever appears, consolidate into `core/`; not now (YAGNI).
- Independent of the `llm_executions` user_id migration.

## Architecture

```
                          seed (startup, insert-if-missing only)
 registry.MODEL_CATALOG ────────────────────────────────┐
 (seed-only defaults)                                   ▼
                                        model_providers / model_configurations
                                          ▲ admin writes         │ reads
                                          │                      ▼
 /api/admin/llm/catalog ──► ModelCatalogAdminService   catalog.ensure_loaded(session)
 (require_admin)              (llm module only)          │  async DB → snapshot
                                   │ invalidate()        ▼
                                   └──────────► catalog snapshot (per-process,
                                                 30s TTL, tuple[ModelSpec, ...])
                                                        │ sync reads
                                                        ▼
                              catalog.models_for_capability / get_model / list_models
                                                        │
                                     ModelRouter.candidates() (sync, unchanged shape)
                                                        │
                                     LlmService / ChatService / telemetry (cost)
```

### The async-load / sync-read boundary

`ModelRouter.candidates()` is sync and must stay sync (called from sync and
async paths). Resolution:

- `modules/llm/catalog.py` holds a **per-process snapshot**
  (`tuple[ModelSpec, ...]`) with a 30s TTL, mirroring
  `runtime_config/cache.py` (`current_snapshot` / `put_snapshot` /
  `invalidate` + async `ensure_loaded(session)` that loads from the DB when
  cold/expired).
- Every `LlmService` public entry point awaits `ensure_ready()` (new) which
  awaits `catalog.ensure_loaded(self._session)` before any sync
  `candidates()` read. Warm-cache calls perform zero DB queries.
- Sync reads on a cold cache return an empty catalog — which surfaces as
  `NoCandidateModelError`, never a crash. Entry points always warm first,
  so this is only reachable if the DB itself is unreachable at load time
  (which raises loudly from `ensure_loaded`).

### `ModelSpec` (unchanged shape, new provenance)

The frozen `ModelSpec` dataclass stays the internal currency (router,
telemetry, providers all keep their signatures). Snapshot entries are built
from DB rows: `enabled = provider.enabled AND model.enabled` (effective
enablement is computed at load; the snapshot keeps disabled rows so
`list_models(enabled_only=False)` still serves the public models endpoint).
Rows whose provider has no registered adapter are **excluded** from the
snapshot with a warning — they are unserveable. Capability strings that
don't round-trip through `ModelCapability` are dropped per-capability with
a warning (tolerate-and-warn on read; reject on write).

### Candidate ordering determinism

The static tuple's implicit order is replaced by `ORDER BY provider.name,
model_name` at load. Preference ordering (settings-preferred model first)
is applied on top, exactly as today. Fallback order beyond the preferred
model is therefore alphabetical — deterministic, and coincidentally
identical to today's order for the two seeded models.

## Data model (one reversible migration)

`model_configurations` gains:

| Column | Type | Notes |
|---|---|---|
| `input_cost_per_1m` | Float NOT NULL, server_default `0` | USD per 1M input tokens |
| `output_cost_per_1m` | Float NOT NULL, server_default `0` | USD per 1M output tokens |
| `updated_at` | timestamptz NOT NULL, `now()` default + onupdate | convention (golden rule 6) |
| unique `(provider_id, model_name)` | constraint `uq_model_configurations_provider_model` | guards admin POST and concurrent seed races (dedup before create) |

`model_providers` gains `updated_at` (same convention; provider rows are
now mutable via PATCH).

**Backfill:** existing rows get the code-catalog prices via literal
`UPDATE`s in the migration (`gemini-3.5-flash-lite` → 0.10/0.40,
`gemini-3.6-flash` → 0.30/2.50). Values are duplicated into the migration
on purpose — migrations never import app code. Downgrade drops the
constraint and columns.

## Seed semantics (explicit)

- `upsert_provider` / `upsert_model` are already insert-if-missing; they
  now also write pricing **on insert only**. An existing row is returned
  untouched — restart never overwrites `enabled` or pricing.
- A model removed from `MODEL_CATALOG`: nothing happens — the DB row stays;
  the admin disables it. (Its adapter still exists, so it keeps working
  until disabled.)
- Startup seeding guarantees the happy path: a fresh DB always has the
  seeded, enabled defaults before the first request.

## Cost path audit (exact call sites)

Per-call unit prices must come from the DB catalog row used for the call.
All cost math flows through `ModelSpec`, and every runtime `ModelSpec` will
originate from the snapshot, so the cost path needs **no code change** —
only provenance proof:

| Site | Role |
|---|---|
| `modules/llm/telemetry.py:182-183` | `ExecutionWrite.unit_cost_in/out ← ctx.model.input/output_cost_per_1m` (persisted to `cost_records.unit_cost_in/out`) |
| `modules/llm/telemetry.py:189-195` | `estimate_cost(model, usage)` — computes `llm_executions.cost` / `cost_records.total_cost` from `model.*_cost_per_1m` (short-circuits when the provider reported `usage.cost_usd`) |
| `modules/llm/service.py:147` and `:268` | the only two `TelemetryContext(...)` constructions; `model=` comes from `ModelRouter.run()`'s returned spec or `candidates()[0]` |
| `modules/llm/model_router.py:36-42, 58` | `candidates()` — the single source of runtime `ModelSpec`s (switches to the snapshot) |

Chat/orchestration reuse `LlmService.router` / `.telemetry`, so they
inherit the same provenance. An integration test proves an admin reprice
reaches `cost_records.unit_cost_in/out` and `total_cost`.

## Read-path rewiring map

| Site | Change |
|---|---|
| `registry.py` | keeps `ModelSpec` + `MODEL_CATALOG` (docstring: seed-only defaults); `list_models` / `get_model` / `models_for_capability` are **removed** |
| `catalog.py` (new) | snapshot cache + async `ensure_loaded(session)` + sync `list_models` / `get_model` / `models_for_capability` (same signatures as the old registry functions) |
| `model_router.py:38` | `candidates()` reads `catalog.models_for_capability(...)` |
| `model_router.py:44-50` | `build()` calls `build_provider(ProviderBuildContext(settings, model))` directly — the spec is already in hand |
| `providers/__init__.py:28-38` | `build_provider_for` (and its registry import) removed; adds `KNOWN_ADAPTERS` / `has_adapter(name)` |
| `service.py` | new `async ensure_ready()` (enabled check + `ensure_loaded` + non-empty check); all entry points await it; `list_public_models` becomes async and reads the snapshot |
| `chat_service.py:63, 84` | `self._llm.ensure_enabled()` → `await self._llm.ensure_ready()` |
| `llm/router.py:61` | awaits `list_public_models()` |

## Admin API (`/api/admin/llm`, all behind `require_admin`)

Lives in `modules/llm/admin_router.py` (thin, HTTP only) → calls the llm
module's `ModelCatalogAdminService` — same placement pattern as
`runtime_config/router.py` (`/admin/...` prefix inside the owning module,
registered in `main.py`). Only the llm module touches these tables.

| Endpoint | Behavior |
|---|---|
| `GET /api/admin/llm/catalog` | All providers + models (including no-adapter rows), each with `enabled`, `effective_enabled` (model ∧ provider ∧ adapter), `has_adapter`, pricing, capabilities, `updated_at`. |
| `PATCH /api/admin/llm/catalog/providers/{provider}` | Body `{"enabled": bool}`. 404 if no provider row. |
| `PATCH /api/admin/llm/catalog/models/{provider}/{model_name}` | Body: any of `enabled`, `input_cost_per_1m`, `output_cost_per_1m` (partial; `ge=0` on prices). 404 if row missing. |
| `POST /api/admin/llm/catalog/models` | Full model definition. Provider must have a registered adapter (422 otherwise); capabilities validated as `list[ModelCapability]` (unknown string → FastAPI 422); duplicate `(provider, model_name)` → 409. Auto-creates the provider row (enabled) if the adapter exists but the row doesn't. |

Every successful write calls `catalog.invalidate()` — the writing process
sees the change immediately; other processes within the TTL. Writes log
provider/model/changed-field names only (no values needed; nothing here is
secret, but stay terse).

Typed errors (in `modules/llm/exceptions.py`, mapped centrally):

| Exception | Status |
|---|---|
| `CatalogProviderNotFoundError` | 404 |
| `CatalogModelNotFoundError` | 404 |
| `AdapterNotRegisteredError` | 422 |
| `DuplicateCatalogModelError` | 409 |

Anonymous → 401, non-admin → 403 (existing handlers). No frontend in this
plan — the backoffice consumes these endpoints later. Pricing appears only
in the admin response; the public `GET /api/llm/models` payload is
unchanged.

## Failure semantics

- **Empty or all-disabled catalog at call time** raises the existing
  `NoCandidateModelError` (mapped 503) loudly. Seeding at startup
  guarantees the happy path on a fresh DB; if an admin disabled everything,
  a restart does NOT re-enable (insert-if-missing) — the error is the
  correct, loud outcome.
- **Disabling ALL models degrades exactly like `llm_enabled=false` at the
  chat boundary:** `ChatService.stream_chat` / `stream_confirm` call
  `await self._llm.ensure_ready()` at the same pre-stream position where
  `ensure_enabled()` sits today. `ensure_ready` raises
  `NoCandidateModelError` (all-disabled) exactly where `LlmDisabledError`
  (llm off) is raised — before any SSE event, both mapped to 503. An
  integration test pins the parity.
- **Adapter disappears for a DB row:** skipped from the snapshot with a
  warning at load; never crashes. The admin GET still shows the row with
  `has_adapter: false`.
- **DB unreachable at load time:** `ensure_loaded` raises the underlying
  DB error — loud by design (same posture as any repository call).

## Constraints (restated)

- Only the llm module touches `model_providers` / `model_configurations`;
  the admin router calls the llm module's public service.
- Provider SDK imports stay confined to `modules/llm/providers/`.
- Capabilities stored in JSONB round-trip through `ModelCapability`:
  reject unknown strings on write; tolerate-and-warn on read.
- Tests build settings via `tests/factories.py::make_settings`, never
  `Settings()` directly (existing violations in touched tests are fixed in
  passing).
- Migration tested up/down/up. Strict mypy + ruff. Commits via
  `scripts/git-commit-clean.sh`, no attribution trailers.

## Existing tests whose behavior-source changes (explicit list)

| Test | Change |
|---|---|
| `tests/llm/test_registry.py` | query-function tests move to `tests/llm/test_catalog.py` (snapshot-backed); the file shrinks to seed-defaults assertions on `MODEL_CATALOG` |
| `tests/llm/test_model_router.py` | `candidates()` now reads the snapshot (warmed by an autouse fixture); `_settings()` switches from `Settings.model_validate` to `make_settings` |
| `tests/llm/test_llm_telemetry.py:31` | `get_model` import moves from `registry` to `catalog` (snapshot-backed) |
| every test constructing `LlmService`/`ChatService` | protected by a root-conftest autouse fixture that pre-warms the snapshot from `MODEL_CATALOG`, so unit tests see exactly the catalog they saw when it was static; DB-facing catalog tests call `catalog.invalidate()` explicitly |

## Testing

- **Unit:** snapshot cache TTL/put/invalidate (monkeypatched `monotonic`);
  row→spec conversion (effective enabled, adapter skip, unknown-capability
  tolerance); query functions over an injected snapshot;
  `ensure_ready` raises on empty snapshot; `ModelCreate` rejects unknown
  capability strings; pricing `ge=0` bounds.
- **Integration (Postgres):** migration up/down/up; seed inserts pricing;
  re-seed never overwrites admin edits; `ensure_loaded` reads seeded rows;
  disable-provider cascades to effective enablement; admin API matrix
  (401/403/200, 404s, 409, 422s); reprice → `cost_records` provenance;
  all-disabled ≙ `llm_enabled=false` chat-boundary parity.

## Out of scope

- Backoffice frontend (consumes the admin API later).
- Runtime-tunable preferred model (`settings.llm.provider/model` override
  belongs to the runtime_config whitelist, later).
- Audit table for catalog writes (runtime_config-style `_audit`) — catalog
  rows carry `updated_at`; full attribution can follow the
  `app_settings_audit` precedent later if the backoffice needs it.
- Redis pub/sub invalidation (same documented upgrade path as
  runtime_config: the cache module is the single seam).
- Deleting catalog rows (disable instead; keeps history and FK simplicity).

## Accepted risks

- **Up to 30s staleness in non-writing processes** — same accepted
  trade-off as runtime_config.
- **Two TTL-cache modules with the same shape** (`runtime_config/cache.py`,
  `llm/catalog.py`). Accepted: consolidating into `core/` for two users is
  premature; noted as the consolidation point if a third appears.
- **`registry.py` keeps the name "registry" while becoming seed-only.**
  Accepted to avoid churn in `ModelSpec` imports across the module;
  docstrings make the role explicit.
- **Alphabetical fallback ordering** replaces implicit tuple order.
  Deterministic and currently identical; a future `sort_order` column is
  the escape hatch if explicit ordering is ever needed.
