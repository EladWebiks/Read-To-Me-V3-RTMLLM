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

    async def get_by_email(self, email: str) -> User | None:
        """Return a non-deleted user by email."""
        stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_google_sub(self, google_sub: str) -> User | None:
        """Return a non-deleted user by Google subject id."""
        stmt = select(User).where(
            User.google_sub == google_sub,
            User.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def any_google_linked(self) -> bool:
        """True when any non-deleted user has a Google identity."""
        stmt = (
            select(User.id).where(User.google_sub.is_not(None), User.deleted_at.is_(None)).limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def save(self, user: User) -> User:
        """Flush pending changes on an already-tracked user."""
        await self._session.flush()
        await self._session.refresh(user)
        return user
