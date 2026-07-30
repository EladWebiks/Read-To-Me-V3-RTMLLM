"""User persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
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
        """Return a non-deleted user by email, case-insensitively.

        Email is case-insensitive in practice, and rows seeded before Google
        SSO may hold mixed case (e.g. "Owner@Example.com"). Comparing verbatim
        would miss the match and silently fork a second, parallel account
        instead of linking the existing one, stranding its library. Writes
        normalize to lower case; this `lower()` covers legacy rows.
        """
        stmt = select(User).where(
            func.lower(User.email) == email.lower(),
            User.deleted_at.is_(None),
        )
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

    async def list_all(self, *, limit: int, offset: int) -> tuple[list[User], int]:
        """Backoffice page over ALL users, newest first, soft-deleted included."""
        total_stmt = select(func.count()).select_from(User)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = select(User).order_by(User.created_at.desc(), User.id).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows), total

    async def get_by_id_any(self, user_id: UUID) -> User | None:
        """Backoffice lookup that also returns soft-deleted users."""
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_username_any(self, username: str) -> User | None:
        """Identity-collision lookup: soft-deleted rows included.

        `users.username` is UNIQUE over the whole table, not just over live
        rows, so a soft-deleted row still owns its username. The
        deleted-filtered `get_by_username` cannot see it and would let an
        insert fail on the index instead of on a typed domain error.
        """
        result = await self._session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_email_any(self, email: str) -> User | None:
        """Identity-collision lookup by email (case-insensitive), deleted included."""
        stmt = select(User).where(func.lower(User.email) == email.lower())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_google_sub_any(self, google_sub: str) -> User | None:
        """Identity-collision lookup by Google subject id, deleted included."""
        result = await self._session.execute(select(User).where(User.google_sub == google_sub))
        return result.scalar_one_or_none()

    async def count_active_admins(self) -> int:
        """Non-deleted users with the admin flag."""
        stmt = (
            select(func.count())
            .select_from(User)
            .where(User.is_admin.is_(True), User.deleted_at.is_(None))
        )
        return int((await self._session.execute(stmt)).scalar_one())
