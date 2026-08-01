# Backoffice MVP (Admin Area) — Design

Date: 2026-07-30
Status: Approved direction fixed by owner; produced in autonomous session.

## Goal

An admin-only backoffice for RTM v3: user management, AI usage/cost
visibility, tool-call audit, job monitoring, runtime settings, and LLM
catalog management. Backend routes live under `/api/admin/*` behind
`require_admin`; frontend routes live under `/admin/*` behind a new
`RequireAdmin` guard, with the nav entry gated on `useIsAdmin`.

## Owner decisions (fixed)

1. **`modules/admin` is a THIN AGGREGATION module** — routers + schemas
   only. No `repository.py`, no `models.py`, no tables, no service of its
   own. Every data need is served by the OWNING module's public service.
   Where a read doesn't exist yet, an admin-scoped method is added to THAT
   module's service — never a query in the admin module, never an import of
   another module's repository/models.
2. **The two existing admin APIs stay where they are.**
   `runtime_config/router.py` (`/api/admin/settings…`) and
   `llm/admin_router.py` (`/api/admin/llm/catalog…`) are NOT migrated into
   `modules/admin`.
3. **Admin reads are explicitly cross-user.** Existing repositories are
   ownership-scoped by default (`user_id` filter, `deleted_at` filter);
   those methods are never loosened. New, clearly-named admin methods
   (`list_users_admin`, `usage_by_user_admin`, …) are added instead.
   Soft-deleted users are VISIBLE in the backoffice (marked), not filtered.
4. **Pagination convention (new admin list endpoints):** `limit`/`offset`
   query params + envelope `{items, total, limit, offset}`. Mirrored as one
   TS type + hook. Existing runtime_config/catalog response shapes are
   mirrored as TS types EXACTLY — never reshaped.
5. **MVP is stat tiles + tables — no chart library.** Charts are a noted
   follow-up decision.
6. **Membership changes are an operator override.** Membership will later
   be Stripe-managed; the UI labels manual changes as an override.
7. **No job actions in the jobs monitor** (cancel/retry stay in their
   owning features). Read-only.

## Research findings that shape the plan (verified against the code)

1. **The frontend admin foundation does not exist yet.** There is no
   `RequireAdmin` guard, no `useIsAdmin` hook, and no `/admin` route in
   `frontend/src/app/App.tsx` (checked 2026-07-30). `useMe` and
   `User.is_admin` exist. The foundation (guard, hook, layout route, nav
   gating) is therefore an explicit early task, not a given.
2. **EPUB import jobs are in-memory** (`imports/jobs.py` module-level
   `_jobs` dict — no DB table, per-process). A cross-user DB read is
   impossible. The jobs monitor covers **scraping + downloads** only;
   import-job durability is a noted follow-up.
3. **`tool_calls` has no `user_id` column.** Attribution goes
   `tool_calls.message_id → conversation_messages → conversations.user_id`
   — all three are llm-module tables, so the join lives in `LlmRepository`
   (no boundary violation). Rows with `message_id IS NULL` have
   `user_id = null` in the response.
4. **`llm_executions.user_id` is merged** (NOT NULL, composite index
   `ix_llm_executions_user_id_created_at`), and
   `LlmService.usage_summary(...)` / `LlmRepository.usage_summary_for_user`
   exist. Screen 3's hard dependency is satisfied; admin aggregates extend
   this pattern cross-user.
5. **`Membership` currently has a single value (`free`).** The membership
   select is built generically over the enum; with one value it is
   effectively read-only until tiers ship.
6. **`ApiError` (frontend `shared/lib/api.ts`) discards the response
   `detail`** for JSON requests. Surfacing typed 422/409 errors inline
   requires parsing `detail` into `ApiError.message` (small shared change,
   done in the foundation task).
7. **`BookService.list_read` → `list_by_ids` is not ownership-scoped**, so
   `ScrapingService._book_titles` can be reused as-is for cross-user admin
   job rows (book titles resolve for any owner).
8. `get_db` commits on success (`core/db.py`), so admin service methods
   only `flush()` via repositories — same as existing writes.

## Architecture

```
backend/app/modules/admin/
  __init__.py
  router.py        # aggregator: APIRouter(prefix="/admin"), includes sub-routers
  users_router.py  # /admin/users…
  usage_router.py  # /admin/usage…
  audit_router.py  # /admin/tool-calls…
  jobs_router.py   # /admin/jobs…
  schemas.py       # Page[T] envelope + composed DTOs (e.g. AdminUserUsageRead)
  params.py        # PageParams / PeriodParams query-dependency classes
```

- No repository, no models, no service. Sub-routers keep files small and
  each concern's imports local; `params.py`/`schemas.py` are HTTP-layer DTO
  files (consistent with the "no data layer of its own" rule).
- Composition that needs TWO services (per-user usage rows + usernames) is
  done in the admin router as a thin zip — no business logic.
- Registered once in `main.py`:
  `app.include_router(admin_router, prefix=settings.app.api_prefix)`.
- Owning modules gain admin-scoped **service** methods backed by
  admin-scoped **repository** methods on their own tables only.

## Full inventory: screen → endpoint → owning-module service method

Legend: **existing** (nothing to do) / **new** (build in this plan) /
**existing-no-backend-work** (screen consumes a finished API).

### Screen 1 — Users

| Need | Endpoint | Owning service method | Status |
|---|---|---|---|
| Paginated list, soft-deleted included | `GET /api/admin/users?limit&offset` | `UserService.list_users_admin` (+ `UserRepository.list_all`) | new |
| Toggle `is_admin` / change membership | `PATCH /api/admin/users/{id}` | `UserService.update_user_admin` (+ `UserRepository.get_by_id_any`, `count_active_admins`) | new |
| Soft-delete | `DELETE /api/admin/users/{id}` | `UserService.soft_delete_user_admin` | new |
| Restore | `POST /api/admin/users/{id}/restore` | `UserService.restore_user_admin` | new |

Safety rails (each has a test): an admin cannot remove their own
`is_admin`; cannot soft-delete themselves; the last remaining active admin
cannot be demoted or deleted. New typed exceptions
`AdminSelfActionError` / `LastAdminError` (users module) → HTTP 409.
Membership is an operator override (Stripe later) — UI labels it as such.

### Screen 2 — Settings (frontend-only)

| Need | Endpoint | Owning service method | Status |
|---|---|---|---|
| List keys: effective value, env value, override status | `GET /api/admin/settings` | `RuntimeConfigService.list_effective` | existing-no-backend-work |
| Set override | `PUT /api/admin/settings/{key}` | `RuntimeConfigService.set_override` | existing-no-backend-work |
| Clear override (env value applies) | `DELETE /api/admin/settings/{key}` | `RuntimeConfigService.clear_override` | existing-no-backend-work |

Typed API errors surfaced inline: 404 unknown key, 422 invalid value, 404
clear-nothing. Whitelist already guarantees no secrets reach this API.
Built SECOND to drive out the admin table/form primitives against a
finished API.

### Screen 3 — AI usage & cost

| Need | Endpoint | Owning service method | Status |
|---|---|---|---|
| Global totals + by-model + by-task for `[from, to)` | `GET /api/admin/usage/summary?from&to` | `LlmService.usage_overview_admin` (+ repo `usage_totals_admin`, `usage_by_model_admin`, `usage_by_task_admin`) | new |
| Per-user aggregates (paginated) | `GET /api/admin/usage/by-user?from&to&limit&offset` | `LlmService.usage_by_user_admin` + `UserService.usernames_for_ids` (username zip in admin router) | new |
| Recent executions (paginated) | `GET /api/admin/usage/executions?from&to&limit&offset` | `LlmService.list_executions_admin` | new |

Aggregates read `llm_executions` (it carries provider/model/task/cost per
row; `cost_records` adds only unit prices, not needed here). The existing
per-user `usage_summary` / `UsageTotals` shape is the template; it stays
untouched. Stat tiles + tables only — charts are a follow-up.

### Screen 4 — LLM catalog (frontend-only)

| Need | Endpoint | Owning service method | Status |
|---|---|---|---|
| Providers + models with pricing | `GET /api/admin/llm/catalog` | `ModelCatalogAdminService.list_catalog` | existing-no-backend-work |
| Enable/disable provider | `PATCH /api/admin/llm/catalog/providers/{provider}` | `ModelCatalogAdminService.set_provider_enabled` | existing-no-backend-work |
| Toggle/patch model (enabled, pricing) | `PATCH /api/admin/llm/catalog/models/{provider}/{model}` | `ModelCatalogAdminService.patch_model` | existing-no-backend-work |
| Add model | `POST /api/admin/llm/catalog/models` | `ModelCatalogAdminService.create_model` | existing-no-backend-work |

Typed errors surfaced inline: 404 unknown provider/model, 409 duplicate,
422 no adapter / bad capability.

### Screen 5 — Tool-call audit viewer

| Need | Endpoint | Owning service method | Status |
|---|---|---|---|
| Paginated tool_calls with filters (tool_name, status, risk_level, date range), input/output JSON, duration, confirmation state, user attribution | `GET /api/admin/tool-calls?tool_name&status&risk_level&from&to&limit&offset` | `LlmService.list_tool_calls_admin` (+ repo join to conversations for `user_id`) | new |

### Screen 6 — Jobs monitor (read-only)

| Need | Endpoint | Owning service method | Status |
|---|---|---|---|
| Cross-user scraping jobs | `GET /api/admin/jobs/scraping?status&limit&offset` | `ScrapingService.list_jobs_admin` (+ repo; reuses `_book_titles`) | new |
| Cross-user download jobs | `GET /api/admin/jobs/downloads?status&limit&offset` | `DownloadService.list_jobs_admin` (+ repo) | new |
| EPUB import jobs | — | — | **excluded**: in-memory store, no DB rows; follow-up requires durable import-job rows first |

Admin job reads have no side effects: the downloads admin list does NOT
purge expired jobs (the user-facing list does); the scraping admin list
does not prune. Admin rows show the RAW `error` string (operator-facing),
unlike the user-facing `public_scrape_error` mapping.

## API conventions

- **Pagination:** `limit` (ge=1, le=200, default 50), `offset` (ge=0,
  default 0); response envelope `Page[T] = {items, total, limit, offset}`
  (generic pydantic model in `admin/schemas.py`).
- **Date ranges:** `from`/`to` query params (ISO 8601), interpreted as
  `[from, to)` — matches the existing `usage_summary_for_user` semantics.
  Required on `/admin/usage/*`; optional on `/admin/tool-calls`.
- **Authz:** every route takes `Depends(require_admin)`; anonymous → 401,
  non-admin → 403 (existing handlers). One parametrized authz-matrix test
  covers every admin route; each backend task appends its routes to it.
- **New exception mappings** (`core/exceptions.py`):
  `AdminSelfActionError` → 409 "Admins cannot demote or delete their own
  account"; `LastAdminError` → 409 "At least one active admin must remain".

## Frontend structure

```
frontend/src/features/admin/
  index.ts                     # barrel
  types.ts                     # Page<T> + shared admin types
  api/       settings.ts catalog.ts users.ts usage.ts toolCalls.ts jobs.ts
  hooks/     useAdminSettings.ts useCatalog.ts useAdminUsers.ts useUsage.ts
             useToolCalls.ts useAdminJobs.ts usePageState.ts
  logic/     settingValue.ts period.ts
  components/
    AdminLayout.tsx AdminNav.tsx AdminPlaceholder.tsx
    common/    PaginationControls.tsx StatTile.tsx DateRangeField.tsx JsonBlock.tsx
    settings/  SettingsPage.tsx SettingRow.tsx ValueEditor.tsx
    catalog/   CatalogPage.tsx ProviderSection.tsx ModelRow.tsx AddModelForm.tsx
    users/     UsersPage.tsx UsersTable.tsx UserRow.tsx
    usage/     UsagePage.tsx UsageSummaryTiles.tsx BreakdownTable.tsx
               ByUserTable.tsx ExecutionsTable.tsx
    toolcalls/ ToolCallsPage.tsx ToolCallFilters.tsx ToolCallRow.tsx
    jobs/      JobsPage.tsx ScrapingJobsTable.tsx DownloadJobsTable.tsx
```

- `RequireAdmin` + `useIsAdmin` live in `features/auth` (they are auth
  concerns); everything else in `features/admin`.
- Routes (inside the existing `ProtectedRoute` → `AppShell` nesting):
  `/admin` (AdminLayout with sidebar) → index redirect to `/admin/users`,
  children `users | settings | usage | catalog | tool-calls | jobs`.
  Unbuilt screens render `AdminPlaceholder` until their task lands.
- Nav: `ShellNavLinks` gains an Admin link rendered only when `useIsAdmin`.
- All server state via react-query (no zustand mirrors); all fetching via
  the typed client in `src/shared/lib/api.ts`.
- ESLint caps (file ≤110 lines, fn ≤60, depth ≤3) are honored by
  composing each screen from small subcomponents; shared primitives
  (`PaginationControls`, `DateRangeField`, `StatTile`, `JsonBlock`,
  `usePageState`) live in `components/common/` + `hooks/` and are driven
  out by screens 2/4 before the data-heavy screens consume them.
- TS types mirror backend pydantic responses exactly (snake_case fields).

## Build order (plan documents)

The implementation is split into seven self-contained plans (see
`docs/superpowers/plans/2026-07-30-backoffice-00-overview.md` for the
dependency table): `01-foundation` (backend admin scaffold + authz test
harness + frontend guard/layout/nav/API-client + pagination primitives),
then `02-users`, `03-settings`, `04-catalog`, `05-usage`, `06-tool-calls`,
`07-jobs`. Only the foundation is a hard prerequisite; the recommended
order runs users first and the frontend-only screens (settings, catalog)
before the data-heavy ones. Every task is independently green and
committed.

## Testing

- **Backend:** authz matrix (anonymous 401 / non-admin 403) parametrized
  once over every new admin route in `tests/admin/test_authz_matrix.py`,
  extended per task; admin-200 behavior in per-screen test files; safety
  rails (self-demote, self-delete, last-admin — incl. the service-level
  `LastAdminError` path); aggregate correctness against seeded rows with
  known token/cost sums and `[from, to)` boundary checks; tool-call
  attribution (joined user_id + NULL message_id row); cross-user job
  visibility + status filter. Shared client/user fixtures in
  `tests/admin/` follow the `test_catalog_admin_api.py` pattern.
- **Frontend (vitest):** `RequireAdmin` guard behavior, nav gating,
  `usePageState` pagination hook, `settingValue` parse/format logic, and
  one representative screen per kind — settings (form screen) and usage
  (data screen) — with mocked query data.
- Gates per task: backend `ruff check --fix && ruff format`, `mypy .`,
  `pytest -m "unit or integration"`; frontend `npm run lint`,
  `npm run build`, `npm run test`.

## Constraints

- Strict mypy + ruff (complexity ≤10, statements ≤20, branches ≤6,
  args ≤6). Aggregate endpoints split query-building into helpers;
  query-param groups use dependency classes (`PageParams`, `PeriodParams`)
  to keep router functions under the args cap.
- pydantic schemas for every admin response — no raw dict/ORM passthrough.
- Never log or return secrets. The settings screen only ever sees
  whitelisted tunables (runtime_config registry guarantee). Admin usage
  endpoints return aggregates and metadata — never prompt/content text.
- Commits via `bash scripts/git-commit-clean.sh /tmp/msg.txt`; no
  attribution trailers.

## Out of scope / follow-ups

- Charts (chart-library decision deferred; MVP is tiles + tables).
- Job actions (cancel/retry/delete) in the jobs monitor.
- EPUB import jobs in the monitor (needs durable DB-backed import jobs).
- Stripe-managed membership (manual changes stay labeled as override).
- CSV export, live auto-refresh (react-query defaults only).
- `app_settings_audit` history viewer (data exists; screen later).
- Catalog-screen vitest coverage (settings covers the form-screen kind).

## Accepted risks

- Per-user usage rows resolve usernames via a second service call zipped in
  the admin router — two queries per page, acceptable at backoffice scale.
- The last-admin rail counts only ACTIVE (non-deleted) admins; restoring a
  demoted-then-deleted admin cannot create a zero-admin state because
  demote/delete of the last active admin is blocked.
- Tool-call rows with `message_id = NULL` (or pruned messages) show
  `user: —`; acceptable for MVP audit.
- Admin list endpoints cap `limit` at 200; no cursor pagination (tables are
  small at MVP scale; offset drift under concurrent writes is tolerable).
