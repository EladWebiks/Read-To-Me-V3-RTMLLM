# Backoffice MVP — Plan Overview

**Spec:** `docs/superpowers/specs/2026-07-30-backoffice-mvp-design.md`

The backoffice is planned as seven small plans instead of one large one.
Each plan is self-contained (full code, TDD steps, gates, commits) and ends
with working software.

## Plan documents

| # | Plan | Scope | Depends on |
|---|---|---|---|
| 1 | `2026-07-30-backoffice-01-foundation.md` | Backend `modules/admin` scaffold (`Page`, `PageParams`/`PeriodParams`, aggregator router, test harness + authz matrix skeleton); frontend `RequireAdmin`/`useIsAdmin`, admin layout/nav/routes, API-client fixes (`apiPatch`, error `detail`), pagination primitives | — |
| 2 | `2026-07-30-backoffice-02-users.md` | Users admin service methods + safety rails, `/api/admin/users` routes, users screen | 1 |
| 3 | `2026-07-30-backoffice-03-settings.md` | Settings screen (frontend-only, existing API) | 1 |
| 4 | `2026-07-30-backoffice-04-catalog.md` | LLM catalog screen (frontend-only, existing API) | 1 |
| 5 | `2026-07-30-backoffice-05-usage.md` | Usage/cost aggregates API (+ `usernames_for_ids` on users service) + usage screen | 1 |
| 6 | `2026-07-30-backoffice-06-tool-calls.md` | Tool-call audit API + screen | 1 |
| 7 | `2026-07-30-backoffice-07-jobs.md` | Jobs monitor API (scraping + downloads) + screen | 1 |

## Recommended execution order

1 → 2 → 3 → 4 → 5 → 6 → 7.

Rationale: the frontend-only screens (3, 4) drive the admin table/form
patterns against finished APIs before the data-heavy screens (5–7) consume
them; users (2) ships the highest-value management screen first. Plans 3–7
are mutually independent — only plan 1 is a hard prerequisite (plans 5–7
also append routes to the authz matrix file plan 1 creates).

## Shared conventions (pinned in every plan)

- Every new admin route registers itself in
  `backend/tests/admin/test_authz_matrix.py::ROUTES` (401 anon / 403
  non-admin, parametrized once).
- Pagination: `limit`/`offset` + `Page[T]` envelope. Date ranges:
  `from`/`to` meaning `[from, to)`.
- `modules/admin` stays a thin aggregation module — routers + DTOs only;
  every query lives in the owning module's service/repository.
- Each screen plan swaps its own `AdminPlaceholder` route in `App.tsx`.
  After all six screens land, `AdminPlaceholder` may be deleted as cleanup
  (optional, not part of any plan).
