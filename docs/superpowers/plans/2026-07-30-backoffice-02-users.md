# Backoffice 02 — Users Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admin user management: paginated cross-user list (soft-deleted visible, marked), toggle `is_admin`, membership operator-override, soft-delete/restore — with safety rails (no self-demote, no self-delete, never zero active admins).

**Architecture:** All logic in the users module (`UserService` admin methods over new admin-scoped `UserRepository` reads); `modules/admin/users_router.py` is a thin HTTP layer added to the foundation aggregator. Frontend screen composes the foundation's pagination primitives.

**Tech Stack:** FastAPI, SQLAlchemy async, pydantic v2, pytest; React 19, react-query, vitest.

**Spec:** `docs/superpowers/specs/2026-07-30-backoffice-mvp-design.md`. **Depends on:** `2026-07-30-backoffice-01-foundation.md` (Page/PageParams, aggregator router, test harness, RequireAdmin routes, pagination primitives).

## Global Constraints

- Backend gates per task (run from `backend/`): `uv run ruff check . --fix && uv run ruff format .`, `uv run mypy .`, `uv run pytest -m "unit or integration"`. Integration tests need Postgres/Redis/MinIO and `TEST_DATABASE_URL` pointing at a separate test DB.
- Frontend gates per task (run from `frontend/`): `npm run lint`, `npm run build`, `npm run test`.
- Commit with `bash scripts/git-commit-clean.sh /tmp/msg.txt`. **Never** add attribution trailers. Verify with `git log -1 --format=%B`.
- Ruff limits: complexity ≤10, statements ≤20, branches ≤6, args ≤6. ESLint limits: file ≤110 lines, function ≤60, nesting ≤3 (tests/barrels exempt).
- Admin reads are new, admin-named methods — never loosen ownership-scoped ones. Actor identity always from `require_admin`, never the body.
- Every new route registers in `backend/tests/admin/test_authz_matrix.py::ROUTES`.
- No Alembic migrations in this plan.

---

### Task 1: Users module — admin service methods + safety rails

**Files:**
- Modify: `backend/app/modules/users/repository.py`
- Modify: `backend/app/modules/users/schemas.py`
- Modify: `backend/app/modules/users/exceptions.py`
- Modify: `backend/app/modules/users/service.py`
- Modify: `backend/app/core/exceptions.py`
- Test: `backend/tests/test_users_admin_service.py`

**Interfaces:**
- Consumes: existing `User` model, `UserRepository`, `UserService`, `Membership`.
- Produces (used by Task 2):
  - `UserAdminRead` (pydantic): `id: UUID`, `username: str`, `email: str | None`, `is_admin: bool`, `membership: Membership`, `google_linked: bool`, `created_at: datetime`, `deleted_at: datetime | None`; classmethod `from_user(user: User) -> UserAdminRead`.
  - `UserAdminPatch` (pydantic): `is_admin: bool | None = None`, `membership: Membership | None = None`.
  - `UserService.list_users_admin(*, limit: int, offset: int) -> tuple[list[UserAdminRead], int]`
  - `UserService.update_user_admin(*, actor_id: UUID, user_id: UUID, patch: UserAdminPatch) -> UserAdminRead`
  - `UserService.soft_delete_user_admin(*, actor_id: UUID, user_id: UUID) -> UserAdminRead`
  - `UserService.restore_user_admin(user_id: UUID) -> UserAdminRead`
  - Exceptions `AdminSelfActionError`, `LastAdminError` → both HTTP 409.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_users_admin_service.py
"""UserService backoffice methods + safety rails (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.modules.users.exceptions import AdminSelfActionError, LastAdminError
from app.modules.users.schemas import UserAdminPatch, UserCreate
from app.modules.users.service import UserService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.dbcleanup import clear_users


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await clear_users(conn)
    async with factory() as sess:
        yield sess
        await sess.rollback()
    async with engine.begin() as conn:
        await clear_users(conn)
    await engine.dispose()


def _user(username: str, *, is_admin: bool = False) -> UserCreate:
    return UserCreate(username=username, password="password123", is_admin=is_admin)


@pytest.mark.integration
async def test_list_users_admin_includes_soft_deleted(session: AsyncSession) -> None:
    service = UserService(session)
    admin = await service.create(_user("boss", is_admin=True))
    victim = await service.create(_user("victim"))
    await service.soft_delete_user_admin(actor_id=admin.id, user_id=victim.id)
    items, total = await service.list_users_admin(limit=10, offset=0)
    assert total == 2
    by_name = {u.username: u for u in items}
    assert by_name["victim"].deleted_at is not None
    assert by_name["boss"].deleted_at is None
    assert by_name["boss"].google_linked is False


@pytest.mark.integration
async def test_self_demotion_blocked(session: AsyncSession) -> None:
    service = UserService(session)
    admin = await service.create(_user("boss", is_admin=True))
    with pytest.raises(AdminSelfActionError):
        await service.update_user_admin(
            actor_id=admin.id, user_id=admin.id, patch=UserAdminPatch(is_admin=False)
        )


@pytest.mark.integration
async def test_self_delete_blocked(session: AsyncSession) -> None:
    service = UserService(session)
    admin = await service.create(_user("boss", is_admin=True))
    with pytest.raises(AdminSelfActionError):
        await service.soft_delete_user_admin(actor_id=admin.id, user_id=admin.id)


@pytest.mark.integration
async def test_last_admin_cannot_be_demoted(session: AsyncSession) -> None:
    service = UserService(session)
    admin = await service.create(_user("only-admin", is_admin=True))
    with pytest.raises(LastAdminError):
        await service.update_user_admin(
            actor_id=uuid4(), user_id=admin.id, patch=UserAdminPatch(is_admin=False)
        )


@pytest.mark.integration
async def test_last_admin_cannot_be_deleted(session: AsyncSession) -> None:
    service = UserService(session)
    admin = await service.create(_user("only-admin", is_admin=True))
    with pytest.raises(LastAdminError):
        await service.soft_delete_user_admin(actor_id=uuid4(), user_id=admin.id)


@pytest.mark.integration
async def test_demoting_one_of_two_admins_works(session: AsyncSession) -> None:
    service = UserService(session)
    actor = await service.create(_user("boss", is_admin=True))
    other = await service.create(_user("other", is_admin=True))
    updated = await service.update_user_admin(
        actor_id=actor.id, user_id=other.id, patch=UserAdminPatch(is_admin=False)
    )
    assert updated.is_admin is False


@pytest.mark.integration
async def test_soft_delete_then_restore(session: AsyncSession) -> None:
    service = UserService(session)
    admin = await service.create(_user("boss", is_admin=True))
    victim = await service.create(_user("victim"))
    deleted = await service.soft_delete_user_admin(actor_id=admin.id, user_id=victim.id)
    assert deleted.deleted_at is not None
    restored = await service.restore_user_admin(victim.id)
    assert restored.deleted_at is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `uv run pytest tests/test_users_admin_service.py -v`
Expected: FAIL with `ImportError` (`AdminSelfActionError` does not exist).

- [ ] **Step 3: Add exceptions**

Append to `backend/app/modules/users/exceptions.py`:

```python
class AdminSelfActionError(UserError):
    """An admin tried to demote or soft-delete their own account."""


class LastAdminError(UserError):
    """The operation would leave zero active (non-deleted) admins."""
```

- [ ] **Step 4: Add repository methods**

Append to `UserRepository` in `backend/app/modules/users/repository.py`:

```python
    async def list_all(self, *, limit: int, offset: int) -> tuple[list[User], int]:
        """Backoffice page over ALL users, newest first, soft-deleted included."""
        total_stmt = select(func.count()).select_from(User)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(User)
            .order_by(User.created_at.desc(), User.id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows), total

    async def get_by_id_any(self, user_id: UUID) -> User | None:
        """Backoffice lookup that also returns soft-deleted users."""
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def count_active_admins(self) -> int:
        """Non-deleted users with the admin flag."""
        stmt = (
            select(func.count())
            .select_from(User)
            .where(User.is_admin.is_(True), User.deleted_at.is_(None))
        )
        return int((await self._session.execute(stmt)).scalar_one())
```

- [ ] **Step 5: Add schemas**

In `backend/app/modules/users/schemas.py`, make the import block:

```python
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.users.membership import Membership

if TYPE_CHECKING:
    from app.modules.users.models import User
```

(keep `UserCreate`/`UserRead` unchanged), then append:

```python
class UserAdminRead(BaseModel):
    """Backoffice view of one user (soft-deleted rows included, marked)."""

    id: UUID
    username: str
    email: str | None
    is_admin: bool
    membership: Membership
    google_linked: bool
    created_at: datetime
    deleted_at: datetime | None

    @classmethod
    def from_user(cls, user: User) -> UserAdminRead:
        """Build the admin row; google_linked derives from google_sub."""
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            is_admin=user.is_admin,
            membership=Membership(user.membership),
            google_linked=user.google_sub is not None,
            created_at=user.created_at,
            deleted_at=user.deleted_at,
        )


class UserAdminPatch(BaseModel):
    """PATCH /api/admin/users/{id} body — only supplied fields change."""

    is_admin: bool | None = None
    membership: Membership | None = None
```

- [ ] **Step 6: Add service methods**

Append to `UserService` in `backend/app/modules/users/service.py` (extend imports with `from datetime import UTC, datetime`, `AdminSelfActionError`, `LastAdminError`, `UserAdminPatch`, `UserAdminRead`):

```python
    async def list_users_admin(
        self, *, limit: int, offset: int
    ) -> tuple[list[UserAdminRead], int]:
        """Backoffice page over all users, soft-deleted included."""
        users, total = await self._repo.list_all(limit=limit, offset=offset)
        return [UserAdminRead.from_user(user) for user in users], total

    async def update_user_admin(
        self, *, actor_id: UUID, user_id: UUID, patch: UserAdminPatch
    ) -> UserAdminRead:
        """Apply is_admin/membership changes with backoffice safety rails."""
        user = await self._require_any(user_id)
        if patch.is_admin is not None and patch.is_admin != user.is_admin:
            await self._guard_demotion(actor_id, user, demote=not patch.is_admin)
            user.is_admin = patch.is_admin
        if patch.membership is not None:
            user.membership = patch.membership
        return UserAdminRead.from_user(await self._repo.save(user))

    async def soft_delete_user_admin(
        self, *, actor_id: UUID, user_id: UUID
    ) -> UserAdminRead:
        """Soft-delete a user; blocked for self and for the last active admin."""
        user = await self._require_any(user_id)
        if user.id == actor_id:
            raise AdminSelfActionError("self-delete")
        if user.is_admin and user.deleted_at is None:
            await self._guard_last_admin()
        if user.deleted_at is None:
            user.deleted_at = datetime.now(UTC)
        return UserAdminRead.from_user(await self._repo.save(user))

    async def restore_user_admin(self, user_id: UUID) -> UserAdminRead:
        """Clear a user's soft-delete marker."""
        user = await self._require_any(user_id)
        user.deleted_at = None
        return UserAdminRead.from_user(await self._repo.save(user))

    async def _require_any(self, user_id: UUID) -> User:
        user = await self._repo.get_by_id_any(user_id)
        if user is None:
            raise UserNotFoundError(str(user_id))
        return user

    async def _guard_demotion(self, actor_id: UUID, user: User, *, demote: bool) -> None:
        if not demote:
            return
        if user.id == actor_id:
            raise AdminSelfActionError("self-demote")
        if user.deleted_at is None:
            await self._guard_last_admin()

    async def _guard_last_admin(self) -> None:
        if await self._repo.count_active_admins() <= 1:
            raise LastAdminError("at least one active admin must remain")
```

- [ ] **Step 7: Map the new exceptions to 409**

In `backend/app/core/exceptions.py`, extend the users import to include `AdminSelfActionError` and `LastAdminError`, add `_register_admin_user_handlers(app)` to `register_exception_handlers`, and append:

```python
def _register_admin_user_handlers(app: FastAPI) -> None:
    @app.exception_handler(AdminSelfActionError)
    async def _admin_self_action(
        _request: Request,
        _exc: AdminSelfActionError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": "Admins cannot demote or delete their own account"},
        )

    @app.exception_handler(LastAdminError)
    async def _last_admin(
        _request: Request,
        _exc: LastAdminError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": "At least one active admin must remain"},
        )
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/test_users_admin_service.py -v`
Expected: PASS (7 tests)

- [ ] **Step 9: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add backoffice user admin methods with safety rails\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 2: `/api/admin/users` routes

**Files:**
- Create: `backend/app/modules/admin/users_router.py`
- Modify: `backend/app/modules/admin/router.py`
- Modify: `backend/tests/admin/test_authz_matrix.py`
- Test: `backend/tests/admin/test_users_admin_api.py`

**Interfaces:**
- Consumes: Task 1's service methods/schemas; foundation's `Page`, `PageParams`, aggregator router, test harness.
- Produces: `GET /api/admin/users`, `PATCH /api/admin/users/{id}`, `DELETE /api/admin/users/{id}`, `POST /api/admin/users/{id}/restore` (used by Task 3's screen).

- [ ] **Step 1: Write the failing tests**

Append to `ROUTES` in `backend/tests/admin/test_authz_matrix.py`:

```python
    ("GET", "/api/admin/users", None),
    ("PATCH", f"/api/admin/users/{ZERO}", {"is_admin": True}),
    ("DELETE", f"/api/admin/users/{ZERO}", None),
    ("POST", f"/api/admin/users/{ZERO}/restore", None),
```

```python
# backend/tests/admin/test_users_admin_api.py
"""Backoffice user management API (needs Postgres)."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient

from tests.admin.helpers import create_user, login

BASE = "/api/admin/users"
ZERO = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
async def admin(client: AsyncClient) -> UUID:
    user_id = await create_user("boss", is_admin=True)
    login(client, user_id, "boss")
    return user_id


@pytest.mark.integration
async def test_list_includes_soft_deleted_marked(client: AsyncClient, admin: UUID) -> None:
    await create_user("ghost", deleted=True)
    response = await client.get(BASE)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    ghost = next(u for u in payload["items"] if u["username"] == "ghost")
    assert ghost["deleted_at"] is not None
    boss = next(u for u in payload["items"] if u["username"] == "boss")
    assert boss["deleted_at"] is None
    assert boss["google_linked"] is True


@pytest.mark.integration
async def test_pagination_envelope(client: AsyncClient, admin: UUID) -> None:
    for index in range(3):
        await create_user(f"user-{index}")
    response = await client.get(f"{BASE}?limit=2&offset=0")
    payload = response.json()
    assert payload["total"] == 4
    assert len(payload["items"]) == 2
    assert payload["limit"] == 2
    assert payload["offset"] == 0


@pytest.mark.integration
async def test_promote_then_demote_other_user(client: AsyncClient, admin: UUID) -> None:
    other = await create_user("other")
    up = await client.patch(f"{BASE}/{other}", json={"is_admin": True})
    assert up.status_code == 200
    assert up.json()["is_admin"] is True
    down = await client.patch(f"{BASE}/{other}", json={"is_admin": False})
    assert down.status_code == 200
    assert down.json()["is_admin"] is False


@pytest.mark.integration
async def test_cannot_demote_self(client: AsyncClient, admin: UUID) -> None:
    response = await client.patch(f"{BASE}/{admin}", json={"is_admin": False})
    assert response.status_code == 409


@pytest.mark.integration
async def test_cannot_delete_self(client: AsyncClient, admin: UUID) -> None:
    response = await client.delete(f"{BASE}/{admin}")
    assert response.status_code == 409


@pytest.mark.integration
async def test_delete_other_admin_allowed_when_two(client: AsyncClient, admin: UUID) -> None:
    other = await create_user("other-admin", is_admin=True)
    response = await client.delete(f"{BASE}/{other}")
    assert response.status_code == 200
    assert response.json()["deleted_at"] is not None


@pytest.mark.integration
async def test_soft_delete_then_restore(client: AsyncClient, admin: UUID) -> None:
    target = await create_user("victim")
    deleted = await client.delete(f"{BASE}/{target}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted_at"] is not None
    restored = await client.post(f"{BASE}/{target}/restore")
    assert restored.status_code == 200
    assert restored.json()["deleted_at"] is None


@pytest.mark.integration
async def test_membership_change_valid_and_invalid(client: AsyncClient, admin: UUID) -> None:
    target = await create_user("member")
    ok = await client.patch(f"{BASE}/{target}", json={"membership": "free"})
    assert ok.status_code == 200
    assert ok.json()["membership"] == "free"
    bad = await client.patch(f"{BASE}/{target}", json={"membership": "platinum"})
    assert bad.status_code == 422


@pytest.mark.integration
async def test_unknown_user_404(client: AsyncClient, admin: UUID) -> None:
    response = await client.patch(f"{BASE}/{ZERO}", json={"is_admin": True})
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/admin -v`
Expected: FAIL — 404 on every `/api/admin/users` request (routes missing).

- [ ] **Step 3: Implement the router**

```python
# backend/app/modules/admin/users_router.py
"""Backoffice user management routes. HTTP only; logic in UserService."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_admin
from app.modules.admin.params import PageParams
from app.modules.admin.schemas import Page
from app.modules.users.schemas import UserAdminPatch, UserAdminRead, UserRead
from app.modules.users.service import UserService

router = APIRouter(prefix="/users")


def _service(session: Annotated[AsyncSession, Depends(get_db)]) -> UserService:
    return UserService(session)


@router.get("")
async def list_users(
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[UserService, Depends(_service)],
    page: Annotated[PageParams, Depends()],
) -> Page[UserAdminRead]:
    """All users (soft-deleted included, marked), newest first."""
    items, total = await service.list_users_admin(limit=page.limit, offset=page.offset)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.patch("/{user_id}")
async def patch_user(
    user_id: UUID,
    body: UserAdminPatch,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[UserService, Depends(_service)],
) -> UserAdminRead:
    """Toggle is_admin / change membership (operator override; Stripe later)."""
    return await service.update_user_admin(actor_id=admin.id, user_id=user_id, patch=body)


@router.delete("/{user_id}")
async def soft_delete_user(
    user_id: UUID,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[UserService, Depends(_service)],
) -> UserAdminRead:
    """Soft-delete a user (row stays visible in the backoffice, marked)."""
    return await service.soft_delete_user_admin(actor_id=admin.id, user_id=user_id)


@router.post("/{user_id}/restore")
async def restore_user(
    user_id: UUID,
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[UserService, Depends(_service)],
) -> UserAdminRead:
    """Clear a user's soft-delete marker."""
    return await service.restore_user_admin(user_id)
```

In `backend/app/modules/admin/router.py`, add:

```python
from app.modules.admin.users_router import router as users_router
```

and after the `router = APIRouter(...)` line:

```python
router.include_router(users_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/admin -v`
Expected: PASS (8 matrix cases + 10 API tests; scaffold test unchanged)

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add backoffice user management routes\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 3: Users screen

**Files:**
- Create: `frontend/src/features/admin/api/users.ts`
- Create: `frontend/src/features/admin/hooks/useAdminUsers.ts`
- Create: `frontend/src/features/admin/components/users/UsersPage.tsx`
- Create: `frontend/src/features/admin/components/users/UsersTable.tsx`
- Create: `frontend/src/features/admin/components/users/UserRow.tsx`
- Modify: `frontend/src/features/admin/index.ts`
- Modify: `frontend/src/app/App.tsx` (swap the users placeholder)

**Interfaces:**
- Consumes: Task 2 routes; foundation's `Page<T>`, `apiPatch`, `usePageState`, `PaginationControls`.
- Produces: `UsersPage` export.

- [ ] **Step 1: Implement API + hooks**

```typescript
// frontend/src/features/admin/api/users.ts
import type { Page } from '@/features/admin/types'
import { apiDelete, apiGet, apiPatch, apiPost } from '@/shared/lib/api'

/** Mirrors UserAdminRead (users/schemas.py) exactly. */
export type AdminUser = {
  id: string
  username: string
  email: string | null
  is_admin: boolean
  membership: string
  google_linked: boolean
  created_at: string
  deleted_at: string | null
}

export type AdminUserPatch = { is_admin?: boolean; membership?: string }

/** Mirrors the Membership enum; extend when tiers ship. */
export const MEMBERSHIPS = ['free'] as const

export function fetchAdminUsers(limit: number, offset: number): Promise<Page<AdminUser>> {
  return apiGet(`/api/admin/users?limit=${limit}&offset=${offset}`)
}

export function patchAdminUser(id: string, body: AdminUserPatch): Promise<AdminUser> {
  return apiPatch(`/api/admin/users/${id}`, body)
}

export function softDeleteAdminUser(id: string): Promise<AdminUser> {
  return apiDelete(`/api/admin/users/${id}`)
}

export function restoreAdminUser(id: string): Promise<AdminUser> {
  return apiPost(`/api/admin/users/${id}/restore`)
}
```

```typescript
// frontend/src/features/admin/hooks/useAdminUsers.ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchAdminUsers,
  patchAdminUser,
  restoreAdminUser,
  softDeleteAdminUser,
  type AdminUserPatch,
} from '@/features/admin/api/users'

const usersKey = ['admin', 'users'] as const

export function useAdminUsers(limit: number, offset: number) {
  return useQuery({
    queryKey: [...usersKey, limit, offset],
    queryFn: () => fetchAdminUsers(limit, offset),
  })
}

function useInvalidateUsers() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: usersKey })
}

export function usePatchUser() {
  const invalidate = useInvalidateUsers()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: AdminUserPatch }) =>
      patchAdminUser(id, body),
    onSuccess: invalidate,
  })
}

export function useDeleteUser() {
  const invalidate = useInvalidateUsers()
  return useMutation({ mutationFn: softDeleteAdminUser, onSuccess: invalidate })
}

export function useRestoreUser() {
  const invalidate = useInvalidateUsers()
  return useMutation({ mutationFn: restoreAdminUser, onSuccess: invalidate })
}
```

- [ ] **Step 2: Implement the components**

```tsx
// frontend/src/features/admin/components/users/UsersPage.tsx
import { PaginationControls } from '@/features/admin/components/common/PaginationControls'
import { useAdminUsers } from '@/features/admin/hooks/useAdminUsers'
import { usePageState } from '@/features/admin/hooks/usePageState'
import { UsersTable } from './UsersTable'

export function UsersPage() {
  const page = usePageState(50)
  const { data, isLoading, error } = useAdminUsers(page.limit, page.offset)
  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading users…</p>
  }
  if (error || !data) {
    return <p className="text-sm text-destructive">Failed to load users.</p>
  }
  return (
    <section>
      <h1 className="mb-1 text-lg font-semibold">Users</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Membership changes here are an operator override — membership will be Stripe-managed
        later. Soft-deleted users stay listed and can be restored.
      </p>
      <UsersTable users={data.items} />
      <PaginationControls
        total={data.total}
        limit={page.limit}
        offset={page.offset}
        onPrev={page.prev}
        onNext={() => page.next(data.total)}
      />
    </section>
  )
}
```

```tsx
// frontend/src/features/admin/components/users/UsersTable.tsx
import type { AdminUser } from '@/features/admin/api/users'
import { UserRow } from './UserRow'

export function UsersTable({ users }: { users: AdminUser[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-muted-foreground">
          <tr>
            <th className="px-2 py-1.5 font-medium">Username</th>
            <th className="px-2 py-1.5 font-medium">Email</th>
            <th className="px-2 py-1.5 font-medium">Admin</th>
            <th className="px-2 py-1.5 font-medium">Membership</th>
            <th className="px-2 py-1.5 font-medium">Google</th>
            <th className="px-2 py-1.5 font-medium">Created</th>
            <th className="px-2 py-1.5 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <UserRow key={user.id} user={user} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

```tsx
// frontend/src/features/admin/components/users/UserRow.tsx
import { MEMBERSHIPS, type AdminUser } from '@/features/admin/api/users'
import {
  useDeleteUser,
  usePatchUser,
  useRestoreUser,
} from '@/features/admin/hooks/useAdminUsers'

export function UserRow({ user }: { user: AdminUser }) {
  const patch = usePatchUser()
  const remove = useDeleteUser()
  const restore = useRestoreUser()
  const deleted = user.deleted_at !== null
  const error = patch.error ?? remove.error ?? restore.error

  const toggleAdmin = () => {
    if (window.confirm(`${user.is_admin ? 'Remove' : 'Grant'} admin for ${user.username}?`)) {
      patch.mutate({ id: user.id, body: { is_admin: !user.is_admin } })
    }
  }

  const softDelete = () => {
    if (window.confirm(`Soft-delete ${user.username}?`)) {
      remove.mutate(user.id)
    }
  }

  return (
    <tr className={`border-t border-border/60 ${deleted ? 'opacity-60' : ''}`}>
      <td className="px-2 py-1.5">
        {user.username}
        {deleted && (
          <span className="ml-2 rounded bg-destructive/15 px-1.5 py-0.5 text-xs text-destructive">
            deleted
          </span>
        )}
      </td>
      <td className="px-2 py-1.5 text-muted-foreground">{user.email ?? '—'}</td>
      <td className="px-2 py-1.5">
        <input
          type="checkbox"
          checked={user.is_admin}
          aria-label={`Admin flag for ${user.username}`}
          onChange={toggleAdmin}
        />
      </td>
      <td className="px-2 py-1.5">
        <select
          className="rounded border border-border bg-background px-1 py-0.5 text-xs"
          value={user.membership}
          aria-label={`Membership for ${user.username} (operator override)`}
          onChange={(event) =>
            patch.mutate({ id: user.id, body: { membership: event.target.value } })
          }
        >
          {MEMBERSHIPS.map((tier) => (
            <option key={tier} value={tier}>
              {tier}
            </option>
          ))}
        </select>
      </td>
      <td className="px-2 py-1.5">{user.google_linked ? 'linked' : '—'}</td>
      <td className="px-2 py-1.5 text-muted-foreground">
        {new Date(user.created_at).toLocaleDateString()}
      </td>
      <td className="px-2 py-1.5">
        {deleted ? (
          <button type="button" className="text-xs underline" onClick={() => restore.mutate(user.id)}>
            Restore
          </button>
        ) : (
          <button type="button" className="text-xs underline" onClick={softDelete}>
            Delete
          </button>
        )}
        {error ? <p className="text-xs text-destructive">{error.message}</p> : null}
      </td>
    </tr>
  )
}
```

- [ ] **Step 3: Wire the route and barrel**

Append to `frontend/src/features/admin/index.ts`:

```typescript
export { UsersPage } from './components/users/UsersPage'
```

In `frontend/src/app/App.tsx`: extend the `@/features/admin` import with `UsersPage` and change the users route to:

```tsx
<Route path="users" element={<UsersPage />} />
```

- [ ] **Step 4: Gates + commit**

```bash
cd frontend && npm run lint && npm run build && npm run test && cd ..
printf 'feat: add backoffice users screen\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```
