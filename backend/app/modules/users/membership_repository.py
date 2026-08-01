"""DB access for the memberships table (and tier-scoped user queries)."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import MembershipTier, User


class MembershipRepository:
    """memberships access; user_counts/reassign touch users (same module)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_slug(self, slug: str) -> MembershipTier | None:
        stmt = select(MembershipTier).where(MembershipTier.slug == slug)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_all(self) -> list[MembershipTier]:
        stmt = select(MembershipTier).order_by(MembershipTier.rank, MembershipTier.slug)
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_default(self) -> MembershipTier | None:
        stmt = select(MembershipTier).where(MembershipTier.is_default.is_(True))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    def add(self, row: MembershipTier) -> None:
        self._session.add(row)

    async def save(self, row: MembershipTier) -> MembershipTier:
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def clear_default(self) -> None:
        """Un-crown the current default (crowning swap, step 1)."""
        await self._session.execute(
            update(MembershipTier)
            .where(MembershipTier.is_default.is_(True))
            .values(is_default=False)
        )

    async def user_counts(self) -> dict[str, int]:
        """slug -> live user count (soft-deleted included: they still hold a tier)."""
        stmt = select(User.membership, func.count()).group_by(User.membership)
        return {slug: int(count) for slug, count in (await self._session.execute(stmt)).all()}

    async def reassign_users(self, from_slug: str, to_slug: str) -> int:
        """Move every user off a tier (deactivation migration). Returns count."""
        # execute() is typed as Result[Any]; an UPDATE always yields a
        # CursorResult, which is the only shape carrying rowcount.
        result = cast(
            "CursorResult[Any]",
            await self._session.execute(
                update(User).where(User.membership == from_slug).values(membership=to_slug)
            ),
        )
        return int(result.rowcount or 0)
