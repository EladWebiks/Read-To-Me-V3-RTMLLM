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
