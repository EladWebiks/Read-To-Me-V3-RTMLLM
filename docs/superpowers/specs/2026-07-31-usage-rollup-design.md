# Usage Rollup — Design Spec

**Status:** Approved (maintainer, 2026-07-31)
**Plan:** Part D — `docs/superpowers/plans/2026-07-31-usage-rollup-part-d.md` (to be written after spec review)
**Relates to:** [Tier-Based Usage Management](./2026-07-31-tier-usage-management.md) (Parts A–C). Part D sequences **after Part C** (it rolls up tables Part C creates). The user-facing usage surface / admin-gap work discussed separately becomes **Part E** and reads from this rollup.

## 1. Problem

Usage reads aggregate raw tables on the fly. The per-user current-month quota check is index-bounded (fine forever), but:

1. **Admin aggregates** (`/api/admin/usage/summary`, `/by-user`, by-model/by-task) scan the selected period across **all** users — cost grows with total history and user count, unbounded.
2. **`llm_executions` grows forever** (a row per provider round, several per turn); nothing prunes it, and every wide-period read pays for that.
3. **Meter sprawl:** after Part C, six quota kinds are metered from four tables with per-table semantics (soft-delete included here, excluded there, completed-only there). Every new surface (Part E) would re-derive them on the fly; the by-user admin endpoint already issues 4+ queries per page.
4. **Some wanted numbers are not recorded at all:** quota rejections (denied turns / 429s — the upsell signal) leave no row anywhere; job failure rates are derivable but only by more raw scans.

## 2. Decisions (locked, maintainer-approved)

1. **Scope:** the rollup answers all of — the six quota kinds; LLM model/task breakdowns; **quota rejections** (which therefore must start being recorded); job outcomes/failure counts.
2. **Freshness — hybrid:** closed (UTC) days are read from rollup rows; **today is always read live** from raw tables. Enforcement switches to hybrid reads. Every read becomes bounded (≤31 rollup rows + one single-day raw scan) with zero staleness for the current day.
3. **Retention:** raw tables remain the source of truth **forever**; the rollup is a derived, rebuildable cache. Pruning/archiving raw history is a documented future option, not built now.
4. **Stripe posture (undecided future):** design so an append-only `usage_events` ledger can be added at the charge points later without changing rollup reads. Charge points are untouched by this design; `quota_rejections` establishes the event-table pattern.

## 3. Current state (verified 2026-07-31)

- `llm_executions` (`user_id` NOT NULL, composite `(user_id, created_at)` index) with `usage_summary` / `usage_totals_admin` / `usage_by_user_admin` / by-model / by-task aggregate queries in `llm/repository.py`.
- Part C meters (planned): `download_jobs.total_count` (soft-deleted rows included — flow meter), `scraping_jobs.chapters_done`, `epub_imports` completed rows, `stored_bytes` (level meter over live rows).
- Quota rejections: **unrecorded** — `QuotaExceededError` is raised, logged, and lost. The error carries `kind/limit/used/resets_at` but not `user_id`.
- arq worker exists (`app/jobs/worker.py`) with the purge job as the background-work pattern; arq supports `cron_jobs` in `WorkerSettings`.
- Admin usage endpoints accept arbitrary `[from, to)` ranges — the rollup grain must serve arbitrary ranges, hence **daily**, not monthly.

## 4. The `usage` module (new)

```
modules/usage/
  kinds.py         # UsageMetric StrEnum + METRIC_REGISTRY + QuotaKind -> metric(s) map
  models.py        # UsageDaily, LlmModelDaily, LlmTaskDaily, QuotaRejection
  repository.py    # this module's tables only
  read_service.py  # rolled reads + hybrid composition helpers (imports NO domain modules)
  rollup.py        # nightly builder + backfill (composes domain services; worker-side)
  exceptions.py    # (only if needed)
```

**Import discipline (cycle-free by construction):** domain services (`downloads`, `scraping`, `imports`, `llm`) and orchestration may import `usage.read_service`. Only `usage/rollup.py` imports domain services (to collect facts), and nothing it imports reaches back into it. `usage` never imports `orchestration`.

### 4.1 Metric registry (code, not DB)

`UsageMetric(StrEnum)` + `METRIC_REGISTRY` (label, unit). Adding a metric = enum value + registry entry + a fact source — **no migration** (same keyed philosophy as `membership_quotas`). Initial metrics:

| Metric | Fact source (rolled by the builder) |
|---|---|
| `llm_tokens_in`, `llm_tokens_out`, `llm_cost_usd`, `llm_executions` | `llm_executions` per user/day |
| `llm_failures` | `llm_executions` rows with `status != "ok"` |
| `audio_chapters`, `audio_jobs` | `download_jobs` by `created_at` day, **soft-deleted included** (flow-meter semantics, Part C) |
| `audio_jobs_failed` | `download_jobs.status == "failed"` |
| `scrape_chapters`, `scrape_jobs` | `scraping_jobs` by `created_at` day (`SUM(chapters_done)` / count) |
| `scrape_jobs_failed` | `scraping_jobs.status == "failed"` |
| `epub_imports` | `epub_imports.status == "completed"` by `created_at` day |
| `epub_imports_failed` | `epub_imports.status == "failed"` |
| `rejected_<quota_kind>` (one per enforced kind) | `quota_rejections` per user/day |

**QuotaKind → metric map** (read-time): `LLM_TOKENS` → `llm_tokens_in + llm_tokens_out`; `LLM_COST_USD` → `llm_cost_usd`; `AUDIO_CHAPTERS` → `audio_chapters`; `SCRAPE_CHAPTERS` → `scrape_chapters`; `EPUB_IMPORTS` → `epub_imports`. **`STORAGE_BYTES` is deliberately not rolled** — it is a level meter; the live `stored_bytes` query remains its only source.

### 4.2 Tables

- `usage_daily(id, user_id FK, day DATE (UTC), metric String(48), amount Float, created_at, updated_at)` — unique `(user_id, day, metric)`, index `(user_id, day)`, index `(day)`. **Sparse:** zero-amount rows are omitted. Float64 is exact for integer counts ≤ 2^53 (same argument as `membership_quotas.limit_value`).
- `llm_model_daily(id, day, provider, model, tokens_in, tokens_out, cost, executions)` — unique `(day, provider, model)`. Wide is fine: LLM telemetry fields are stable.
- `llm_task_daily(id, day, task, tokens_in, tokens_out, cost, executions)` — unique `(day, task)`.
- `quota_rejections(id, user_id FK, quota_kind String(32), source String(16): "chat" | "api", created_at)` — index `(user_id, created_at)`, index `(created_at)`. Raw event rows; rolled into `rejected_*` metrics nightly like everything else.

## 5. Rejection recording (the one new write path)

- `QuotaExceededError` gains `user_id: UUID | None` (it already receives it for logging).
- Recording happens where the rejection becomes user-visible — **not** inside `QuotaService.enforce` (keeps it pure/static, keeps unit tests DB-free, and avoids recording inside a transaction the raised exception is about to roll back):
  1. **Orchestration's catch** (chat path): the session is alive and the error is handled, not propagated — insert `quota_rejections(source="chat")` and commit alongside the SSE error event.
  2. **The central 429 handler** (`core/exceptions.py`, REST job paths): the request transaction rolls back on the exception, so the handler writes via its own short `SessionLocal` transaction (`source="api"`), best-effort (failure to record logs a warning, never breaks the 429 response).

## 6. Rollup builder

- **arq cron**, daily at 00:10 UTC, in the existing worker.
- **Idempotent per day:** delete that day's `usage_daily` / `llm_*_daily` rows, re-insert from facts. Re-running any day is always safe (raw is truth).
- **Trailing window, not just yesterday:** re-rolls the last `usage_rollup_window_days` (default **7**, runtime-tunable via the registry) every night. Facts land late by design — a scrape job's `chapters_done` grows while it runs; an EPUB completes the day after creation; re-rolling converges them. A job still non-terminal past the window freezes at its last rolled value — **documented, accepted** (bounded by that job's own range).
- **Fact collection** goes through each owning module's *service* (`llm`, `downloads`, `scraping`, `imports` each expose a `daily_usage_facts(day) -> list[(user_id, metric, amount)]`-shaped method plus the model/task breakdown for llm) — each module owns the SQL over its own tables; the builder only composes and upserts.
- **Backfill:** a one-shot command (`uv run python -m app.modules.usage.rollup` style entry) rolls all history up to yesterday at deploy time; also the recovery path if rollup data is ever suspect (delete + backfill).
- No watermark table: the nightly window plus explicit backfill covers catch-up after worker downtime ≤ window; longer downtime → run backfill (documented in the plan's runbook step).

## 7. Read paths (hybrid)

Rule: **closed days from rollup, today from raw, summed at read time.**

- `read_service.rolled_amount(user_id, metrics, start_day, end_day) -> float` and range variants for admin (per-user page, totals, model/task breakdowns).
- **Month amount for quota checks** = `rolled_amount(month days before today)` + a **today-tail supplied by the caller** from its own repository (a day-bounded variant of each existing meter). The caller supplying the tail is what keeps `downloads → usage` one-directional (no cycle) and preserves the caller-metered pattern of Parts B–C. Enforcement points change from "scan my table for the month" to "rolled + my today-tail".
- **Admin endpoints:** summary tiles and by-user/by-model/by-task compose rolled rows for closed days + one-day raw aggregates for today. The recent-executions **list** stays raw (row listing, not an aggregate).
- Every read is bounded regardless of history size: ≤31 `usage_daily` rows per metric + one single-day raw scan.

## 8. Accepted behaviors / edges (documented, not bugs)

- Today's numbers are exact (live); closed-day numbers converge within the trailing window; a >window-length-running job's late chapters are not counted after its window passes.
- Rollup and raw can briefly disagree for in-window days between cron runs; the property test (§10) pins the converged state, not mid-window states.
- Quota semantics are unchanged by this design: `>=` blocks, admins exempt, UTC months, one-unit overage.
- Soft-deleted download jobs keep counting in flow metrics (rolled by `created_at`, `deleted_at` ignored) — identical to Part C's meter semantics.

## 9. Out of scope

- Pruning/archiving raw tables (future: a cron deleting raw rows older than N closed months once the rollup is trusted — noted, not built).
- `usage_events` charge-time ledger (add if Stripe metered billing materializes; charge points untouched today).
- Any UI (Part E consumes this; no screens change in Part D except where enforcement reads switch invisibly).
- Real-time counters / Redis caches.

## 10. Test strategy (proof obligations)

1. Builder idempotency: rolling the same day twice yields identical rows.
2. Late-arriving convergence: a job completing after its creation day's first roll is corrected by the next roll within the window.
3. Backfill equivalence: for seeded history, rolled totals == on-the-fly raw aggregates (per metric, per user, per model/task).
4. Hybrid month math: rolled days + today-tail equals a full raw month scan, including across a UTC day boundary.
5. Rejections: recorded from the chat path (same-session commit) and the REST path (survives the request rollback); rolled into `rejected_*` metrics.
6. Enforcement behavior unchanged: the Part B/C quota tests still pass with hybrid reads swapped in (blocked/unblocked outcomes identical).
7. Sparse-row rule: zero-amount metrics produce no rows.
