# LLM usage attribution (`llm_executions.user_id`) — Design

Date: 2026-07-30
Status: Approved

## Goal

Attribute every LLM provider call to the user it ran for, by adding a
`user_id UUID NOT NULL` FK to `llm_executions`. This is groundwork for
membership tiers: per-user monthly usage/cost aggregation, tier quotas
enforced in orchestration budget checks, and later Stripe usage-based
billing. Billing-grade metering needs direct, indexed, NOT NULL attribution —
today the only link is a NULLABLE `conversation_id`.

## Decisions (user-approved)

1. **Fresh start, NOT NULL from day one.** Existing `llm_executions` data is
   disposable dev-only telemetry. The migration wipes `cost_records` then
   `llm_executions` instead of backfilling, so there are no partial
   attribution states and no `server_default` is needed.
2. **Plain FK, no cascade.** Users are soft-deleted (`deleted_at`); usage
   records must survive for billing/audit even if a user row is later
   removed. No `ON DELETE` behavior on the FK.
3. **`cost_records` does NOT get `user_id`.** It joins 1:1 to
   `llm_executions` via `llm_execution_id` (NOT NULL FK — verified: it is the
   only table in the codebase referencing `llm_executions`). `llm_executions`
   stays the single attribution point; duplicating `user_id` would create a
   second source of truth that can drift.
4. **`user_id` is a REQUIRED parameter** through the whole telemetry write
   API (`ExecutionWrite`, `TelemetryContext`, every `LlmService` entry point
   that records telemetry). A new call site cannot compile (strict mypy) or
   run without supplying it — silent unattributed usage becomes impossible.

## Schema & migration

One reversible Alembic migration, chained off `db448309b4a6` (the
`feature/sso` `google_sub` migration — currently the single head on this
branch; verify `uv run alembic heads` shows exactly one head before and
after):

Upgrade:
1. `DELETE FROM cost_records` (FK child first), then
   `DELETE FROM llm_executions`. **Verified wipe order:** grep of all models
   and migrations shows `cost_records.llm_execution_id` is the only FK into
   `llm_executions`; `cost_records.llm_execution_id` is NOT NULL, so a full
   `DELETE` of both tables is correct.
2. `ADD COLUMN user_id UUID NOT NULL` — legal without a default because the
   table is empty at that point.
3. Named FK `fk_llm_executions_user_id_users` → `users.id`, no cascade.
4. Composite index `ix_llm_executions_user_id_created_at (user_id, created_at)`.

Downgrade: drop index → drop FK → drop column. The migration docstring
states explicitly that the wiped `cost_records`/`llm_executions` rows are
unrecoverable in both directions.

### Index shape justification

The target query is *"sum tokens/cost per user for a billing month"*:

```sql
SELECT sum(tokens_in), sum(tokens_out), sum(cost), count(*)
FROM llm_executions
WHERE user_id = :user AND created_at >= :month_start AND created_at < :month_end;
```

- Composite btree `(user_id, created_at)` — equality column first, range
  column second — lets Postgres do one contiguous index range scan of
  exactly the user's rows in the period.
- A plain `user_id` index would scan the user's **entire** history and
  filter `created_at` against the heap — cost grows with lifetime usage,
  which is exactly what a billing table accumulates.
- `(created_at, user_id)` is wrong for the same reason mirrored: the range
  column first forces scanning all users' rows in the period.
- The composite's leftmost prefix also serves plain `user_id` lookups, so no
  separate single-column `user_id` index is added. The existing
  `conversation_id`/`task`/`provider`/`status`/`trace_id` indexes are
  untouched.

## Write path — full audit of `llm_executions` writers

There is exactly **one** insert site: `LlmRepository.record_execution`
(`backend/app/modules/llm/repository.py`), called only by
`LlmTelemetry._write` (via `record_call` and `write_result`), and
`LlmTelemetry` is instantiated only by `LlmService.__init__`. So threading
`user_id` through `LlmService`'s recording entry points covers every path.

Recording entry points on `LlmService` and their callers (each becomes an
explicit plan task item; strict mypy will confirm the list is exhaustive):

| Entry point | Records telemetry | Production callers | `user_id` source |
|---|---|---|---|
| `stream_tools` | yes (`write_result` in `finally`) | `orchestration/service.py` `_StreamedRound.events` (chat tool loop) | `ToolContext.user_id` (from server session via `get_current_user`) |
| `generate_structured` | yes (via `generate_structured_with_model`) | `llm/conversation_context.py` `_summarize` (rolling conversation summary) | `build(user_id, …)` parameter — threaded into `_summarize` |
| `generate_structured_with_model` | yes | `summaries/service.py` `SummaryService.ensure` (book summaries; invoked by the `summarize_book` tool with `ctx.user_id`) | `ensure(user_id, …)` parameter |
| `generate_text` | yes | none today | required param anyway — future callers must supply |
| `call_tools` | yes | none today | required param anyway |
| `create_embeddings` | yes (currently `conversation_id=None`) | none today | required param anyway |
| `stream_text` | **no telemetry today** (pre-existing gap) | none today | out of scope; noted so it isn't mistaken for a covered path |

Scraping and discovery modules contain **no** LLM usage (verified by grep) —
the deterministic-first rule holds and there is no LLM fallback call site
there today.

**Open-question check (per the brief):** every live write path has an
authenticated `user_id` in scope. No path required inventing a sentinel
user, so there is no open question to flag.

### API shape changes

- `ExecutionWrite`: new required field `user_id: uuid.UUID` (declared before
  the defaulted `conversation_id`).
- `TelemetryContext`: new required field `user_id: uuid.UUID` (before the
  defaulted `conversation_id`).
- `LlmService.generate_text / call_tools / stream_tools /
  generate_structured / generate_structured_with_model / create_embeddings`:
  new keyword-only required `user_id: UUID` parameter.
- `LlmService._record` is refactored to accept a prebuilt `TelemetryContext`
  instead of loose arguments — adding a 7th loose argument would breach the
  ruff `max-args 6` gate; callers construct the context inline.
- `orchestration/service.py` `_StreamedRound.events` takes the `ToolContext`
  instead of a bare `conversation_id` and passes both ids to `stream_tools`.
- `ConversationContextService._summarize` gains a `user_id` parameter,
  supplied by `build(user_id, …)`.
- `SummaryService.ensure` passes its existing `user_id` through to
  `generate_structured_with_model`.

### Test impact (deliberate updates)

- `backend/tests/llm/test_llm_telemetry.py` — the only structural break:
  `TelemetryContext` gains a required field, and the NOT NULL FK means the
  test must create a real `users` row and assert `user_id` round-trips.
- `tests/llm/test_chat.py`, `test_orchestration.py`, `test_hitl.py` and the
  shared `tests/llm/stream_fakes.py` — unaffected: their `stream_tools`
  fakes accept `**kwargs`, so the extra `user_id` kwarg passes through.
- `tests/llm/test_conversation_context.py`, `test_book_summaries.py` —
  unaffected: `AsyncMock` fakes accept arbitrary kwargs.
- API-level fixtures (`test_auth_api.py`, `test_library_api.py`,
  `test_reader_api.py`, `test_google_auth_api.py`) already delete
  `cost_records` → `llm_executions` → … → `users` in FK-safe order —
  unaffected.

## Read path (proves the index and attribution)

One repository + service method, no HTTP route yet (the backoffice plan
consumes it later):

- `LlmRepository.usage_summary_for_user(user_id, *, period_start,
  period_end) -> UsageTotals` — a single aggregate `SELECT` over the
  half-open interval `[period_start, period_end)`, exactly the billing-month
  query the composite index serves. `UsageTotals` is a frozen dataclass:
  `tokens_in, tokens_out, total_cost, execution_count`.
- `LlmService.usage_summary(user_id, *, period_start, period_end) ->
  UserUsageSummary` — pydantic DTO echoing the user/period plus the totals.
  Other modules go through this service method, never the repository
  (module-boundary rule).
- Integration test: two users, in-range and out-of-range rows, asserts
  ownership filtering, date-range filtering, sums, count, and the
  zeros-on-empty-range path (`COALESCE`).

## Constraints

- Only the llm module touches `llm_executions` (its repository); other
  modules use the llm module's public service.
- Migration is reversible and exercised `upgrade → downgrade → upgrade`,
  and applied to the test DB (`TEST_DATABASE_URL`) — never point tests at
  the app DB.
- Strict mypy + ruff + pytest gates per CLAUDE.md pass per task; commits via
  `bash scripts/git-commit-clean.sh` with no attribution trailers.

## Sequencing

Independent of the config restructure and the is_admin/membership rework
(different modules) — safe in parallel with either. Only coordination point:
Alembic head ordering. This migration chains off `db448309b4a6`; if another
migration lands first, regenerate the revision so `alembic heads` stays at
exactly one head.
