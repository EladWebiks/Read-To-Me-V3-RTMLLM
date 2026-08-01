"""Unit tests for the authorization dependencies (no DB, no HTTP)."""

from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from app.core.deps import require_admin, require_membership
from app.modules.auth.exceptions import NotAuthorizedError
from app.modules.users.schemas import UserRead
from sqlalchemy.ext.asyncio import AsyncSession

# The dependency only forwards the session to ensure_loaded, which every test
# here replaces with an AsyncMock — so no real session is ever touched.
_NO_SESSION = cast("AsyncSession", None)


def _user(*, is_admin: bool = False, membership: str = "free") -> UserRead:
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


@pytest.mark.unit
async def test_require_membership_passes_sufficient_tier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # This test exercises the dependency's wiring (ensure_loaded is awaited,
    # then meets_minimum gates the result) — meets_minimum's own cold/warm
    # snapshot logic is covered exhaustively in tests/memberships/test_registry.py.
    monkeypatch.setattr("app.core.deps.ensure_loaded", AsyncMock())
    monkeypatch.setattr("app.core.deps.meets_minimum", lambda actual, minimum: True)
    dep = require_membership("free")
    user = _user()
    assert await dep(user, _NO_SESSION) is user


@pytest.mark.unit
async def test_require_membership_rejects_insufficient_tier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Only `free` exists; simulate a higher requirement by failing the comparator.
    monkeypatch.setattr("app.core.deps.ensure_loaded", AsyncMock())
    monkeypatch.setattr("app.core.deps.meets_minimum", lambda actual, minimum: False)
    dep = require_membership("free")
    with pytest.raises(NotAuthorizedError):
        await dep(_user(), _NO_SESSION)
