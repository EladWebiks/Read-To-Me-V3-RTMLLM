"""DB access for the usage module's tables only."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.quotas.kinds import QuotaKind
from app.modules.usage.kinds import (
    REJECTION_METRICS,
    LlmModelFact,
    LlmTaskFact,
    UsageFact,
    UsageMetric,
)
from app.modules.usage.models import (
    LlmModelDaily,
    LlmTaskDaily,
    QuotaRejection,
    UsageDaily,
)


def day_window(day: date) -> tuple[datetime, datetime]:
    """[day 00:00 UTC, next day 00:00 UTC) — shared by fact queries."""
    start = datetime.combine(day, time(), tzinfo=UTC)
    return start, start + timedelta(days=1)


class UsageRepository:
    """Reads and idempotent per-day writes over the rollup tables."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_day(self, day: date, facts: Sequence[UsageFact]) -> None:
        """Idempotent per-day rebuild: delete the day, insert non-zero facts."""
        await self._session.execute(delete(UsageDaily).where(UsageDaily.day == day))
        for fact in facts:
            if fact.amount == 0:
                continue  # sparse: zero rows are omitted (spec §4.2)
            self._session.add(
                UsageDaily(
                    user_id=fact.user_id,
                    day=day,
                    metric=fact.metric.value,
                    amount=fact.amount,
                )
            )
        await self._session.flush()

    async def replace_llm_day(
        self,
        day: date,
        model_rows: Sequence[LlmModelFact],
        task_rows: Sequence[LlmTaskFact],
    ) -> None:
        """Idempotent per-day rebuild of the cross-user LLM breakdowns."""
        await self._session.execute(delete(LlmModelDaily).where(LlmModelDaily.day == day))
        await self._session.execute(delete(LlmTaskDaily).where(LlmTaskDaily.day == day))
        for row in model_rows:
            self._session.add(
                LlmModelDaily(
                    day=day,
                    provider=row.provider,
                    model=row.model,
                    tokens_in=row.tokens_in,
                    tokens_out=row.tokens_out,
                    cost_usd=row.cost_usd,
                    executions=row.executions,
                )
            )
        for trow in task_rows:
            self._session.add(
                LlmTaskDaily(
                    day=day,
                    task=trow.task,
                    tokens_in=trow.tokens_in,
                    tokens_out=trow.tokens_out,
                    cost_usd=trow.cost_usd,
                    executions=trow.executions,
                )
            )
        await self._session.flush()

    async def rolled_amount(
        self,
        user_id: UUID,
        metrics: Sequence[UsageMetric],
        *,
        start_day: date,
        end_day: date,
    ) -> float:
        """Sum over [start_day, end_day) for one user."""
        stmt = select(func.coalesce(func.sum(UsageDaily.amount), 0.0)).where(
            UsageDaily.user_id == user_id,
            UsageDaily.metric.in_([m.value for m in metrics]),
            UsageDaily.day >= start_day,
            UsageDaily.day < end_day,
        )
        return float((await self._session.execute(stmt)).scalar_one())

    async def rolled_user_table(
        self, *, start_day: date, end_day: date
    ) -> dict[UUID, dict[UsageMetric, float]]:
        """Per-user metric sums over [start_day, end_day) — admin by-user."""
        stmt = (
            select(UsageDaily.user_id, UsageDaily.metric, func.sum(UsageDaily.amount))
            .where(UsageDaily.day >= start_day, UsageDaily.day < end_day)
            .group_by(UsageDaily.user_id, UsageDaily.metric)
        )
        table: dict[UUID, dict[UsageMetric, float]] = {}
        for user_id, metric, amount in (await self._session.execute(stmt)).all():
            try:
                key = UsageMetric(metric)
            except ValueError:
                continue  # row from a retired metric: skip, never crash
            table.setdefault(user_id, {})[key] = float(amount)
        return table

    async def rolled_totals(
        self, metrics: Sequence[UsageMetric], *, start_day: date, end_day: date
    ) -> dict[UsageMetric, float]:
        """Cross-user sums per metric over [start_day, end_day)."""
        stmt = (
            select(UsageDaily.metric, func.sum(UsageDaily.amount))
            .where(
                UsageDaily.metric.in_([m.value for m in metrics]),
                UsageDaily.day >= start_day,
                UsageDaily.day < end_day,
            )
            .group_by(UsageDaily.metric)
        )
        rows = (await self._session.execute(stmt)).all()
        return {UsageMetric(metric): float(amount) for metric, amount in rows}

    async def rolled_model_rows(self, *, start_day: date, end_day: date) -> list[LlmModelFact]:
        """Rolled (provider, model) aggregates over [start_day, end_day)."""
        stmt = (
            select(
                LlmModelDaily.provider,
                LlmModelDaily.model,
                func.sum(LlmModelDaily.tokens_in),
                func.sum(LlmModelDaily.tokens_out),
                func.sum(LlmModelDaily.cost_usd),
                func.sum(LlmModelDaily.executions),
            )
            .where(LlmModelDaily.day >= start_day, LlmModelDaily.day < end_day)
            .group_by(LlmModelDaily.provider, LlmModelDaily.model)
        )
        return [
            LlmModelFact(r[0], r[1], int(r[2]), int(r[3]), float(r[4]), int(r[5]))
            for r in (await self._session.execute(stmt)).all()
        ]

    async def rolled_task_rows(self, *, start_day: date, end_day: date) -> list[LlmTaskFact]:
        """Rolled per-task aggregates over [start_day, end_day)."""
        stmt = (
            select(
                LlmTaskDaily.task,
                func.sum(LlmTaskDaily.tokens_in),
                func.sum(LlmTaskDaily.tokens_out),
                func.sum(LlmTaskDaily.cost_usd),
                func.sum(LlmTaskDaily.executions),
            )
            .where(LlmTaskDaily.day >= start_day, LlmTaskDaily.day < end_day)
            .group_by(LlmTaskDaily.task)
        )
        return [
            LlmTaskFact(r[0], int(r[1]), int(r[2]), float(r[3]), int(r[4]))
            for r in (await self._session.execute(stmt)).all()
        ]

    def add_rejection(self, user_id: UUID, kind: QuotaKind, source: str) -> None:
        """Queue a rejection event on the caller's session (caller commits)."""
        self._session.add(QuotaRejection(user_id=user_id, quota_kind=kind.value, source=source))

    async def rejection_counts(self, *, start: datetime, end: datetime) -> dict[str, int]:
        """Raw quota_rejections per kind for [start, end) — the today-tail."""
        stmt = (
            select(QuotaRejection.quota_kind, func.count())
            .where(QuotaRejection.created_at >= start, QuotaRejection.created_at < end)
            .group_by(QuotaRejection.quota_kind)
        )
        rows = (await self._session.execute(stmt)).all()
        return {str(row[0]): int(row[1]) for row in rows}

    async def rejection_counts_by_user(self, *, start: datetime, end: datetime) -> dict[UUID, int]:
        """Raw quota_rejections per user for [start, end) — the today-tail."""
        stmt = (
            select(QuotaRejection.user_id, func.count())
            .where(QuotaRejection.created_at >= start, QuotaRejection.created_at < end)
            .group_by(QuotaRejection.user_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return {row[0]: int(row[1]) for row in rows}

    async def rejection_facts(self, day: date) -> list[UsageFact]:
        """Roll this module's own raw events into rejected_* facts."""
        start, end = day_window(day)
        stmt = (
            select(
                QuotaRejection.user_id,
                QuotaRejection.quota_kind,
                func.count(QuotaRejection.id),
            )
            .where(QuotaRejection.created_at >= start, QuotaRejection.created_at < end)
            .group_by(QuotaRejection.user_id, QuotaRejection.quota_kind)
        )
        facts: list[UsageFact] = []
        for user_id, kind_raw, count in (await self._session.execute(stmt)).all():
            try:
                metric = REJECTION_METRICS[QuotaKind(kind_raw)]
            except ValueError:
                continue  # row from a retired quota kind: skip, never crash
            facts.append(UsageFact(user_id, metric, float(count)))
        return facts
