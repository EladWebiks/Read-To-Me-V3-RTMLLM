"""User persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User


class UserRepository:
    """DB access for the users table only."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Return a non-deleted user by id."""
        stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Return a non-deleted user by username."""
        stmt = select(User).where(User.username == username, User.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add(self, user: User) -> User:
        """Persist a new user and flush to assign defaults."""
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user
