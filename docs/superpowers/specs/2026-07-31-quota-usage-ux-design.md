# Quota & Usage UX — Design Spec (Parts E–F)

**Status:** Approved (maintainer, 2026-07-31)
**Plans:**
- [Part E — end-user usage UX](../plans/2026-07-31-usage-ux-part-e.md) (`/api/me/usage`, Plan & usage page, chat refusal marker + informed composer)
- [Part F — admin usage UX](../plans/2026-07-31-admin-usage-ux-part-f.md) (rejection visibility, hybrid month columns, per-user overrides, registry-driven tier dropdown)

**Relates to:** [Tier-Based Usage Management](./2026-07-31-tier-usage-management.md) (Parts A–C) and [Usage Rollup](./2026-07-31-usage-rollup-design.md) (Part D). This spec is the "Part E" both documents point at, split E/F because the combined task list exceeds ~10.

## 1. Problem

Quotas (Parts A–D) are enforcement-only: users discover limits by hitting a wall.

1. **No self-service visibility.** Nothing shows a user their tier, per-kind usage, or limits. The only usage surfaces are admin-gated.
2. **The chat refusal is ephemeral and leaves a lie in history.** The `quota_exceeded` SSE error renders a local banner outside the message list; the user's message is persisted server-side *before* the turn (spec §3.5), so a reload shows an unanswered orphan bubble with no explanation. The composer never disables, and every futile retry persists another orphan.
3. **Admin gaps:** Part D records `quota_rejections` and `rejected_*` metrics but no screen shows them; the B6/C5 by-user month/quota columns stay raw scans after D6 converts the period aggregates to hybrid; there is no per-user quota lever short of granting full admin exemption; the frontend hardcodes `MEMBERSHIPS = ['free']`, violating the registry-driven rule the moment a second tier exists.

## 2. Current state (verified 2026-07-31)

**Parts A–D are approved plans, NOT implemented.** Verified: no `modules/quotas/`, no `modules/usage/`, no policy/quota/usage migrations, no quota checks on any job-creation path, no unmerged branches holding any of it — the six A–D documents are docs-only commits. Every prerequisite in this spec is therefore **by plan**: the E/F plans consume interfaces as named in the A–D plans and must re-verify them against merged code before starting (each plan's Task 1 begins with that check).

Frontend facts driving the design:

- `shared/lib/api.ts::ApiError` is `{status, message}`; the 429 `detail` string flows into `message` (sufficient — REST 429 bodies are plain strings by locked contract).
- `features/assistant`: SSE errors land in ephemeral `useState` rendered at the bottom of `AssistantMessageList` (`role="alert"` div); composer disable is exactly `sending || blocked` (`blocked` = pending HITL confirm); the `cancelled` role is the existing client-side inline-note pattern; hydration (`GET /api/chat/{id}`) renders whatever roles the server persisted.
- `conversation_messages.role` is a free `String(32)` and the message schema serves `role: str` — a new persisted role needs **no migration**.
- Settings is a client-only slide-over sheet (no settings page, no server-backed section); the navbar avatar (`layout/UserAvatar.tsx`) already has `membership` via `useMe()`; `@radix-ui/react-dropdown-menu` is installed but unwrapped.
- Admin usage screen (`features/admin/components/usage/`) is stat tiles + tables (no charts, no drill-down); adding an admin screen is a 3-edit pattern (route + barrel + `AdminNav.LINKS`). No toast library; progress bars are a hand-rolled inline pattern (`EpubImportProgress.tsx`).
- `features/admin/api/users.ts` hardcodes `MEMBERSHIPS = ['free'] as const`.

## 3. Decisions (locked)

### 3.1 Split and sequencing

- **Part E (end-user, 6 tasks)** sequences **after Part D Tasks 1–2 and 5** (usage module, rejection recording, hybrid enforcement pattern) — transitively after all of B and C. It consumes: `QuotaService.limits_for`, `QuotaKind`/`KIND_REGISTRY`, `UsageReadService.rolled_month_amount`/`hybrid_split`, the B4 SSE error plumbing, and the C-plan domain meter methods.
- **Part F (admin, 7 tasks)** sequences **after Part D Task 6** plus B6/C5 (the admin by-user columns it converts/extends). F's overrides tasks depend only on Part B; its screen tasks depend on B7/C5's table state.
- Parts E and F are independent of each other except that F's overrides are automatically reflected by E's `/api/me/usage` (both read limits through `QuotaService.limits_for`). Either may land first.

### 3.2 `GET /api/me/usage` — home, shape, composition

- **Home:** `modules/usage/router.py` (self-serve router, session identity only — no user-id parameter, golden rule 3), logic in a new composition-layer file `modules/usage/self_service.py`.
- **Import-discipline amendment to Part D §4:** `rollup.py` **and `self_service.py`** are the usage module's composition files allowed to import domain services; `read_service.py` stays pure (importable by domains, cycle-free); `usage` still never imports orchestration.
- **Shape** (registry-driven — every `QuotaKind` always present, ordered by registry):

```json
{
  "membership": "free",
  "exempt": false,
  "as_of": "2026-07-31T12:00:00+00:00",
  "resets_at": "2026-08-01T00:00:00+00:00",
  "kinds": [
    {"kind": "llm_tokens", "label": "AI tokens", "unit": "tokens",
     "window": "month", "used": 1234.0, "limit": 5000.0},
    {"kind": "storage_bytes", "label": "Download storage", "unit": "bytes",
     "window": "standing", "used": 52428800.0, "limit": null}
  ]
}
```

- **`used` composition:** month kinds = `rolled_month_amount(user_id, kind, now)` + a today-tail from the owning domain's meter with a `[today 00:00 UTC, month end)` window — the exact D-Task-5 hybrid pattern. `storage_bytes` = live `stored_bytes` only (level meter, never rolled). Where Part C left a meter repository-private, Part E adds a one-line service passthrough (services compose services, never foreign repositories): `DownloadService.chapters_in_period` / `.stored_bytes`, `ScrapingService.chapters_in_period`, `ImportService.completed_in_period`; LLM uses the existing `LlmService.usage_summary`.
- **`limit`** from `QuotaService.limits_for(user)` — `null` = unlimited; Part F's per-user overrides surface here with zero E changes. **Admins:** `exempt: true`, all limits `null`, `used` still computed (admins see their own consumption).
- `resets_at` = current UTC month end (applies to month kinds; standing kinds ignore it). Per-kind dispatch table keeps the composer under ruff's branch limits.

### 3.3 Chat refusal: persisted marker + informed composer

- **Persisted marker:** in orchestration's quota catch — the same block that emits the SSE error (B3) and records the rejection (D2) — persist a `ConversationMessage(role="quota_refusal", content=str(exc))` in the same commit as the rejection row. No migration. The SSE error contract is **unchanged** (locked shape).
- **Context exclusion:** the conversation-context builder must exclude `quota_refusal` rows (an assistant-role marker would be replayed into future prompts as model speech — the reason a distinct role was chosen). The exclusion is explicit and tested.
- **Client rendering:** on a `quota_exceeded` SSE error the client appends a local `quota_refusal` message (mirroring the persisted one — the `cancelled` pattern) instead of the generic banner; after reload, hydration serves the server's copy. `ChatTurn` renders `quota_refusal` as a muted amber inline note; **unknown roles fall back to the same note style** so future roles degrade gracefully. Other error codes keep the existing banner.
- **Composer lock:** `disabled = sending || blocked || quotaBlocked`; placeholder "Monthly AI limit reached — resets <date>". `quotaBlocked` has two sources: (a) session flag set by the `quota_exceeded` SSE error (carries `resets_at`); (b) derived **during render** from the `['me', 'usage']` query when the assistant is open — `used >= limit` on `llm_tokens` or `llm_cost_usd` (never a setter in an effect, per frontend rules). The lock therefore survives reload and releases when a raised quota shows up on the next query refresh (no push mechanism — accepted).

### 3.4 Plan & usage page

- New feature `frontend/src/features/usage/{api,components,hooks,logic}/` with an `index.ts` barrel; route `/usage` inside the protected shell (not admin-gated); query key `['me', 'usage']`, `staleTime` 30s.
- **Entry point:** `UserAvatar` becomes a dropdown (new `shared/ui/dropdown-menu.tsx` wrapper over the installed Radix dep, in the `tooltip.tsx` style): email, tier label, "Plan & usage" link. Logout stays where it is.
- **Page:** header = tier name + "Usage resets <date>". One meter row per **month** kind: label, `used / limit` formatted per unit (tokens with thousands separators, USD `$x.xx`, counts plain), inline progress bar (the existing hand-rolled pattern — no component library), **amber ≥80%, red at 100%**; `limit: null` renders muted "Unlimited" with no bar. A separate **Storage** section renders the standing meter with byte formatting (MB/GB) and the copy "Frees up when downloads expire or are deleted" instead of a reset date. `exempt: true` shows a "No limits apply (admin)" note above the meters.
- Threshold styling **is** the approaching-limit warning (maintainer decision): no header badge, no composer banner.
- Formatting/threshold logic lives in `logic/format.ts` with vitest coverage; components split to respect the 110-line ESLint cap.

### 3.5 Part F — admin

- **Rejection visibility:** `GET /api/admin/usage/summary` gains `rejections: int` + `rejections_by_kind: dict[str, int]`; by-user rows gain `period_rejections: int`. All computed for the **selected period** via hybrid reads (rolled `rejected_*` metrics + today's raw `quota_rejections` count). UI: a "Quota rejections" stat tile, a per-kind breakdown in the existing `BreakdownTable` pattern, and a "Rejections" column on the by-user table.
- **Hybrid month columns:** B6/C5's `_decorate_rows` current-month scans (`usage_for_users` + the three job set-variants) switch to `rolled_user_table` over the month's closed days + the existing set-variant meters with a today window — the same transformation D5 applies to enforcement. Response shape unchanged.
- **Per-user overrides:** new sparse table `user_quota_overrides(id UUID PK, user_id FK NOT NULL, quota_kind String(32), limit_value Float > 0, created_at, updated_at, unique (user_id, quota_kind))`, owned by the **quotas** module (its table; users FK is a reference, not a repository reach). Resolution in `QuotaService.limits_for`: **admin exempt → user override row → tier row → unlimited** (specificity-wins, consistent with §3.3 of the A–C spec; looser and tighter both allowed). Row absent = tier applies; deleting the row restores tier behavior. Every enforcement point and `/api/me/usage` inherit overrides with zero changes.
- **Overrides admin API:** `GET /api/admin/users/{user_id}/quotas` (kind registry + tier limits for placeholder rendering + override rows), `PUT /api/admin/users/{user_id}/quotas/{kind}` (`{limit_value: > 0}`), `DELETE …/{kind}` (404 if absent) — the membership-quotas set/clear pattern, behind `require_admin`.
- **Overrides UI:** a per-row "Quotas" dialog on the admin Users screen — registry-driven inputs, blank = tier default with the effective tier limit shown as placeholder (the blank=inherit pattern from the policies screen).
- **Tier dropdown:** the users screen's membership `<select>` options come from Part A's `GET /api/admin/membership-policies` response instead of the hardcoded `MEMBERSHIPS` const (which is deleted).

### 3.6 Cut from scope (recorded decisions)

- **Job-surface 429 audit:** C5 already owns making downloads/scraper/import surfaces render `ApiError.message` (including fixing the two surfaces that currently swallow it). Reader per-paragraph TTS is not quota-enforced at all (only download-job creation is), so there is no reader 429 to render. No E/F work.
- **Policy/quota edit audit trail:** deferred — structured logs already record actor + change; revisit when Stripe makes edits financially sensitive.
- **Header ≥80% badge / composer warning banner:** deferred — meter threshold colors carry the warning.
- No Stripe/upgrade flow, no payment UI; refusal copy may say "upgrade" as words only (locked upstream). No new aggregation mechanisms or cached counters.

## 4. Contracts consumed across modules (allowed directions)

- `usage/self_service.py` → `quotas.service.QuotaService`, `users` identity via router dep, `llm.service`, `downloads.service`, `scraping.service`, `imports.service`, `usage.read_service`. (Composition file — §3.2 amendment. `usage` never imports orchestration.)
- orchestration (quota catch) → the llm-module repository path it already uses to persist conversation messages, plus `usage.read_service.record_rejection` (Part D).
- quotas → `users.service` (existing direction); `user_quota_overrides` is a quotas-owned table.
- admin usage router → `usage.read_service` passthroughs (D6) + the F additions; frontend admin users screen → membership-policies endpoint (Part A).

## 5. Error contract

Unchanged from the A–C spec §6 (locked): SSE `{"code": "quota_exceeded", "kind", "detail", "resets_at"}`; REST 429 `{"detail": "<user copy>"}`. Part E adds no new error shapes; the persisted `quota_refusal` message carries the same `detail` string as content.

## 6. Out of scope

- Stripe, payments, upgrade flows (copy-only mentions allowed).
- Push/instant composer unlock on quota raise (query refresh is the mechanism).
- Per-kind usage history charts / time series for end users (rollup supports it later; not now).
- Email/notification warnings at thresholds.
- Admin per-user drill-down screen (the by-user table row remains the unit; overrides live in a dialog).

## 7. Test strategy (proof obligations)

1. `/api/me/usage`: registry coverage (every kind present exactly once), hybrid math (rolled + today tail == full raw month, incl. UTC day boundary), storage served live, `limit` reflects tier rows, admin gets `exempt` + null limits + real `used`, 401 anonymous.
2. Refusal marker: persisted in the same commit as the rejection row; content == SSE `detail`; hydration serves it; the context builder never includes `quota_refusal` rows (test builds context over a conversation containing one).
3. Composer: locks from the SSE error with reset copy; locks on assistant open when the usage query shows an LLM kind at/over limit; derived state computed in render (no effect-setter); unlocks when the query shows under-limit.
4. Page: format helpers (tokens/USD/bytes/thresholds) unit-tested; meter states under/near/at/unlimited; storage section; admin note; loading/error states.
5. Overrides: resolution permutations (override × tier row × admin) through `QuotaService.limits_for`; enforcement honors an override without restart; API upsert/clear/404/422 + authz; dialog blank-vs-value semantics.
6. Rejections: summary/by-user rejection counts = rolled `rejected_*` + today raw, pinned against seeded rejections spanning the hybrid boundary.
7. Hybrid month columns: decorated by-user values identical to the raw-scan implementation for seeded data (equivalence test, D §10.3 style).
8. Tier dropdown: options rendered from the served policies list; `MEMBERSHIPS` const removed.
