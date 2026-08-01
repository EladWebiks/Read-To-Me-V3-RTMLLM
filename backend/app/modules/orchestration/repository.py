"""DB access for orchestration-owned tables (membership_policies only)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orchestration.models import MembershipPolicy


class MembershipPolicyRepository:
    """membership_policies access — this module's table only."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_membership(self, membership: str) -> MembershipPolicy | None:
        stmt = select(MembershipPolicy).where(MembershipPolicy.membership == membership)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_all(self) -> list[MembershipPolicy]:
        stmt = select(MembershipPolicy).order_by(MembershipPolicy.membership)
        return list((await self._session.execute(stmt)).scalars().all())

    def add(self, row: MembershipPolicy) -> None:
        self._session.add(row)

    async def save(self, row: MembershipPolicy) -> MembershipPolicy:
        await self._session.flush()
        await self._session.refresh(row)
        return row
