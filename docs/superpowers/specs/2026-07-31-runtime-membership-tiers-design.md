# Runtime Membership Tiers — Design

Date: 2026-07-31
Status: approved

## 1. Goal

Admins create, edit, and deactivate membership tiers at runtime — no code
change, no migration per tier. The `Membership` Python enum is deleted; the
tier registry becomes a DB table served through a cached snapshot. End users
get a tier picker on Plan & usage (flag-gated, no Stripe) for manual testing.

Everything downstream already keys on the tier slug string
(`membership_policies`, `membership_quotas`, `users.membership`); this design
adds the registry those strings point at, and referential integrity so a
stranded slug is impossible.

## 2. Data model

### 2.1 New table `memberships` (owned by the users module)

| column        | type                    | notes                                                        |
| ------------- | ----------------------- | ------------------------------------------------------------ |
| `id`          | UUID PK                 | repo convention; NOT the join key                            |
| `slug`        | String(32), unique      | join key everywhere; **immutable after creation**; pattern `^[a-z0-9_-]{1,32}$` |
| `label`       | String(64)              | display name ("Premium"); freely editable                    |
| `description` | Text, nullable          | presentation only (plan picker blurb)                        |
| `price_label` | String(32), nullable    | presentation only ("$9/mo"); no Stripe semantics             |
| `rank`        | Integer                 | ordering for pickers and `meets_minimum`; ties broken by slug |
| `is_active`   | Boolean, default true   | assignable / shown in pickers                                |
| `is_default`  | Boolean, default false  | where new signups land; partial unique index (`WHERE is_default`) enforces exactly one |
| `created_at` / `updated_at` | timestamptz | repo convention                                    |

### 2.2 Referential integrity (Option B — slug FKs)

One migration:

1. Create `memberships`.
2. Backfill: insert `free` (rank 0, label "Free", active, default), then any
   other distinct slug found in `users.membership`,
   `membership_policies.membership`, or `membership_quotas.membership`
   (rank 0, label = slug, active, not default) so the FKs are valid.
3. Add `FOREIGN KEY ... REFERENCES memberships(slug) ON DELETE RESTRICT` to
   `users.membership`, `membership_policies.membership`, and
   `membership_quotas.membership`.

Reversible: drop the three FKs, drop the table. `users.membership` keeps
`server_default='free'`. `user_quota_overrides` is untouched (keys on
`user_id`, not tier).

Because tiers are deactivated, never hard-deleted, the RESTRICT never fires
in practice — it is a backstop that makes "unknown slug" a DB impossibility
rather than a runtime warning. No default-tier fallback logic is needed.

### 2.3 Snapshot cache `users/membership_registry.py`

Direct sibling of `modules/llm/catalog.py`: frozen `TierSpec` dataclass
(slug, label, description, price_label, rank, is_active, is_default),
`current_snapshot()` / `put_snapshot()` / `invalidate()` /
`ensure_loaded(session)`, 30s TTL. Every write to `memberships` calls
`invalidate()`: the writing process sees the change immediately; other
processes (arq worker, other API workers) converge within the TTL.

## 3. Enum removal

`Membership` (StrEnum) and `MEMBERSHIP_RANK` are deleted. The replacement is
asymmetric by design:

- **Reads** — `UserRead.membership`, `UserAdminRead.membership`,
  `MeUsageResponse.membership`, `UserQuotasResponse.membership` become plain
  `str`. Values come from our own DB (FK-guaranteed); a profile must never
  fail serialization over tier state.
- **Writes** — `UserAdminPatch.membership`, the `{membership}` path params in
  the membership-policies and membership-quotas admin routers (become `str`),
  and the self-switch body validate in the **service** against the registry
  snapshot and raise typed `UnknownMembershipError` → 404 (mapped centrally).
  Assignment paths (admin user patch, self-switch) additionally require
  `is_active`; policy/quota admin endpoints accept inactive tiers (an admin
  may still edit a deactivated tier's rows).
- **`meets_minimum(actual, minimum)`** keeps its fail-closed contract, reading
  rank from the snapshot instead of `MEMBERSHIP_RANK`. `require_membership`
  gains a session dependency and awaits `ensure_loaded` first (currently used
  by zero routes; contained change).

## 4. Tier lifecycle

- **Create** — active immediately; also inserts the all-NULL
  `membership_policies` row (per-turn caps inherit runtime settings) in the
  same transaction. No `membership_quotas` rows: absent = unlimited, which the
  admin UI labels explicitly. Admin configures quotas in the same sitting.
- **Edit** — label, description, price_label, rank, `is_default` freely
  editable. Slug immutable. Setting `is_default` on tier B clears it on the
  previous default (single UPDATE pair, one transaction).
- **Deactivate** — requires an explicit migration target chosen by the admin.
  One transaction: reassign every user on the tier to the target, set
  `is_active = false`. Guards: target exists, is active, is not the tier
  itself; the default tier cannot be deactivated (crown another default
  first). The tier's policy/quota rows are kept (reactivation restores its
  full configuration).
- **Reactivate** — `PATCH` with `is_active: true`.
- **No hard delete.**

Startup seeding changes: `seed_membership_policies` iterates the
`memberships` table instead of the enum. A users-module seed ensures the
`free` row exists (insert-if-missing; never overwrites admin edits) — same
contract as the LLM catalog seed.

## 5. API surface

### 5.1 Admin — new `memberships` router (all `require_admin`)

| endpoint | behavior |
| --- | --- |
| `GET /api/admin/memberships` | every tier (active and inactive), each with a live user count |
| `POST /api/admin/memberships` | create; body: slug, label, rank, optional description/price_label |
| `PATCH /api/admin/memberships/{slug}` | edit label/description/price_label/rank/is_default/`is_active: true` |
| `POST /api/admin/memberships/{slug}/deactivate` | body `{migrate_to: <slug>}`; reassign-then-deactivate transaction |

Errors: duplicate slug → 409; unknown slug → 404; guard violations
(deactivate default, bad migrate target) → 422 typed domain errors. All
writes log with `actor` (established admin-write pattern) and call
`invalidate()`.

### 5.2 Self-serve (any authenticated user)

- `GET /api/me/plans` — active tiers ordered by rank: slug, label,
  description, price_label, plus `current: bool` per tier and a top-level
  `can_switch` (the runtime flag) so the frontend needs no separate config
  call.
- `POST /api/me/membership` — body `{membership: <slug>}`. 403 when the flag
  is off; 404 unknown or inactive slug; no-op success if already on that
  tier. Logged with the user as actor. Downgrading while over the new tier's
  limits is allowed — enforcement bites on the next action.

### 5.3 Runtime flag

New `MembershipSettings` group in `app/core/config.py`:
`self_switch_enabled: bool = True` (env `membership_self_switch_enabled`),
registered as a full section in the runtime-config registry. When Stripe
lands, flip it off at runtime: the buttons disappear and the endpoint 403s —
no redeploy.

### 5.4 Existing endpoints

`/api/admin/membership-policies` and `/api/admin/membership-quotas` keep
their paths and shapes; only the path-param type changes (enum → str,
service-validated). The admin users PATCH keeps its shape; membership values
are validated against active tiers.

## 6. Frontend

### 6.1 Admin — Policies page

Already one card per tier. Add:

- "New tier" button → create dialog (slug, label, rank, description, price
  label).
- Per-card header actions: edit dialog (label/description/price/rank/default
  — not slug) and a deactivate action whose dialog forces choosing the
  migration target and shows the affected user count.
- Inactive tiers render collapsed/dimmed with a reactivate button.
- Cards ordered by rank. Unlimited quotas labeled explicitly.

Admin users page: the membership dropdown switches to the memberships
endpoint and lists only active tiers.

### 6.2 Plan & usage page

Below the meters, a "Plans" section: one card per active tier (label,
price_label, description), ordered by rank; current tier highlighted; others
get a "Switch to X" button with a window.confirm. Section hidden entirely
when `can_switch` is false. On switch success, invalidate the me-usage and
plans queries so meters re-render against the new tier immediately.

New feature api/hooks follow the existing pattern
(`features/usage/api/meUsage.ts` et al.); ESLint size limits (≤110 lines per
file) will force small components — expected split: `PlansSection`,
`PlanCard`, `usePlans`/`useSwitchPlan`.

## 7. Testing

- **Unit**: registry snapshot TTL/invalidate (mirror catalog tests);
  `meets_minimum` from snapshot (fail-closed on unknown/cold);
  service guards (duplicate slug, deactivate default, bad migrate target,
  inactive assignment rejected); `test_membership.py` rewritten against the
  registry.
- **Integration**: memberships admin CRUD + deactivate-migrates-users
  round-trip; policy auto-row on create; seed idempotency (free row, policy
  rows from table); self-switch flag on/off; `/me/plans` shape; existing
  policy/quota/admin-user tests updated for enum removal (factories gain a
  tier helper that inserts a registry row).
- **Frontend**: PoliciesPage create/edit/deactivate dialogs; UsagePage plans
  section render/hide on `can_switch`; switch invalidates queries.

## 8. Out of scope

- Stripe/billing integration (`price_label` is text; no payment flow).
- Hard-deleting tiers.
- Per-tier feature gating beyond the existing `require_membership` hook.
- Slug renames.
- Redis pub/sub cache invalidation (30s TTL suffices; `invalidate()` is the
  single seam if it ever doesn't).
