# Authorization Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the never-enforced `users.role` column with an `is_admin` authority flag plus a string-backed `membership` tier enum, and add the `require_admin` / `require_membership(minimum)` enforcement dependencies the app has never had.

**Architecture:** A new `users/membership.py` holds the `Membership` StrEnum and the in-code rank map (tier ordering never lives in the DB). One reversible Alembic migration swaps the columns and backfills `is_admin` from `role`. `app/core/deps.py` gains two dependencies layered on the existing `get_current_user`; a new typed `NotAuthorizedError` maps centrally to 403. The SSO branch's provisioning/bootstrap code is adjusted from `role=` strings to the new flags — a code-level change only, since no server has ever run the SSO branch (no Google users or provisioned rows exist anywhere).

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, pydantic v2, pytest (+Postgres for integration), React 19 + TS (type mirror only).

**Spec:** `docs/superpowers/specs/2026-07-29-authorization-rework-design.md` (approved).

## Global Constraints

- **Sequencing: do NOT start until `feature/sso` is merged.** This plan edits SSO outputs (`create_from_google`, `_resolve_google_user` tests, `backend/tests/test_google_login_service.py`, the post-SSO `frontend/src/features/auth/types.ts`) and chains a migration after the SSO branch's `db448309b4a6`. Reasons: single Alembic head, no repeated conflicts in `users`/`bootstrap`/auth tests, and no chasing a moving target. SSO artifacts superseded by this plan are listed in the spec ("SSO artifacts this supersedes").
- All backend gates must pass per task (run from `backend/`): `uv run ruff check . --fix && uv run ruff format .`, `uv run mypy .`, `uv run pytest -m "unit or integration"`.
- Frontend gates (run from `frontend/`): `npm run lint`, `npm run build`, `npm run test`.
- Integration tests need Postgres/Redis/MinIO and `TEST_DATABASE_URL` pointing at a separate test DB — never the app DB.
- Commit with `bash scripts/git-commit-clean.sh /tmp/msg.txt` (write the message to `/tmp/msg.txt` first). **Never** add `Co-authored-by`/`Made-with` trailers. Verify with `git log -1 --format=%B`.
- Ruff limits: complexity ≤10, statements ≤20, branches ≤6, args ≤6. Full type hints; strict mypy. No bare `except`.
- Module dependency direction: `auth` calls the `users` **service** only (never its repository); `users` must not import from `auth`. `core/deps` may import from both (it already does). Ownership checks elsewhere are untouched.
- Decisions fixed by the owner (do not relitigate): `membership` is a Python `StrEnum` stored as `String(32)` — NOT an int, NOT a native Postgres enum. Tier ordering lives in the code rank map. Only `free` exists now. `is_admin` and `membership` are independent.
- The LLM *message* `role` fields (`Message.role`, `app/modules/llm/**`, `app/modules/orchestration/**`, assistant frontend) are a different concept — never touch them.

---

### Task 1: `Membership` enum + rank map + `meets_minimum`

**Files:**
- Create: `backend/app/modules/users/membership.py`
- Test: `backend/tests/test_membership.py`

**Interfaces:**
- Consumes: nothing.
- Produces (used by Tasks 2, 4, 5):
  - `class Membership(StrEnum)` with `FREE = "free"` (the only member for now; this enum is the extension point for future tiers)
  - `MEMBERSHIP_RANK: dict[str, int]` = `{Membership.FREE: 0}` (keys are plain strings via StrEnum; ordering lives here, never in the DB)
  - `meets_minimum(actual: str, minimum: str) -> bool` — fail-closed: unknown `minimum` → `False`; unknown `actual` ranks 0.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_membership.py
"""Unit tests for membership tiers and rank ordering."""

import pytest

from app.modules.users import membership as membership_module
from app.modules.users.membership import MEMBERSHIP_RANK, Membership, meets_minimum


@pytest.mark.unit
def test_membership_is_string_backed() -> None:
    assert Membership.FREE == "free"
    assert isinstance(Membership.FREE, str)


@pytest.mark.unit
def test_rank_map_covers_every_tier() -> None:
    assert set(MEMBERSHIP_RANK) == {member.value for member in Membership}
    assert MEMBERSHIP_RANK[Membership.FREE] == 0


@pytest.mark.unit
def test_free_meets_free() -> None:
    assert meets_minimum(Membership.FREE, Membership.FREE) is True


@pytest.mark.unit
def test_ordering_with_future_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(membership_module, "MEMBERSHIP_RANK", {"free": 0, "premium": 1})
    assert meets_minimum("free", "premium") is False
    assert meets_minimum("premium", "free") is True
    assert meets_minimum("premium", "premium") is True


@pytest.mark.unit
def test_unknown_actual_ranks_lowest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(membership_module, "MEMBERSHIP_RANK", {"free": 0, "premium": 1})
    assert meets_minimum("garbage", "free") is True
    assert meets_minimum("garbage", "premium") is False


@pytest.mark.unit
def test_unknown_minimum_fails_closed() -> None:
    assert meets_minimum(Membership.FREE, "premium") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `uv run pytest tests/test_membership.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.modules.users.membership'`

- [ ] **Step 3: Implement `membership.py`**

```python
# backend/app/modules/users/membership.py
"""Membership tiers and their in-code rank ordering.

Values are stored as strings in `users.membership` and map directly to
future Stripe product lookup keys. Ordering lives ONLY in MEMBERSHIP_RANK —
never as integers in the DB.
"""

from __future__ import annotations

from enum import StrEnum


class Membership(StrEnum):
    """Product tier. Extend here when a new tier ships."""

    FREE = "free"


MEMBERSHIP_RANK: dict[str, int] = {Membership.FREE: 0}


def meets_minimum(actual: str, minimum: str) -> bool:
    """True when `actual` ranks at least `minimum`; fail-closed on unknowns."""
    required = MEMBERSHIP_RANK.get(minimum)
    if required is None:
        return False
    return MEMBERSHIP_RANK.get(actual, 0) >= required
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_membership.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m unit
printf 'feat: add membership tier enum with in-code rank ordering\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 2: Replace `users.role` with `is_admin` + `membership` (model, schemas, service, bootstrap, migration, test sweep)

This swap is atomic — the model, schemas, service, bootstrap, and every test
passing `role=` must change together or nothing is green. It is one task with
one commit.

**Files:**
- Modify: `backend/app/modules/users/models.py`
- Modify: `backend/app/modules/users/schemas.py`
- Modify: `backend/app/modules/users/service.py` (`create`, `create_from_google`)
- Modify: `backend/app/core/bootstrap.py`
- Create: `backend/migrations/versions/<generated>_replace_users_role_with_is_admin_and_membership.py`
- Test (new): `backend/tests/test_user_authz_fields.py`
- Modify (sweep — every `UserCreate(..., role=...)` call site and `role` assertion):
  - `backend/tests/test_users_google.py:37,43,54`
  - `backend/tests/test_google_login_service.py` (4 call sites — exists post-SSO merge)
  - `backend/tests/test_auth_api.py:62`
  - `backend/tests/test_reader_api.py:67`
  - `backend/tests/test_library_api.py:61`
  - `backend/tests/test_chapter_upsert.py:32`
  - `backend/tests/llm/test_conversation_context.py:46,100`
  - `backend/tests/llm/test_chat.py:41`
  - `backend/tests/llm/test_import_discovered_hitl.py:38`
  - `backend/tests/llm/test_hitl.py:44`
  - `backend/tests/llm/test_book_summaries.py:38`
  - `backend/tests/llm/test_search_library_content.py:38,69,72`
  - `backend/tests/llm/test_b32_action_tools.py:56`
  - `backend/tests/llm/test_b31_read_tools.py:55`
  - `backend/tests/llm/test_orchestration.py:43`

  (Line numbers are pre-merge references — re-grep in Step 6; the sweep rule
  is what matters, not the numbers.)

**Interfaces:**
- Consumes: `Membership` (Task 1).
- Produces (used by Tasks 3–5):
  - `User.is_admin: Mapped[bool]` (default `False`, server default `false`), `User.membership: Mapped[str]` (default `Membership.FREE`, server default `"free"`); `User.role` is gone.
  - `UserCreate(username, password, email=None, is_admin: bool = False)` — no `role`, no `membership` (new users are always `free`; tier changes are a future billing concern).
  - `UserRead` with `is_admin: bool` and `membership: Membership` (no `role`).
  - `seed_admin_user` seeds `is_admin=True`; `create_from_google` provisions `is_admin=False, membership='free'` via model defaults.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_user_authz_fields.py
"""Integration tests for users authority/membership fields (needs Postgres)."""

from collections.abc import AsyncIterator

import pytest
from app.core.bootstrap import seed_admin_user
from app.core.config import get_settings
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserCreate
from app.modules.users.service import UserService
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as sess:
        await sess.execute(text("DELETE FROM users"))
        await sess.commit()
        yield sess
        await sess.rollback()
    async with factory() as cleanup:
        await cleanup.execute(text("DELETE FROM users"))
        await cleanup.commit()
    await engine.dispose()


@pytest.mark.integration
async def test_create_defaults_to_non_admin_free(session: AsyncSession) -> None:
    user = await UserService(session).create(
        UserCreate(username="plain", password="password123")
    )
    assert user.is_admin is False
    assert user.membership == Membership.FREE


@pytest.mark.integration
async def test_create_with_admin_flag(session: AsyncSession) -> None:
    user = await UserService(session).create(
        UserCreate(username="boss", password="password123", is_admin=True)
    )
    assert user.is_admin is True
    assert user.membership == Membership.FREE


@pytest.mark.integration
async def test_seed_admin_user_sets_is_admin(session: AsyncSession) -> None:
    await seed_admin_user(session)
    entity = await UserService(session).get_entity_by_username(
        get_settings().admin_username
    )
    assert entity is not None
    assert entity.is_admin is True
    assert entity.membership == Membership.FREE


@pytest.mark.integration
async def test_google_provisioned_user_is_non_admin_free(session: AsyncSession) -> None:
    user = await UserService(session).create_from_google("sub-authz", "tier@example.com")
    assert user.is_admin is False
    assert user.membership == Membership.FREE
    assert user.password_hash is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_user_authz_fields.py -v`
Expected: FAIL — `UserCreate` rejects/ignores `is_admin` and `User` has no `is_admin` attribute.

- [ ] **Step 3: Update the model**

In `backend/app/modules/users/models.py`, extend the sqlalchemy import to
`from sqlalchemy import Boolean, DateTime, String, false, func`, add
`from app.modules.users.membership import Membership`, and replace the
`role` line with:

```python
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
    )
    membership: Mapped[str] = mapped_column(
        String(32),
        default=Membership.FREE,
        server_default=Membership.FREE.value,
    )
```

- [ ] **Step 4: Update schemas, service, bootstrap**

`backend/app/modules/users/schemas.py` — add
`from app.modules.users.membership import Membership`; replace both classes'
`role` fields:

```python
class UserCreate(BaseModel):
    """Input for creating a user."""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    email: EmailStr | None = None
    is_admin: bool = False


class UserRead(BaseModel):
    """Public user representation (never includes password)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str | None
    is_admin: bool
    membership: Membership
    created_at: datetime
```

`backend/app/modules/users/service.py` — in `create`, replace
`role=data.role,` with `is_admin=data.is_admin,`; in `create_from_google`,
delete the `role="user",` line entirely (model defaults make provisioned
users `is_admin=False, membership='free'`).

`backend/app/core/bootstrap.py` — in `seed_admin_user`, replace
`role="admin",` with `is_admin=True,`.

- [ ] **Step 5: Create the migration**

Run: `uv run alembic revision -m "replace users role with is_admin and membership"`
Verify the generated `down_revision` is `"db448309b4a6"` (the SSO migration)
and `uv run alembic heads` shows exactly one head. Fill in:

```python
def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column("membership", sa.String(length=32), nullable=False, server_default="free"),
    )
    op.execute(sa.text("UPDATE users SET is_admin = TRUE WHERE role = 'admin'"))
    op.drop_column("users", "role")


def downgrade() -> None:
    # Recreate role from is_admin; original column had NOT NULL and no
    # server default, so backfill through a temporary default then drop it.
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
    )
    op.execute(sa.text("UPDATE users SET role = 'admin' WHERE is_admin"))
    op.alter_column("users", "role", server_default=None)
    op.drop_column("users", "membership")
    op.drop_column("users", "is_admin")
```

- [ ] **Step 6: Sweep every `role=` usage in backend tests**

Re-grep rather than trusting the line numbers above:

```bash
grep -rn 'role=' tests --include='*.py' | grep -i 'usercreate\|role="admin"\|role="user"'
grep -rn '\.role' tests app --include='*.py' | grep -v llm | grep -v orchestration
```

Apply two mechanical rules:
1. In every `UserCreate(...)` call, delete the `role="admin"` / `role="user"`
   argument. No current test depends on role semantics — they date from the
   default-admin era. Do NOT add `is_admin=True` anywhere in this sweep;
   admin-specific behavior gets explicit tests in Tasks 3–4.
2. In `backend/tests/test_users_google.py`, replace
   `assert user.role == "user"` with:

```python
    assert user.is_admin is False
    assert user.membership == Membership.FREE
```

   (add `from app.modules.users.membership import Membership` to that file).

Leave every LLM/orchestration *message* `role` untouched (`Message(role=...)`,
`add_message(..., role=...)`, `row.role` — different concept).

- [ ] **Step 7: Apply the migration to dev and test DBs; verify reversibility**

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

Expected: all three succeed. Then run the same `upgrade head` with
`DATABASE_URL` set to your `TEST_DATABASE_URL` value so integration tests see
the new columns.

- [ ] **Step 8: Run the new test, then the full suite**

```bash
uv run pytest tests/test_user_authz_fields.py -v
uv run pytest -m "unit or integration"
```

Expected: PASS (4 new tests; full suite green — any failure here is a missed
sweep site).

- [ ] **Step 9: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat!: replace users.role with is_admin flag and membership tier\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 3: First-login admin-claim regression (SSO rule keeps conferring authority)

The `AuthService._resolve_google_user` matching rules are **unchanged** —
this task only proves the kept first-login rule now confers `is_admin=True`
via the seeded row, in exactly the production sequence: admin row seeded by
bootstrap, first Google login happens after the Task 2 migration ran (the
test DB is already at head, so the test reproduces that ordering).

**Files:**
- Modify: `backend/tests/test_google_login_service.py`

**Interfaces:**
- Consumes: `seed_admin_user` with `is_admin=True` (Task 2); `UserRead.is_admin` / `.membership` (Task 2); existing `AuthService.login_with_google` (SSO).
- Produces: nothing new — regression coverage only.

- [ ] **Step 1: Update the admin-claim test to seed via bootstrap and assert authority**

In `backend/tests/test_google_login_service.py`, add imports
`from app.core.bootstrap import seed_admin_user` and
`from app.modules.users.membership import Membership`, then replace
`test_first_google_login_claims_admin` with:

```python
@pytest.mark.integration
async def test_first_google_login_claims_admin(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    await seed_admin_user(session)  # exactly how the row exists in production
    _patch_google(monkeypatch, "sub-admin", "owner@example.com")
    user, token = await _service(session).login_with_google("code")
    assert user.username == settings.admin_username
    assert user.email == "owner@example.com"
    assert user.is_admin is True
    assert user.membership == Membership.FREE
    assert token
```

In `test_second_google_account_provisions_new_user`, seed the admin with
`await seed_admin_user(session)` instead of the manual `UserCreate` call, and
add after the existing assertions:

```python
    assert user.is_admin is False
```

- [ ] **Step 2: Run the file to verify it passes**

Run: `uv run pytest tests/test_google_login_service.py -v`
Expected: PASS. (If `is_admin is True` fails, Task 2's bootstrap change or
migration backfill is wrong — fix there, not here; the matching rules
themselves must not change.)

- [ ] **Step 3: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'test: verify first Google login inherits seeded admin authority\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 4: `NotAuthorizedError` + `require_admin` dependency + 403 mapping

**Files:**
- Modify: `backend/app/modules/auth/exceptions.py`
- Modify: `backend/app/core/exceptions.py` (`_register_auth_handlers`)
- Modify: `backend/app/core/deps.py`
- Test: `backend/tests/test_authz_deps_unit.py` (unit)
- Test: `backend/tests/test_authz_api.py` (integration matrix)

**Interfaces:**
- Consumes: `UserRead.is_admin` (Task 2); existing `get_current_user`.
- Produces (used by Task 5 and future backoffice routes):
  - `class NotAuthorizedError(AuthError)` in `app.modules.auth.exceptions`
  - Central handler: `NotAuthorizedError` → **403** `{"detail": "Not authorized"}` (distinct from the 401 of `NotAuthenticatedError`)
  - `async require_admin(current_user: UserRead = Depends(get_current_user)) -> UserRead` in `app.core.deps`
  - Test scaffolding reused by Task 5: `_build_app()` / `client` fixture in `backend/tests/test_authz_api.py`, `_user(...)` helper in `backend/tests/test_authz_deps_unit.py`.

- [ ] **Step 1: Write the failing unit tests**

```python
# backend/tests/test_authz_deps_unit.py
"""Unit tests for the authorization dependencies (no DB, no HTTP)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.deps import require_admin
from app.modules.auth.exceptions import NotAuthorizedError
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserRead


def _user(*, is_admin: bool = False, membership: Membership = Membership.FREE) -> UserRead:
    return UserRead(
        id=uuid4(),
        username="tester",
        email=None,
        is_admin=is_admin,
        membership=membership,
        created_at=datetime.now(UTC),
    )


@pytest.mark.unit
async def test_require_admin_returns_the_admin_user() -> None:
    user = _user(is_admin=True)
    assert await require_admin(user) is user


@pytest.mark.unit
async def test_require_admin_rejects_non_admin() -> None:
    with pytest.raises(NotAuthorizedError):
        await require_admin(_user())
```

- [ ] **Step 2: Write the failing integration tests (authorization matrix)**

```python
# backend/tests/test_authz_api.py
"""Authorization matrix over a test-local app using the real deps/handlers."""

from collections.abc import AsyncIterator, Callable
from typing import Annotated

import pytest
from app.core.config import get_settings
from app.core.deps import get_db, require_admin
from app.core.exceptions import register_exception_handlers
from app.core.security import create_access_token
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


def _build_app() -> FastAPI:
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/admin-only")
    async def admin_only(
        user: Annotated[UserRead, Depends(require_admin)],
    ) -> dict[str, str]:
        return {"username": user.username}

    return test_app


def _make_db_override(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[], AsyncIterator[AsyncSession]]:
    async def _override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return _override_db


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM users"))
    test_app = _build_app()
    test_app.dependency_overrides[get_db] = _make_db_override(session_factory)
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    test_app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM users"))
    await engine.dispose()


async def _login_as(client: AsyncClient, *, is_admin: bool) -> None:
    """Create a user directly and set their session cookie on the client."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    username = "matrix-admin" if is_admin else "matrix-user"
    async with factory() as session:
        user = await UserService(session).create(
            UserCreate(username=username, password="password123", is_admin=is_admin)
        )
        await session.commit()
    await engine.dispose()
    token = create_access_token(user_id=user.id, username=user.username, settings=settings)
    client.cookies.set("rtm_token", token)


@pytest.mark.integration
async def test_admin_route_rejects_anonymous(client: AsyncClient) -> None:
    response = await client.get("/admin-only")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.integration
async def test_admin_route_rejects_non_admin(client: AsyncClient) -> None:
    await _login_as(client, is_admin=False)
    response = await client.get("/admin-only")
    assert response.status_code == 403
    assert response.json() == {"detail": "Not authorized"}


@pytest.mark.integration
async def test_admin_route_allows_admin(client: AsyncClient) -> None:
    await _login_as(client, is_admin=True)
    response = await client.get("/admin-only")
    assert response.status_code == 200
    assert response.json() == {"username": "matrix-admin"}
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_authz_deps_unit.py tests/test_authz_api.py -v
```

Expected: FAIL with `ImportError: cannot import name 'require_admin'` (and
`NotAuthorizedError`).

- [ ] **Step 4: Implement**

Append to `backend/app/modules/auth/exceptions.py`:

```python
class NotAuthorizedError(AuthError):
    """Raised when the authenticated user lacks permission."""
```

In `backend/app/core/exceptions.py`, add `NotAuthorizedError` to the
`app.modules.auth.exceptions` import and register in
`_register_auth_handlers`:

```python
    @app.exception_handler(NotAuthorizedError)
    async def _not_authorized(
        _request: Request,
        _exc: NotAuthorizedError,
    ) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": "Not authorized"})
```

In `backend/app/core/deps.py`, change the auth-exceptions import to
`from app.modules.auth.exceptions import NotAuthenticatedError, NotAuthorizedError`
and append:

```python
async def require_admin(
    current_user: Annotated[UserRead, Depends(get_current_user)],
) -> UserRead:
    """Require an authenticated admin (backoffice authority flag)."""
    if not current_user.is_admin:
        raise NotAuthorizedError
    return current_user
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_authz_deps_unit.py tests/test_authz_api.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add require_admin dependency with typed 403 NotAuthorizedError\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 5: `require_membership(minimum)` dependency factory

No consumers yet by design — this is the hook for tier-gated features and
per-tier AI budgets. Tests pin the contract. Since only `free` exists, the
insufficient-tier path is exercised by patching the comparator/rank map (the
spec's accepted risk), never by inventing enum members.

**Files:**
- Modify: `backend/app/core/deps.py`
- Modify: `backend/tests/test_authz_deps_unit.py` (extend)
- Modify: `backend/tests/test_authz_api.py` (extend)

**Interfaces:**
- Consumes: `Membership`, `meets_minimum` (Task 1); `UserRead.membership` (Task 2); `NotAuthorizedError` (Task 4); Task 4's test scaffolding (`_user`, `_build_app`, `client`).
- Produces: `require_membership(minimum: Membership) -> Callable[[UserRead], Awaitable[UserRead]]` in `app.core.deps` — usage on future routes: `Depends(require_membership(Membership.FREE))`.

- [ ] **Step 1: Write the failing unit tests**

Append to `backend/tests/test_authz_deps_unit.py` (extend the
`app.core.deps` import with `require_membership`):

```python
@pytest.mark.unit
async def test_require_membership_passes_sufficient_tier() -> None:
    dep = require_membership(Membership.FREE)
    user = _user()
    assert await dep(user) is user


@pytest.mark.unit
async def test_require_membership_rejects_insufficient_tier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Only `free` exists; simulate a higher requirement by failing the comparator.
    monkeypatch.setattr("app.core.deps.meets_minimum", lambda actual, minimum: False)
    dep = require_membership(Membership.FREE)
    with pytest.raises(NotAuthorizedError):
        await dep(_user())
```

- [ ] **Step 2: Write the failing integration tests**

In `backend/tests/test_authz_api.py`: extend the `app.core.deps` import with
`require_membership`, add `from app.modules.users.membership import Membership`,
add a route to `_build_app()` after `admin_only`:

```python
    @test_app.get("/free-tier")
    async def free_tier(
        user: Annotated[UserRead, Depends(require_membership(Membership.FREE))],
    ) -> dict[str, str]:
        return {"username": user.username}
```

and append the tests:

```python
@pytest.mark.integration
async def test_membership_route_rejects_anonymous(client: AsyncClient) -> None:
    response = await client.get("/free-tier")
    assert response.status_code == 401


@pytest.mark.integration
async def test_membership_route_allows_free_user_at_free_minimum(
    client: AsyncClient,
) -> None:
    await _login_as(client, is_admin=False)
    response = await client.get("/free-tier")
    assert response.status_code == 200
    assert response.json() == {"username": "matrix-user"}


@pytest.mark.integration
async def test_membership_route_rejects_insufficient_tier(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.deps.meets_minimum", lambda actual, minimum: False)
    await _login_as(client, is_admin=False)
    response = await client.get("/free-tier")
    assert response.status_code == 403
    assert response.json() == {"detail": "Not authorized"}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_authz_deps_unit.py tests/test_authz_api.py -v`
Expected: FAIL with `ImportError: cannot import name 'require_membership'`.

- [ ] **Step 4: Implement the factory**

In `backend/app/core/deps.py`, extend imports (`from collections.abc import
AsyncGenerator, Awaitable, Callable` and
`from app.modules.users.membership import Membership, meets_minimum`) and
append:

```python
def require_membership(
    minimum: Membership,
) -> Callable[[UserRead], Awaitable[UserRead]]:
    """Dependency factory gating a route on a minimum membership tier.

    Ordering comes from MEMBERSHIP_RANK (in code, fail-closed) — this is the
    hook for tier-gated features and per-tier AI budgets.
    """

    async def _require(
        current_user: Annotated[UserRead, Depends(get_current_user)],
    ) -> UserRead:
        if not meets_minimum(current_user.membership, minimum):
            raise NotAuthorizedError
        return current_user

    return _require
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_authz_deps_unit.py tests/test_authz_api.py -v`
Expected: PASS (10 tests across the two files)

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add require_membership dependency factory with rank-map ordering\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 6: Frontend — mirror `UserRead` in auth types

Nothing in the frontend renders or reads `role` (verified by grep — the only
hits are ARIA attributes and assistant chat-message roles, which are
unrelated). This is a type-only change; `npm run build` is the proof.

**Files:**
- Modify: `frontend/src/features/auth/types.ts`

**Interfaces:**
- Consumes: the `UserRead` JSON shape from Task 2 (`is_admin`, `membership`, no `role`).
- Produces: `User` TS type consumed by `MeResponse` and the `me` query.

- [ ] **Step 1: Update the type**

Replace the `User` type in `frontend/src/features/auth/types.ts` (the file is
post-SSO, so `LoginResponse` is already gone — keep `MeResponse`):

```typescript
export type User = {
  id: string
  username: string
  email: string | null
  is_admin: boolean
  membership: string
  created_at: string
}
```

- [ ] **Step 2: Verify nothing referenced `role`**

Run (from `frontend/`):

```bash
grep -rn "\.role" src --include='*.ts' --include='*.tsx' | grep -v assistant
```

Expected: no output (assistant chat-message roles are the only `.role` users
and are excluded; ARIA `role="..."` attributes don't match `.role`).

- [ ] **Step 3: Frontend gates**

```bash
npm run lint
npm run build
npm run test
```

Expected: all pass — `build` (tsc) proves no dangling `role` usage.

- [ ] **Step 4: Commit**

```bash
printf 'feat: mirror is_admin/membership user fields in frontend auth types\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 7: Final verification sweep

**Files:** none new — verification only.

- [ ] **Step 1: Full backend gates**

From `backend/`:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy .
uv run pytest -m "unit or integration"
```

Expected: all clean.

- [ ] **Step 2: Migration chain sanity**

```bash
uv run alembic heads
uv run alembic downgrade -1 && uv run alembic upgrade head
```

Expected: exactly ONE head (this plan's revision, chained after
`db448309b4a6`); round-trip succeeds.

- [ ] **Step 3: Residual `role` grep**

```bash
grep -rn '\brole\b' app --include='*.py' | grep -v llm | grep -v orchestration | grep -v summaries
grep -rn 'role=' tests --include='*.py' | grep -iv 'message\|add_message\|Role\.'
```

Expected: no user-role hits anywhere (only LLM message roles remain, in the
excluded modules).

- [ ] **Step 4: Full frontend gates**

From `frontend/`:

```bash
npm run lint
npm run build
npm run test
```

Expected: all clean.

- [ ] **Step 5: Commit any stragglers and summarize**

Report per superpowers:verification-before-completion — show actual command
output for each gate before claiming done. Then follow
superpowers:finishing-a-development-branch.
