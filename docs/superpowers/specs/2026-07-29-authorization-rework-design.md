# Authorization Rework (`role` → `is_admin` + `membership`) — Design

Date: 2026-07-29
Status: Approved (decisions fixed by owner)

## Goal

Replace the dead `users.role` column with two orthogonal concepts and the
enforcement primitives the app has never had:

- `is_admin: bool` — pure authority flag for future backoffice access.
- `membership: str` — a string-backed tier enum (starting with only `free`)
  that will drive tier-gated features and per-tier AI budgets.

Today `role` defaults to `"admin"`, is never checked anywhere (there is no
role-checking dependency in `app/core/deps.py`), and conflates authority with
product tier. This rework removes it and adds `require_admin` /
`require_membership(minimum)` dependencies layered on `get_current_user`.

## Decisions (owner-approved)

1. **String-backed enum for membership** — Python `StrEnum`
   (`Membership.FREE = "free"`), stored as `String(32)`. NOT an int column,
   NOT a native Postgres enum type: values are readable in DB and audit rows,
   new tiers don't require a type migration, and values map directly to
   future Stripe product lookup keys.
2. **Tier ordering lives in code**, not the DB: a rank map
   (`MEMBERSHIP_RANK = {"free": 0}`; later `{"free": 0, "premium": 1}`) so
   `require_membership(minimum)` compares ranks without magic DB integers.
   Comparison is fail-closed: an unknown stored tier ranks as 0; an unknown
   *required* tier never passes.
3. **Start with only `free`.** The enum is the extension point; no `premium`
   member ships now. Tests exercise multi-tier ordering by patching the rank
   map, not by adding speculative enum members.
4. **`is_admin` is separate from membership.** Admin is authority (backoffice),
   membership is product tier. The seeded admin is `is_admin=True,
   membership='free'` — the two never derive from each other.
5. **Land AFTER `feature/sso` merges.** See Sequencing.

## Data model & migration

`users` table changes (one reversible Alembic migration):

- Add `is_admin: bool` NOT NULL, server default `false`.
- Add `membership: varchar(32)` NOT NULL, server default `'free'`.
- Backfill `is_admin = (role = 'admin')`, then drop `role`.
- Downgrade: recreate `role` (`'admin'` where `is_admin` else `'user'`,
  NOT NULL, no server default — matching the original column), drop the two
  new columns.

The migration chains after the SSO branch's `db448309b4a6` (google_sub +
nullable password_hash). `uv run alembic heads` must show exactly one head
before and after.

No data migration concerns: the SSO branch has never been started against a
real server — no Google users or Google-provisioned rows exist anywhere. The
only real rows are bootstrap-seeded admins (`role='admin'` → `is_admin=True`).

## New module code

### `app/modules/users/membership.py` (new)

```python
class Membership(StrEnum):
    FREE = "free"

MEMBERSHIP_RANK: dict[str, int] = {Membership.FREE: 0}

def meets_minimum(actual: str, minimum: str) -> bool:
    """Rank comparison; fail-closed on unknown values."""
```

- `meets_minimum` returns `False` when `minimum` is not in the rank map
  (unknown requirement → deny); an unknown `actual` ranks 0 (lowest).

### Model / schemas (`users` module)

- `User.role` removed. `User.is_admin: Mapped[bool]` (default `False`,
  server default `false`), `User.membership: Mapped[str]` (default
  `Membership.FREE`, server default `"free"`).
- `UserCreate`: loses `role`, gains `is_admin: bool = False`. Membership is
  not creatable via `UserCreate` — new users are always `free` (model
  default); tier changes are a future billing concern.
- `UserRead`: loses `role`, gains `is_admin: bool` and
  `membership: Membership` (pydantic coerces the stored string).

## Enforcement primitives (`app/core/deps.py`)

Layered on the existing `get_current_user` (which already yields `UserRead`
from the server-side session cookie — authenticated identity never comes from
the client):

- `require_admin` — dependency; raises typed `NotAuthorizedError` when
  `not current_user.is_admin`, returns the user otherwise.
- `require_membership(minimum: Membership)` — dependency **factory**; the
  produced dependency raises `NotAuthorizedError` when
  `not meets_minimum(current_user.membership, minimum)`. No consumers yet —
  this is the hook for tier-gated features and per-tier AI budgets.

`NotAuthorizedError` is a new typed exception in
`app/modules/auth/exceptions.py` (subclass of `AuthError`, next to
`NotAuthenticatedError`), mapped centrally in `app/core/exceptions.py`
(`_register_auth_handlers`) to **403** `{"detail": "Not authorized"}` —
distinct from the 401 of `NotAuthenticatedError`.

Module boundaries hold: `core/deps` already imports from `auth` and `users`;
`users` gains no import from `auth`; ownership checks elsewhere are untouched.

## SSO-branch adjustments (code-level, not data)

The `feature/sso` branch is being implemented now, but the server has never
run with it — this is an adjustment of that branch's *code output*, applied
after it merges:

- `UserService.create_from_google`: `role="user"` → provisioned users get
  `is_admin=False` and `membership=Membership.FREE` via model defaults (no
  explicit kwargs needed once `role` is gone).
- `AuthService._resolve_google_user` **first-login admin-claim rule is
  kept unchanged**: if no user has a `google_sub` yet, the first Google login
  claims the seeded admin (matched by `settings.admin_username`) and inherits
  its authority — now `is_admin=True` carried by the seeded row instead of a
  role string. A regression test seeds via `seed_admin_user` and verifies the
  rule when the admin row was created by bootstrap but first login happens
  after this migration runs.
- `seed_admin_user` (`app/core/bootstrap.py`): `role="admin"` →
  `is_admin=True`.
- All tests passing `role=` to `UserCreate` or asserting on `role` are
  updated (full grep sweep; ~16 backend test files, see plan Task 2). LLM
  *message* `role` fields (`Message.role`, `message.role` in orchestration/
  llm modules and assistant frontend) are unrelated and untouched.

### SSO artifacts this supersedes

- `backend/tests/test_users_google.py` — `assert user.role == "user"`
  becomes `is_admin is False` / `membership == Membership.FREE`; the two
  `UserCreate(..., role=...)` call sites drop the kwarg.
- `backend/tests/test_google_login_service.py` (SSO plan Task 5) — four
  `UserCreate(..., role=...)` call sites drop the kwarg; the admin-claim test
  gains `is_admin` assertions.
- SSO **plan** `docs/superpowers/plans/2026-07-29-google-sso.md` Task 4
  (`create_from_google` with `role="user"`) and its embedded test snippets —
  superseded by this design; the SSO doc itself is not edited (history stays
  honest, this section is the pointer).
- SSO **design** matching rule 4 ("role `user`") — provisioned users now get
  `is_admin=False, membership='free'`.
- `frontend/src/features/auth/types.ts` — `User.role` replaced (below).

## Frontend

`User` in `frontend/src/features/auth/types.ts`: drop `role: string`, add
`is_admin: boolean` and `membership: string` (mirrors `UserRead`; typed as
string union later if the UI ever branches on tier). Nothing in the frontend
renders or reads `role` today (verified by grep), so this is a type-only
change; `npm run build` proves no dangling usage.

## Sequencing — land after `feature/sso` merges (decided)

Rationale:

1. **Single migration chain.** The SSO branch owns `db448309b4a6`; this work
   adds the next revision. Running both branches in parallel invites a
   two-headed Alembic history.
2. **Same files, opposite churn.** Both effort touch `users`
   models/schemas/service, `bootstrap.py`, auth service tests. Rebasing this
   rework over an in-flight SSO branch would repeatedly re-resolve the same
   conflicts.
3. **This rework edits SSO outputs.** `create_from_google`,
   `_resolve_google_user`, and their tests only exist in final form once SSO
   lands; adjusting them mid-flight means chasing a moving target.

## Testing

- **Unit:** `Membership` values; `MEMBERSHIP_RANK`; `meets_minimum` ordering
  incl. a patched `{"free": 0, "premium": 1}` map (free fails premium,
  premium passes free/premium), fail-closed cases (unknown actual, unknown
  minimum); `require_admin` / `require_membership` called directly with
  constructed `UserRead`s (raise vs return).
- **Integration (Postgres):** authorization matrix over a test-local FastAPI
  app mounting the real deps + real exception handlers: anonymous → 401,
  authenticated non-admin → 403, admin → 200; `require_membership(FREE)` for
  a free user → 200; insufficient tier → 403 (via patched comparator, since
  only `free` exists); migration round-trip; `create_from_google` flags;
  bootstrap-seeded admin flags; first-login admin-claim confers
  `is_admin=True`.
- Gates: `ruff check` + `format --check`, strict `mypy`,
  `pytest -m "unit or integration"`, `npm run lint`, `npm run build`,
  `npm run test`.

## Out of scope

- Any consumer of `require_admin` / `require_membership` (no backoffice
  routes, no tier-gated features, no per-tier AI budgets yet).
- Membership changes at runtime (upgrade/downgrade flows, Stripe).
- Adding a second tier.
- Admin management UI or promoting/demoting users.

## Accepted risks

- `require_membership` ships without a consumer; it is exercised only by
  tests until the first tier-gated feature arrives. Accepted: it is the
  agreed extension point and the tests pin its contract.
- The higher-tier integration path is tested with a patched rank map rather
  than a real second tier; a true end-to-end premium test arrives with the
  first real tier.
