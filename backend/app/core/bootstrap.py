"""Bootstrap helpers run at application startup."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.modules.users.schemas import UserCreate
from app.modules.users.service import UserService

logger = logging.getLogger(__name__)


async def seed_admin_user(session: AsyncSession | None = None) -> None:
    """Ensure the configured admin user exists (idempotent)."""
    settings = get_settings()
    data = UserCreate(
        username=settings.auth.admin_username,
        password=settings.auth.admin_password,
        role="admin",
    )
    if session is not None:
        user = await UserService(session).ensure_user(data)
        logger.info("Admin user ready: %s", user.username)
        return

    async with SessionLocal() as owned:
        user = await UserService(owned).ensure_user(data)
        await owned.commit()
    logger.info("Admin user ready: %s", user.username)
