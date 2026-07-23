"""Library persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.library.models import UserBook


class LibraryRepository:
    """DB access for user_books only."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_membership(self, user_id: UUID, book_id: UUID) -> UserBook | None:
        """Return active membership if present."""
        stmt = select(UserBook).where(
            UserBook.user_id == user_id,
            UserBook.book_id == book_id,
            UserBook.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_book_ids(self, user_id: UUID) -> list[UUID]:
        """Return book ids in the user's library (newest first)."""
        stmt = (
            select(UserBook.book_id)
            .where(UserBook.user_id == user_id, UserBook.deleted_at.is_(None))
            .order_by(UserBook.added_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, membership: UserBook) -> UserBook:
        """Persist membership."""
        self._session.add(membership)
        await self._session.flush()
        return membership

    async def soft_delete(self, membership: UserBook) -> None:
        """Soft-delete membership."""
        membership.deleted_at = datetime.now(UTC)
        await self._session.flush()
