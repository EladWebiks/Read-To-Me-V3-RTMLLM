"""Rolled reads + rejection recording. Imports NO domain modules.

Hybrid rule (spec §7): closed days come from usage_daily; TODAY is always
read live from raw tables by the CALLER (each domain's existing meter with a
today window) — that one-directional split is what keeps domain -> usage
imports cycle-free. rollup.py is the only usage file importing domains.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.service import QuotaService
from app.modules.usage.kinds import (
    KIND_METRICS,
    REJECTION_METRICS,
    LlmModelFact,
    LlmTaskFact,
    UsageMetric,
)
from app.modules.usage.repository import UsageRepository

logger = logging.getLogger(__name__)


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

    async def period_rejections(
        self, *, period_start: datetime, period_end: datetime, now: datetime
    ) -> tuple[int, dict[str, int]]:
        """Hybrid rejection counts for an arbitrary [from, to) period.

        Rolled rejected_* rows cover [start_day, min(end_day, today));
        raw quota_rejections cover [max(period_start, today_start), period_end).
        Same range split as the admin aggregates.
        """
        today, today_start = self.hybrid_split(now)
        by_kind: dict[str, int] = {}
        rolled_end = min(period_end.astimezone(UTC).date(), today)
        start_day = period_start.astimezone(UTC).date()
        if start_day < rolled_end:
            metric_to_kind = {m: k for k, m in REJECTION_METRICS.items()}
            totals = await self._repo.rolled_totals(
                tuple(REJECTION_METRICS.values()), start_day=start_day, end_day=rolled_end
            )
            for metric, amount in totals.items():
                by_kind[metric_to_kind[metric].value] = int(amount)
        raw_start = max(period_start, today_start)
        if raw_start < period_end:
            counts = await self._repo.rejection_counts(start=raw_start, end=period_end)
            for kind, count in counts.items():
                by_kind[kind] = by_kind.get(kind, 0) + count
        return sum(by_kind.values()), by_kind

    async def period_rejections_by_user(
        self, *, period_start: datetime, period_end: datetime, now: datetime
    ) -> dict[UUID, int]:
        """Per-user hybrid rejection totals for an arbitrary [from, to) period."""
        today, today_start = self.hybrid_split(now)
        result: dict[UUID, int] = {}
        rolled_end = min(period_end.astimezone(UTC).date(), today)
        start_day = period_start.astimezone(UTC).date()
        if start_day < rolled_end:
            rejection_metrics = set(REJECTION_METRICS.values())
            table = await self._repo.rolled_user_table(start_day=start_day, end_day=rolled_end)
            for user_id, metrics in table.items():
                amount = sum(v for m, v in metrics.items() if m in rejection_metrics)
                if amount:
                    result[user_id] = int(amount)
        raw_start = max(period_start, today_start)
        if raw_start < period_end:
            counts = await self._repo.rejection_counts_by_user(start=raw_start, end=period_end)
            for user_id, count in counts.items():
                result[user_id] = result.get(user_id, 0) + count
        return result

    async def record_rejection(self, user_id: UUID, kind: QuotaKind, source: str) -> None:
        """Queue a rejection event on the caller's session (caller commits)."""
        self._repo.add_rejection(user_id, kind, source)


async def record_rejection_detached(user_id: UUID | None, kind: QuotaKind, source: str) -> None:
    """Write a rejection event in its OWN transaction (429 handler path).

    The request transaction rolls back when QuotaExceededError propagates,
    so the handler cannot use the request session. Best-effort: a failure
    here must never break the 429 response.
    """
    if user_id is None:
        return
    try:
        async with SessionLocal() as session:
            UsageRepository(session).add_rejection(user_id, kind, source)
            await session.commit()
    except Exception:
        logger.warning(
            "failed to record quota rejection",
            extra={"user_id": str(user_id), "kind": kind.value},
        )
