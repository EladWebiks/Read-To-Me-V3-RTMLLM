# Tier-Based Usage Management — Design Spec

**Status:** Approved (decisions locked by maintainer 2026-07-31; **amended same day** to cover non-LLM quota dimensions — see §3.0)
**Plans:**
- [Part A — per-tier orchestration budgets](../plans/2026-07-31-tier-budgets-part-a.md) (per-turn caps: schema + resolution + loop wiring + admin surface)
- [Part B — quota infrastructure + LLM quotas](../plans/2026-07-31-monthly-quotas-part-b.md) (keyed `membership_quotas` table, quotas module, chat enforcement, admin/UI)
- [Part C — non-LLM quota dimensions](../plans/2026-07-31-job-quotas-part-c.md) (audio chapters, storage bytes, scrape chapters, EPUB imports)

Part B strictly depends on Part A (per-turn schema + `UserRead` threading). Part C strictly depends on Part B (quotas module). Part C's per-domain tasks are independent of each other.

## 1. Problem

Orchestration budgets (tool iterations, external calls, turn tokens, turn cost, wall clock, HITL rounds) are global today: one `LlmRuntimeSettings` group applies to every user. With memberships in place (`users.membership`, `Membership` StrEnum) and Stripe on the roadmap, budgets must become per-tier, and each user needs usage quotas derived from recorded work — **not just LLM tokens**: MP3 generation (CPU + MinIO storage), scrape jobs, and EPUB imports are real per-user costs the job tables already (mostly) record. The quota schema must hold multiple quota kinds **now**; retrofitting a second dimension after Stripe maps products to tiers is much more painful.

Three parts, one model:

- **Part A — per-tier per-turn budgets:** the per-turn caps move from global settings to membership-tier lookups.
- **Part B — quota infrastructure + LLM quotas:** a keyed, multi-dimension quota store; monthly LLM token/cost quotas enforced at chat turn start.
- **Part C — non-LLM quota dimensions:** audio chapters, storage bytes, scrape chapters, EPUB imports enforced at job creation.

## 2. Current state (verified 2026-07-31)

- `Membership` StrEnum ([membership.py](../../../backend/app/modules/users/membership.py)) currently has one value: `FREE`. Rank ordering lives only in `MEMBERSHIP_RANK`.
- All budget caps live in `LlmRuntimeSettings` (`config.py:134-176`): `max_tool_iters=6`, `max_external_calls=3`, `max_turn_tokens_in=64_000`, `max_turn_tokens_out=8_192`, `max_turn_cost_usd=0.05`, `run_deadline_seconds=60`, `max_hitl_rounds=3`. The **whole group** is a `_FULL_SECTION` in `runtime_config/registry.py`, so every budget key is already runtime-tunable; the chat path already reads effective settings (`llm/router.py::_chat_service` uses `get_effective_settings`).
- `RunBudget` ([budget.py](../../../backend/app/modules/orchestration/budget.py)) holds caps + counters; the HITL freeze snapshot stores **counters only** — resume re-reads settings (`service.py:227`). Part A removes that re-resolution.
- `llm_executions` has NOT NULL `user_id` + composite `ix_llm_executions_user_id_created_at` (migration `cc8afb8f06aa`, current head). `LlmService.usage_summary(user_id, period_start, period_end)` aggregates it.
- **Job tables (Part C meters):**
  - `download_jobs`: `user_id` (indexed), `total_count` (chapters in the job), `object_key`, `expires_at` (TTL + purge), `created_at`. **No size column** — storage metering needs one. MP3 bytes are written in `app/jobs/tasks.py::_process` (`put_bytes` of the combined file plus per-chapter parts), where sizes are in hand.
  - `scraping_jobs`: `user_id` (indexed), `chapters_done`, `created_at`. Single creation choke point `ScrapingService.create_job` (REST + HITL scrape tool).
  - **EPUB imports are in-memory only** (`imports/jobs.py`, "v2 parity") — no durable table, nothing to meter; this also deviates from golden rule 7 (jobs are durable). Part C adds a durable import log.
- Backoffice exists (`modules/admin/` aggregation router + `frontend/src/features/admin/` screens). Frontend has a shared `ApiError { status, message }` surfaced by the existing error handling.

**Hard dependencies — all verified merged:** authorization rework (Membership enum + rank map), runtime_config (effective-settings chain), llm_executions `user_id` migration (usage summary method).

## 3. Decisions (locked)

### 3.0 Amendment (2026-07-31): quotas are keyed and multi-dimension; ownership splits

The original decision put per-turn caps **and** two monthly LLM quota columns on one orchestration-owned `membership_policies` table. Amended (maintainer-approved) before any implementation:

- `membership_policies` (orchestration-owned) keeps **only the seven per-turn caps** — genuinely loop-safety config.
- All quotas — LLM included — live in a keyed table **`membership_quotas`** owned by a new leaf module **`modules/quotas/`**.
- **Why the ownership split:** downloads/scraping/imports services must enforce quotas at job creation, and domain code **must not import the orchestrator** (golden rule). Quota resolution therefore lives below both orchestration and the domain modules. Orchestration keeps per-turn budget enforcement; quotas keeps commercial usage limits.
- **Why keyed rows, not columns:** adding a quota dimension after Stripe maps products to tiers becomes "insert a row + register a kind in code" — no migration, no API change, no UI change (the admin screen is registry-driven).

### 3.1 Two tables

**`membership_policies`** (orchestration module) — one row per `Membership` value, seeded all-NULL:

| Column | Type | NULL means |
|---|---|---|
| `max_tool_iters` | int, nullable | **inherit** (runtime_config → env) |
| `max_external_calls` | int, nullable | **inherit** |
| `max_turn_tokens_in` | int, nullable | **inherit** |
| `max_turn_tokens_out` | int, nullable | **inherit** |
| `max_turn_cost_usd` | float, nullable | **inherit** |
| `run_deadline_seconds` | int, nullable | **inherit** |
| `max_hitl_rounds` | int, nullable | **inherit** |

Plus `id` (UUID PK), `membership` (String(32), unique, NOT NULL), `created_at`, `updated_at`. NULL always means **inherit** here — per-turn caps are safety rails with a global fallback; they can never be absent. Row key tied to the enum by app-level validation (typed PATCH path param; seeding iterates the enum; a test asserts every enum value has a row).

**`membership_quotas`** (quotas module) — sparse; **row absent = unlimited**, so no seeding:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `membership` | String(32), NOT NULL | app-validated against the enum |
| `quota_kind` | String(32), NOT NULL | app-validated against `QuotaKind` |
| `limit_value` | Float, NOT NULL, > 0 | float64 is exact for ints ≤ 2^53 — fine for tokens/chapters/bytes |
| `created_at` / `updated_at` | | |
| unique | `(membership, quota_kind)` | |

> **NULL/absence semantics, loud and simple after the amendment:** per-turn columns NULL = inherit; a quota **row absent** = unlimited. There is no nullable quota column anymore, so the old dual-NULL footgun is gone.

### 3.2 Quota kinds — registry in code, limits in DB

`QuotaKind` StrEnum + metadata registry (label, unit, window) in `modules/quotas/kinds.py`. The admin API serves the registry, so new kinds appear in the backoffice automatically.

| Kind | Window | Meter (owner measures via its own repository) |
|---|---|---|
| `llm_tokens` | month | `SUM(tokens_in + tokens_out)` from `llm_executions` (existing `usage_summary`) |
| `llm_cost_usd` | month | `SUM(cost)` from `llm_executions` |
| `audio_chapters` | month | `SUM(total_count)` of the month's `download_jobs` — work-proportional CPU proxy |
| `storage_bytes` | **standing** | `SUM(size_bytes)` of non-expired complete `download_jobs` (new column, Part C) |
| `scrape_chapters` | month | `SUM(chapters_done)` of the month's `scraping_jobs` |
| `epub_imports` | month | `COUNT(*)` of the month's **completed** rows in the new `epub_imports` table |

Work-proportional meters (chapters, not job counts) were chosen deliberately: a 500-chapter job is not a 2-chapter job, and the query cost is identical. `storage_bytes` is a **standing** (level) quota — compared against current retained bytes, no monthly reset; MP3 TTL + purge still bounds it naturally.

### 3.3 Resolution chain (per-turn caps): specificity-wins, NOT strictest-wins

```
effective cap = membership_policies.<field>  if NOT NULL      (most specific)
                else runtime_config override if present        (admin runtime tuning)
                else env/default from Settings                 (base)
```

A tier value always wins, even when *looser*. In implementation this is two layers: orchestration receives Settings from `get_effective_settings`, which already collapses the bottom two. A missing tier row resolves as all-NULL (full inheritance) with a warning — fail-open to global defaults is correct; global caps still bound the run.

Quota limits have no chain: `membership_quotas` row if present, else unlimited.

### 3.4 Admin exemption is asymmetric

- **Per-turn budgets apply to everyone, admins included** — safety rails against runaway loops.
- **All quota kinds exempt `is_admin` users** — quotas are a commercial construct. The exemption lives in one place (`QuotaService.limits_for*` returns exempt limits), so every enforcement point inherits it.

### 3.5 Enforcement points and semantics

- **Per-turn caps resolve ONCE at turn start** (`PolicyService.resolve(user)` → frozen `ResolvedPolicy` → `RunBudget.from_policy`). **Frozen across HITL pauses:** resolved caps are written into the freeze snapshot and restored verbatim on resume; the resume path must never re-resolve. *Wall-clock nuance:* the snapshot stores the resolved `run_deadline_seconds` value; resume restarts the window from it (`now + value`) — carrying the original absolute deadline across a pause of up to `hitl_ttl_seconds` would expire every resumed run instantly. Legacy snapshots without caps fall back to a fresh resolve (one-time).
- **LLM quotas** (`llm_tokens`, `llm_cost_usd`): checked in `OrchestrationService.run` after policy resolution and **before any provider call** (before conversation-context build, which can itself call the provider for summarization). Rejection = structured SSE error (§6), never a bare 4xx — the stream is already open. Resume-confirm does **not** re-check (same turn). The user's message stays persisted; only the assistant turn is refused.
- **`audio_chapters` + `storage_bytes`**: checked in `DownloadsService.create` — the single choke point for the REST route, single-chapter path, and the `create_audio_download` LLM tool.
- **`scrape_chapters`**: checked at the top of `ScrapingService.create_job` (REST + HITL scrape tool). Enforced at creation only; a running job may finish past the line (mid-job overage accepted, bounded by the job's own chapter range).
- **`epub_imports`**: checked in `ImportService.start` (both entrypoints funnel there), metered from the durable log. Completed imports count; failures don't (failed imports are usually our bugs, not delivered value).
- **Comparison is `>=` everywhere:** at/over the cap blocks the next unit of work; just-under may finish one more unit and land over (bounded per-turn / per-job). Documented, accepted.
- **Caller-metered pattern:** the quotas module resolves limits and compares (`enforce(kind, used, limits)`); each domain measures its own usage through its **own** repository. Keeps `quotas` a leaf module and respects "repository touches only its module's tables". `QuotaService.limits_for(user: UserRead)` serves orchestration (has the user object); `limits_for_user_id(user_id)` serves domain services (they only carry `user_id` — the quotas module resolves membership/is_admin via the users **service**, an allowed direction).
- Metering queries are single index scans on existing `(user_id, …)` indexes; acceptable at current scale. **Documented upgrade path (do not build):** cached per-user counters if metering ever shows in latency traces.
- **Freshness:** limits are read per check, uncached — a tier upgrade or an admin raising a quota unblocks the very next attempt.

### 3.6 Month boundary = calendar month in UTC

`[first-of-month 00:00 UTC, first-of-next-month 00:00 UTC)`, helper owned by the quotas module. Stripe billing-period anchors are a known future adjustment, out of scope. Standing kinds (`storage_bytes`) have no window and no `resets_at`.

## 4. Component design

### 4.1 `modules/quotas/` (new leaf module, Part B)

- `kinds.py`: `QuotaKind(StrEnum)` + `KIND_REGISTRY: dict[QuotaKind, KindMeta]` (label, unit, window `"month" | "standing"`). Adding a dimension = one enum value + one registry entry.
- `models.py`: `MembershipQuota` (§3.1). Registered in `core/orm.py`.
- `repository.py`: `get(membership, kind)`, `list_for_membership`, `list_all`, `upsert`, `delete` — this module's table only.
- `exceptions.py`: `QuotaExceededError(kind, limit, used, resets_at: datetime | None)`; `str(exc)` is user-facing copy built from the registry (month: "Monthly {label} quota reached… resets {date}"; standing: "{label} quota reached — free up space or upgrade").
- `service.py`: `QuotaLimits` (frozen: `exempt: bool`, mapping kind→limit, `limit(kind)`, `any_limited(*kinds)`); `QuotaService(session)` with `limits_for(user)`, `limits_for_user_id(user_id)`, static `current_month_window(now)`, static `enforce(kind, used, limits, *, resets_at)`; admin methods `list_quotas`, `set_quota`, `clear_quota`.
- `admin_router.py`: `GET /api/admin/membership-quotas` (registry + rows), `PUT /api/admin/membership-quotas/{membership}/{kind}` (`{limit_value: > 0}`), `DELETE …/{membership}/{kind}` (= unlimited), behind `require_admin` — the runtime_config set/clear pattern. Typed path params → 422 on unknown tier/kind.
- HTTP mapping: `QuotaExceededError` → **429** with the user-facing detail, registered in `core/exceptions.py`.

### 4.2 Orchestration (Parts A–B)

- `models.py`/migration/seed: `membership_policies`, per-turn columns only.
- `policy.py`: `ResolvedPolicy` (membership, is_admin, seven caps, `tier_overridden`) + `PolicyService.resolve/list_policies/patch_policy`. No quota fields.
- `budget.py`: `RunBudget.from_policy`, `max_hitl_rounds`/`run_deadline_seconds`/`membership` fields, `summary()` gains `membership` (flows into every `done` event — the existing run record).
- `service.py`: `run`/`resume_confirm` take `UserRead`; turn-start quota check (§3.5); HITL freeze/restore of caps.
- `admin_router.py`: `GET /api/admin/membership-policies` (+ inherited effective defaults), `PATCH …/{membership}` (omitted = unchanged, explicit null = inherit).

### 4.3 Domain modules (Part C)

- **downloads:** repository gains `chapters_this_month(user_id, start, end)` and `stored_bytes(user_id)`; `DownloadsService.create` enforces both kinds. Migration adds `download_jobs.size_bytes` (BigInteger, nullable); `app/jobs/tasks.py::_process` records combined + per-chapter part sizes on completion.
- **scraping:** repository gains `chapters_this_month(user_id, start, end)` (SUM `chapters_done`); `create_job` enforces before creating the book/job.
- **imports:** new `models.py` with `EpubImportRecord` (id, user_id FK, book_id nullable, chapter_count, status, created_at/updated_at) + migration; the in-memory runner writes the row at start and stamps terminal status (completed/failed/cancelled) — durable audit log + meter. `ImportService.start` enforces `COUNT(completed this month)`.

### 4.4 Observability

- Policy resolve logs `tier policy resolved` (`extra={run_id, membership, tier_overridden, …caps}`) — policy values are **not secrets, log freely**. `done` events carry `membership`.
- Every quota rejection logs `quota exceeded` with `extra={user_id, membership, kind, used, limit, resets_at}`.

### 4.5 Frontend

- **Backoffice → "Memberships" screen** (`/admin/policies`): Part A ships per-turn cap editing (blank = inherit, placeholder shows the inherited effective value). Part B adds a registry-driven "Quotas" section per tier card (blank = unlimited); Part C's kinds appear automatically once registered.
- **Backoffice → AI Usage screen:** by-user rows gain current-month usage vs LLM quota (Part B), then the job dimensions used/limit (Part C).
- **Chat:** SSE `error` handler becomes code-aware; `quota_exceeded` renders "You've reached your monthly AI limit. Upgrade your plan or try again after <rollover>." (Part B). No upgrade flow, no usage meter — Stripe plan's job.
- **Job creation surfaces** (downloads, scraper, import): a 429 `ApiError` already carries the server's user-facing detail; Part C verifies each surface displays it.

## 5. Contracts consumed across modules (allowed directions)

- orchestration → `users.schemas.UserRead`, `llm.service.LlmService.usage_summary`, `quotas.service.QuotaService`.
- downloads / scraping / imports → `quotas.service.QuotaService` (never the orchestrator).
- quotas → `users.service.UserService` (membership/is_admin lookup for `limits_for_user_id`). quotas imports **no** domain module — callers bring their own meter values.
- admin aggregation router → `users.service`, `llm.service`, `orchestration.policy`, `quotas.service`.

## 6. Error contract

SSE (chat):

```
event: error
data: {"code": "quota_exceeded", "kind": "llm_tokens",
       "detail": "Monthly AI token quota reached…",
       "resets_at": "2026-08-01T00:00:00+00:00"}
```

HTTP (job creation): **429** `{"detail": "<user-facing copy from the registry>"}`. Existing budget errors keep `{code: "budget_exceeded", detail}` on SSE. Tool-path failures (LLM tool hits a quota) surface as a failed tool result (`ok: false`, the same detail) — never a crashed turn.

## 7. Out of scope

- Stripe integration, upgrade flow, user-facing usage meter.
- Billing-period anchors other than UTC calendar months (§3.6).
- Cached usage counters (§3.5 upgrade path).
- Per-tier model selection / rate limits.
- Non-chat LLM work (summarization jobs) under tier budgets — only the orchestrated chat turn is tier-governed for now.
- Backfilling `size_bytes` for pre-existing download jobs (they expire on TTL anyway; meter treats NULL as 0).

## 8. Test strategy (proof obligations)

1. Every `Membership` value has a seeded `membership_policies` row; seeding is idempotent and never overwrites edits.
2. Per-turn resolution chain, all permutations: tier set / NULL × runtime_config override present / absent (incl. one full `RuntimeConfigService.effective_settings()` round-trip).
3. All existing budget/orchestration/HITL tests pass with all-NULL rows — no behavior change.
4. A tier row tightening one cap is enforced on the next turn without restart.
5. HITL: caps frozen at turn start survive a mid-pause tier change; legacy snapshots still resume.
6. Quotas module: limits resolution (row present/absent, admin exempt), month window incl. December rollover, standing kinds get no `resets_at`, `>=` threshold.
7. LLM quotas: under cap runs; at/over blocks with the structured SSE error **before any provider call**; admin exempt; raising the limit unblocks immediately.
8. Per Part C kind: under/over/admin-exempt/unlimited through the real domain service; the LLM tool path surfaces the quota error as a failed tool result; `size_bytes` recorded on job completion; `epub_imports` rows written by the runner with correct terminal status.
