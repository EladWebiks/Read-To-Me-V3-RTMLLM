"""Shared FastAPI dependencies."""

from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.modules.auth.exceptions import NotAuthenticatedError, NotAuthorizedError
from app.modules.auth.service import AuthService
from app.modules.runtime_config.service import RuntimeConfigService
from app.modules.users.membership import Membership, meets_minimum
from app.modules.users.schemas import UserRead

COOKIE_NAME = "rtm_token"


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Request-scoped database session dependency."""
    async for session in get_db_session():
        yield session


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    rtm_token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> UserRead:
    """Require a valid session cookie; raise NotAuthenticatedError otherwise."""
    if not rtm_token:
        raise NotAuthenticatedError
    service = AuthService(session, settings)
    return await service.user_from_token(rtm_token)


async def require_admin(
    current_user: Annotated[UserRead, Depends(get_current_user)],
) -> UserRead:
    """Require an authenticated admin (backoffice authority flag)."""
    if not current_user.is_admin:
        raise NotAuthorizedError
    return current_user


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


async def get_effective_settings(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Settings:
    """Settings with DB overrides applied to runtime-tunable sections.

    Drop-in for `get_settings` — consumers migrate one Depends at a time.
    Cheap when the per-process cache is warm (no DB query).
    """
    return await RuntimeConfigService(session, settings).effective_settings()
