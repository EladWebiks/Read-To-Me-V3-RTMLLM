"""DB access for the quotas module's tables only (membership_quotas)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.quotas.models import MembershipQuota


class MembershipQuotaRepository:
    """CRUD for quota rules; sparse by design (absent pair = unlimited)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, membership: str, quota_kind: str) -> MembershipQuota | None:
        stmt = select(MembershipQuota).where(
            MembershipQuota.membership == membership,
            MembershipQuota.quota_kind == quota_kind,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_membership(self, membership: str) -> list[MembershipQuota]:
        stmt = select(MembershipQuota).where(MembershipQuota.membership == membership)
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_all(self) -> list[MembershipQuota]:
        stmt = select(MembershipQuota).order_by(
            MembershipQuota.membership, MembershipQuota.quota_kind
        )
        return list((await self._session.execute(stmt)).scalars().all())

    def add(self, row: MembershipQuota) -> None:
        self._session.add(row)

    async def save(self, row: MembershipQuota) -> MembershipQuota:
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def delete(self, row: MembershipQuota) -> None:
        await self._session.delete(row)
        await self._session.flush()
