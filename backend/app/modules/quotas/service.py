"""Quota limits resolution and enforcement (caller-metered).

This module is a LEAF: it imports users (identity) and its own code only.
Callers (orchestration, downloads, scraping, imports) measure their own
usage via their own repositories and hand the number to enforce() — that is
what lets domain services enforce quotas without importing the orchestrator.
Admins are exempt from ALL quota kinds here, in one place (spec §3.4);
nobody is exempt from per-turn caps (those live in orchestration).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.quotas.exceptions import QuotaExceededError, QuotaRuleNotFoundError
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.models import MembershipQuota, UserQuotaOverride
from app.modules.quotas.repository import MembershipQuotaRepository
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserRead
from app.modules.users.service import UserService

logger = logging.getLogger(__name__)

_DECEMBER = 12


def _values_from_rows(
    rows: Sequence[MembershipQuota] | Sequence[UserQuotaOverride],
) -> dict[QuotaKind, float]:
    """Keyed rows -> limits, skipping unknown kinds (fail-open, warned)."""
    values: dict[QuotaKind, float] = {}
    for row in rows:
        try:
            values[QuotaKind(row.quota_kind)] = row.limit_value
        except ValueError:
            logger.warning("ignoring unknown quota kind row", extra={"kind": row.quota_kind})
    return values


@dataclass(frozen=True, slots=True)
class QuotaLimits:
    """Resolved limits for one user. Missing kind = unlimited."""

    exempt: bool
    values: Mapping[QuotaKind, float]

    def limit(self, kind: QuotaKind) -> float | None:
        return None if self.exempt else self.values.get(kind)

    def any_limited(self, *kinds: QuotaKind) -> bool:
        return any(self.limit(kind) is not None for kind in kinds)


class QuotaService:
    """Resolve per-tier quota limits and compare metered usage against them."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = MembershipQuotaRepository(session)

    async def limits_for(self, user: UserRead) -> QuotaLimits:
        """Admin exempt > user override > tier row > unlimited.

        Specificity wins: an override replaces the tier limit for its kind
        whether it is looser or tighter. Read fresh per check — no cache, so
        an admin edit applies on the very next attempt.
        """
        if user.is_admin:
            return QuotaLimits(exempt=True, values={})
        values = _values_from_rows(await self._repo.list_for_membership(user.membership.value))
        values |= _values_from_rows(await self._repo.list_overrides_for_user(user.id))
        return QuotaLimits(exempt=False, values=values)

    async def limits_for_user_id(self, user_id: UUID) -> QuotaLimits:
        """Limits for a bare user id (domain-service path: they carry no UserRead)."""
        user = await UserService(self._session).get_by_id(user_id)
        return await self.limits_for(user)

    @staticmethod
    def current_month_window(now: datetime) -> tuple[datetime, datetime]:
        """[first-of-month, first-of-next-month) in UTC.

        Calendar months only; Stripe billing anchors are out of scope (§3.6).
        """
        moment = now.astimezone(UTC)
        start = datetime(moment.year, moment.month, 1, tzinfo=UTC)
        if moment.month == _DECEMBER:
            return start, datetime(moment.year + 1, 1, 1, tzinfo=UTC)
        return start, datetime(moment.year, moment.month + 1, 1, tzinfo=UTC)

    @staticmethod
    def enforce(
        kind: QuotaKind,
        used: float,
        limits: QuotaLimits,
        *,
        resets_at: datetime | None,
        user_id: UUID | None = None,
    ) -> None:
        """Raise QuotaExceededError when used >= limit. No-op if unlimited/exempt."""
        limit = limits.limit(kind)
        if limit is None or used < limit:
            return
        logger.info(
            "quota exceeded",
            extra={
                "user_id": str(user_id) if user_id else None,
                "kind": kind.value,
                "used": used,
                "limit": limit,
                "resets_at": resets_at.isoformat() if resets_at else None,
            },
        )
        raise QuotaExceededError(
            kind, limit=limit, used=used, resets_at=resets_at, user_id=user_id
        )

    async def list_quotas(self) -> list[MembershipQuota]:
        """All configured quota rules (sparse: absent pair = unlimited)."""
        return await self._repo.list_all()

    async def set_quota(
        self,
        membership: Membership,
        kind: QuotaKind,
        limit_value: float,
        *,
        actor_id: UUID,
    ) -> MembershipQuota:
        """Set or replace one rule for (membership, kind)."""
        row = await self._repo.get(membership.value, kind.value)
        if row is None:
            row = MembershipQuota(
                membership=membership.value, quota_kind=kind.value, limit_value=limit_value
            )
            self._repo.add(row)
        else:
            row.limit_value = limit_value
        saved = await self._repo.save(row)
        logger.info(
            "membership quota set",
            extra={
                "membership": membership.value,
                "kind": kind.value,
                "limit": limit_value,
                "actor": str(actor_id),
            },
        )
        return saved

    async def user_quotas(
        self, user_id: UUID
    ) -> tuple[Membership, dict[str, float], list[UserQuotaOverride]]:
        """(membership, sparse tier limits, override rows) for the admin dialog."""
        user = await UserService(self._session).get_by_id(user_id)  # 404s unknown ids
        tier_rows = await self._repo.list_for_membership(user.membership.value)
        tier_limits = {row.quota_kind: row.limit_value for row in tier_rows}
        overrides = await self._repo.list_overrides_for_user(user_id)
        return user.membership, tier_limits, overrides

    async def set_user_quota(
        self, user_id: UUID, kind: QuotaKind, limit_value: float, *, actor_id: UUID
    ) -> UserQuotaOverride:
        """Set or replace this user's override for one kind."""
        await UserService(self._session).get_by_id(user_id)
        row = await self._repo.get_override(user_id, kind.value)
        if row is None:
            row = UserQuotaOverride(
                user_id=user_id, quota_kind=kind.value, limit_value=limit_value
            )
            self._repo.add(row)
        else:
            row.limit_value = limit_value
        saved = await self._repo.save(row)
        logger.info(
            "user quota override set",
            extra={
                "user_id": str(user_id),
                "kind": kind.value,
                "limit": limit_value,
                "actor": str(actor_id),
            },
        )
        return saved

    async def clear_user_quota(self, user_id: UUID, kind: QuotaKind, *, actor_id: UUID) -> None:
        """Drop this user's override; their tier limit applies again."""
        row = await self._repo.get_override(user_id, kind.value)
        if row is None:
            raise QuotaRuleNotFoundError(str(user_id), kind.value)
        await self._repo.delete(row)
        logger.info(
            "user quota override cleared",
            extra={"user_id": str(user_id), "kind": kind.value, "actor": str(actor_id)},
        )

    async def clear_quota(
        self, membership: Membership, kind: QuotaKind, *, actor_id: UUID
    ) -> None:
        """Drop one rule; that (membership, kind) becomes unlimited again."""
        row = await self._repo.get(membership.value, kind.value)
        if row is None:
            raise QuotaRuleNotFoundError(membership.value, kind.value)
        await self._repo.delete(row)
        logger.info(
            "membership quota cleared",
            extra={
                "membership": membership.value,
                "kind": kind.value,
                "actor": str(actor_id),
            },
        )
