"""Shared FastAPI dependencies."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.modules.auth.exceptions import NotAuthenticatedError
from app.modules.auth.service import AuthService
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
