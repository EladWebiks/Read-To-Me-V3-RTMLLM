"""Rolled reads + rejection recording. Imports NO domain modules.

Hybrid rule (spec §7): closed days come from usage_daily; TODAY is always
read live from raw tables by the CALLER (each domain's existing meter with a
today window) — that one-directional split is what keeps domain -> usage
imports cycle-free. rollup.py is the only usage file importing domains.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.service import QuotaService
from app.modules.usage.kinds import (
    KIND_METRICS,
    LlmModelFact,
    LlmTaskFact,
    UsageMetric,
)
from app.modules.usage.repository import UsageRepository


class UsageReadService:
    """Read side of the rollup: closed-day sums for quota and admin callers."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = UsageRepository(session)

    @staticmethod
    def hybrid_split(now: datetime) -> tuple[date, datetime]:
        """(today's UTC date, today's 00:00 UTC) — rolled reads end BEFORE
        today; the caller's raw tail starts AT today_start."""
        today = now.astimezone(UTC).date()
        return today, datetime.combine(today, time(), tzinfo=UTC)

    async def rolled_amount(
        self,
        user_id: UUID,
        metrics: tuple[UsageMetric, ...],
        *,
        start_day: date,
        end_day: date,
    ) -> float:
        """Sum of the given metrics over [start_day, end_day) for one user."""
        return await self._repo.rolled_amount(
            user_id, metrics, start_day=start_day, end_day=end_day
        )

    async def rolled_month_amount(self, user_id: UUID, kind: QuotaKind, now: datetime) -> float:
        """Rolled part of the current month for a quota kind: [month start, today)."""
        month_start, _ = QuotaService.current_month_window(now)
        today, _ = self.hybrid_split(now)
        return await self._repo.rolled_amount(
            user_id, KIND_METRICS[kind], start_day=month_start.date(), end_day=today
        )

    async def rolled_user_table(
        self, *, start_day: date, end_day: date
    ) -> dict[UUID, dict[UsageMetric, float]]:
        """Per-user metric sums over [start_day, end_day)."""
        return await self._repo.rolled_user_table(start_day=start_day, end_day=end_day)

    async def rolled_totals(
        self, metrics: tuple[UsageMetric, ...], *, start_day: date, end_day: date
    ) -> dict[UsageMetric, float]:
        """Cross-user sums per metric over [start_day, end_day)."""
        return await self._repo.rolled_totals(metrics, start_day=start_day, end_day=end_day)

    async def rolled_model_rows(self, *, start_day: date, end_day: date) -> list[LlmModelFact]:
        """Rolled (provider, model) aggregates over [start_day, end_day)."""
        return await self._repo.rolled_model_rows(start_day=start_day, end_day=end_day)

    async def rolled_task_rows(self, *, start_day: date, end_day: date) -> list[LlmTaskFact]:
        """Rolled per-task aggregates over [start_day, end_day)."""
        return await self._repo.rolled_task_rows(start_day=start_day, end_day=end_day)

    async def record_rejection(self, user_id: UUID, kind: QuotaKind, source: str) -> None:
        """Queue a rejection event on the caller's session (caller commits)."""
        self._repo.add_rejection(user_id, kind, source)
