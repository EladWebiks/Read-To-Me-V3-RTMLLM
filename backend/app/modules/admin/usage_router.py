"""Backoffice AI usage/cost routes. HTTP only; aggregates live in LlmService.

Reads are HYBRID (usage spec §7): closed days come from the usage rollup and
only TODAY is scanned raw, so a wide range costs a bounded number of rows.
`/executions` stays fully raw — it lists individual rows, not aggregates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.deps import get_db, require_admin
from app.modules.admin.params import PageParams, PeriodParams
from app.modules.admin.schemas import (
    AdminLlmExecutionRead,
    AdminUsageSummary,
    AdminUserUsageRead,
    Page,
)
from app.modules.downloads.service import DownloadService
from app.modules.imports.service import ImportService
from app.modules.llm.schemas import (
    AdminUsageOverview,
    ExecutionAdminFilters,
    LlmExecutionRead,
    ModelUsageRead,
    TaskUsageRead,
    UserUsageRead,
)
from app.modules.llm.service import LlmService
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.service import QuotaService
from app.modules.scraping.service import ScrapingService
from app.modules.usage.kinds import UsageMetric
from app.modules.usage.read_service import UsageReadService
from app.modules.users.schemas import UserRead
from app.modules.users.service import UserService

router = APIRouter(prefix="/usage")

_LLM_USER_METRICS: dict[str, UsageMetric] = {
    "tokens_in": UsageMetric.LLM_TOKENS_IN,
    "tokens_out": UsageMetric.LLM_TOKENS_OUT,
    "total_cost": UsageMetric.LLM_COST_USD,
    "execution_count": UsageMetric.LLM_EXECUTIONS,
}

# The today-tail sub-query is unpaginated: it must see every user active in
# the one-day overlap before the merged rows are sorted and sliced. 10_000 is
# far above any realistic count of users active in a single day.
_TAIL_USER_LIMIT = 10_000


def _llm(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LlmService:
    return LlmService(session, settings)


def _split_range(period: PeriodParams) -> tuple[date, date, datetime | None, datetime]:
    """(rolled_start_day, rolled_end_day, tail_start | None, tail_end).

    Rolled covers [from_day, min(to_day, today)); the raw tail covers the
    overlap of the range with [today 00:00 UTC, to) — None when the range
    ends before today.
    """
    today, today_start = UsageReadService.hybrid_split(datetime.now(UTC))
    rolled_start = period.period_start.astimezone(UTC).date()
    rolled_end = min(period.period_end.astimezone(UTC).date(), today)
    tail_start = max(period.period_start, today_start)
    if tail_start >= period.period_end:
        return rolled_start, rolled_end, None, period.period_end
    return rolled_start, rolled_end, tail_start, period.period_end


async def _merged_models(
    usage: UsageReadService,
    tail: AdminUsageOverview | None,
    *,
    start_day: date,
    end_day: date,
) -> list[ModelUsageRead]:
    """Rolled (provider, model) rows plus the live today tail, cost-desc."""
    merged: dict[tuple[str, str], ModelUsageRead] = {
        (m.provider, m.model): ModelUsageRead(
            provider=m.provider,
            model=m.model,
            tokens_in=m.tokens_in,
            tokens_out=m.tokens_out,
            total_cost=m.cost_usd,
            execution_count=m.executions,
        )
        for m in await usage.rolled_model_rows(start_day=start_day, end_day=end_day)
    }
    for row in tail.by_model if tail else []:
        base = merged.get((row.provider, row.model))
        merged[(row.provider, row.model)] = ModelUsageRead(
            provider=row.provider,
            model=row.model,
            tokens_in=row.tokens_in + (base.tokens_in if base else 0),
            tokens_out=row.tokens_out + (base.tokens_out if base else 0),
            total_cost=row.total_cost + (base.total_cost if base else 0.0),
            execution_count=row.execution_count + (base.execution_count if base else 0),
        )
    return sorted(merged.values(), key=lambda m: m.total_cost, reverse=True)


async def _merged_tasks(
    usage: UsageReadService,
    tail: AdminUsageOverview | None,
    *,
    start_day: date,
    end_day: date,
) -> list[TaskUsageRead]:
    """Rolled per-task rows plus the live today tail, cost-desc."""
    merged: dict[str, TaskUsageRead] = {
        t.task: TaskUsageRead(
            task=t.task,
            tokens_in=t.tokens_in,
            tokens_out=t.tokens_out,
            total_cost=t.cost_usd,
            execution_count=t.executions,
        )
        for t in await usage.rolled_task_rows(start_day=start_day, end_day=end_day)
    }
    for row in tail.by_task if tail else []:
        base = merged.get(row.task)
        merged[row.task] = TaskUsageRead(
            task=row.task,
            tokens_in=row.tokens_in + (base.tokens_in if base else 0),
            tokens_out=row.tokens_out + (base.tokens_out if base else 0),
            total_cost=row.total_cost + (base.total_cost if base else 0.0),
            execution_count=row.execution_count + (base.execution_count if base else 0),
        )
    return sorted(merged.values(), key=lambda t: t.total_cost, reverse=True)


async def _merged_overview(
    session: AsyncSession, service: LlmService, period: PeriodParams
) -> AdminUsageSummary:
    """Rolled closed-day totals + the live today tail, in the response shape."""
    rolled_start, rolled_end, tail_start, tail_end = _split_range(period)
    usage = UsageReadService(session)
    totals = await usage.rolled_totals(
        tuple(_LLM_USER_METRICS.values()), start_day=rolled_start, end_day=rolled_end
    )
    tail = (
        await service.usage_overview_admin(period_start=tail_start, period_end=tail_end)
        if tail_start is not None
        else None
    )
    rejections, by_kind = await usage.period_rejections(
        period_start=period.period_start,
        period_end=period.period_end,
        now=datetime.now(UTC),
    )
    days = {"start_day": rolled_start, "end_day": rolled_end}
    return AdminUsageSummary(
        period_start=period.period_start,
        period_end=period.period_end,
        tokens_in=int(totals.get(UsageMetric.LLM_TOKENS_IN, 0.0))
        + (tail.tokens_in if tail else 0),
        tokens_out=int(totals.get(UsageMetric.LLM_TOKENS_OUT, 0.0))
        + (tail.tokens_out if tail else 0),
        total_cost=totals.get(UsageMetric.LLM_COST_USD, 0.0) + (tail.total_cost if tail else 0.0),
        execution_count=int(totals.get(UsageMetric.LLM_EXECUTIONS, 0.0))
        + (tail.execution_count if tail else 0),
        by_model=await _merged_models(usage, tail, **days),
        by_task=await _merged_tasks(usage, tail, **days),
        rejections=rejections,
        rejections_by_kind=by_kind,
    )


async def _merged_user_rows(
    session: AsyncSession, service: LlmService, period: PeriodParams
) -> list[UserUsageRead]:
    """Rolled per-user LLM sums + live today tail, cost-desc."""
    rolled_start, rolled_end, tail_start, tail_end = _split_range(period)
    rolled = await UsageReadService(session).rolled_user_table(
        start_day=rolled_start, end_day=rolled_end
    )
    merged: dict[UUID, dict[str, float]] = {
        uid: {field: metrics.get(m, 0.0) for field, m in _LLM_USER_METRICS.items()}
        for uid, metrics in rolled.items()
    }
    if tail_start is not None:
        tail_rows, _ = await service.usage_by_user_admin(
            period_start=tail_start,
            period_end=tail_end,
            limit=_TAIL_USER_LIMIT,
            offset=0,
        )
        for row in tail_rows:
            entry = merged.setdefault(row.user_id, dict.fromkeys(_LLM_USER_METRICS, 0.0))
            entry["tokens_in"] += row.tokens_in
            entry["tokens_out"] += row.tokens_out
            entry["total_cost"] += row.total_cost
            entry["execution_count"] += row.execution_count
    rows = [
        UserUsageRead(
            user_id=uid,
            tokens_in=int(value["tokens_in"]),
            tokens_out=int(value["tokens_out"]),
            total_cost=value["total_cost"],
            execution_count=int(value["execution_count"]),
        )
        for uid, value in merged.items()
    ]
    rows.sort(key=lambda r: r.total_cost, reverse=True)
    return rows


@router.get("/summary")
async def usage_summary(
    period: Annotated[PeriodParams, Depends()],
    _admin: Annotated[UserRead, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[LlmService, Depends(_llm)],
) -> AdminUsageSummary:
    """Global tokens/cost/executions with model, task and rejection breakdowns."""
    return await _merged_overview(session, service, period)


@router.get("/by-user")
async def usage_by_user(
    period: Annotated[PeriodParams, Depends()],
    page: Annotated[PageParams, Depends()],
    _admin: Annotated[UserRead, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[LlmService, Depends(_llm)],
) -> Page[AdminUserUsageRead]:
    """Per-user usage rows + membership, current-month usage, and LLM quota.

    Pagination happens in Python over the merged rows: the set is bounded by
    users *active in the range*, not by history length.
    """
    rows = await _merged_user_rows(session, service, period)
    total = len(rows)
    page_rows = rows[page.offset : page.offset + page.limit]
    items = await _decorate_rows(session, service, page_rows, period)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@dataclass(frozen=True)
class _MonthLookups:
    """Current-month values, hybrid: rolled closed days + today's raw tails."""

    rolled: dict[UUID, dict[UsageMetric, float]]
    tail_llm: dict[UUID, UserUsageRead]
    audio: dict[UUID, int]
    scrape: dict[UUID, int]
    imports: dict[UUID, int]


@dataclass(frozen=True)
class _RowContext:
    """Per-request lookup tables for decorating by-user rows."""

    names: dict[UUID, str]
    tiers: dict[UUID, str]
    quotas: dict[tuple[str, str], float]
    months: _MonthLookups
    rejections: dict[UUID, int]


async def _month_lookups(
    session: AsyncSession, service: LlmService, ids: list[UUID]
) -> _MonthLookups:
    """Hybrid month values: rolled closed days + today tails (usage spec §7)."""
    now = datetime.now(UTC)
    month_start, month_end = QuotaService.current_month_window(now)
    today, today_start = UsageReadService.hybrid_split(now)
    rolled: dict[UUID, dict[UsageMetric, float]] = {}
    if month_start.date() < today:
        wanted = set(ids)
        table = await UsageReadService(session).rolled_user_table(
            start_day=month_start.date(), end_day=today
        )
        rolled = {uid: metrics for uid, metrics in table.items() if uid in wanted}
    window = {"period_start": today_start, "period_end": month_end}
    return _MonthLookups(
        rolled=rolled,
        tail_llm=await service.usage_for_users_admin(ids, **window),
        audio=await DownloadService(session).month_chapters_for_users(ids, **window),
        scrape=await ScrapingService(session).month_chapters_for_users(ids, **window),
        imports=await ImportService(session).month_imports_for_users(ids, **window),
    )


def _month_tokens(lookups: _MonthLookups, uid: UUID) -> int:
    metrics = lookups.rolled.get(uid, {})
    rolled = metrics.get(UsageMetric.LLM_TOKENS_IN, 0.0) + metrics.get(
        UsageMetric.LLM_TOKENS_OUT, 0.0
    )
    tail = lookups.tail_llm.get(uid)
    return int(rolled) + ((tail.tokens_in + tail.tokens_out) if tail else 0)


def _month_cost(lookups: _MonthLookups, uid: UUID) -> float:
    rolled = lookups.rolled.get(uid, {}).get(UsageMetric.LLM_COST_USD, 0.0)
    tail = lookups.tail_llm.get(uid)
    return rolled + (tail.total_cost if tail else 0.0)


def _month_metric(
    lookups: _MonthLookups, uid: UUID, metric: UsageMetric, tail: dict[UUID, int]
) -> int:
    return int(lookups.rolled.get(uid, {}).get(metric, 0.0)) + tail.get(uid, 0)


async def _decorate_rows(
    session: AsyncSession,
    service: LlmService,
    rows: list[UserUsageRead],
    period: PeriodParams,
) -> list[AdminUserUsageRead]:
    """Join usernames, tiers, current-month usage, job counts, and quota rules."""
    users = UserService(session)
    ids = [row.user_id for row in rows]
    ctx = _RowContext(
        names=await users.usernames_for_ids(ids),
        tiers=await users.memberships_for_ids(ids),
        quotas={
            (q.membership, q.quota_kind): q.limit_value
            for q in await QuotaService(session).list_quotas()
        },
        months=await _month_lookups(session, service, ids),
        rejections=await UsageReadService(session).period_rejections_by_user(
            period_start=period.period_start,
            period_end=period.period_end,
            now=datetime.now(UTC),
        ),
    )
    return [_decorated_row(row, ctx) for row in rows]


def _decorated_row(row: UserUsageRead, ctx: _RowContext) -> AdminUserUsageRead:
    tier_value = ctx.tiers.get(row.user_id)
    uid = row.user_id
    months = ctx.months
    return AdminUserUsageRead(
        username=ctx.names.get(uid),
        membership=tier_value,
        month_tokens=_month_tokens(months, uid),
        month_cost=_month_cost(months, uid),
        llm_tokens_limit=ctx.quotas.get((tier_value or "", QuotaKind.LLM_TOKENS.value)),
        llm_cost_limit=ctx.quotas.get((tier_value or "", QuotaKind.LLM_COST_USD.value)),
        month_audio_chapters=_month_metric(months, uid, UsageMetric.AUDIO_CHAPTERS, months.audio),
        month_scrape_chapters=_month_metric(
            months, uid, UsageMetric.SCRAPE_CHAPTERS, months.scrape
        ),
        month_epub_imports=_month_metric(months, uid, UsageMetric.EPUB_IMPORTS, months.imports),
        period_rejections=ctx.rejections.get(uid, 0),
        **row.model_dump(),
    )


@dataclass(frozen=True, slots=True)
class _ExecutionQuery:
    """Raw query params for /executions before username resolution."""

    q: str | None = None
    user_id: UUID | None = None
    task: str | None = None
    status: str | None = None


def _execution_query(
    q: Annotated[str | None, Query(max_length=128)] = None,
    user_id: UUID | None = None,
    task: Annotated[str | None, Query(max_length=64)] = None,
    status: Annotated[str | None, Query(max_length=32)] = None,
) -> _ExecutionQuery:
    return _ExecutionQuery(q=q, user_id=user_id, task=task or None, status=status or None)


async def _execution_filters(
    session: AsyncSession, query: _ExecutionQuery
) -> ExecutionAdminFilters:
    """Resolve username search + optional exact user_id into ExecutionAdminFilters."""
    return ExecutionAdminFilters(
        user_ids=await _resolve_execution_user_ids(session, query),
        task=query.task,
        status=query.status,
    )


async def _resolve_execution_user_ids(
    session: AsyncSession, query: _ExecutionQuery
) -> list[UUID] | None:
    """None = no user filter; empty = match nothing; else IN (...)."""
    if not query.q and query.user_id is None:
        return None
    if not query.q:
        return [query.user_id] if query.user_id is not None else None
    matched = await UserService(session).ids_matching_q(query.q.strip())
    if query.user_id is None:
        return matched
    return [query.user_id] if query.user_id in matched else []


async def _decorate_executions(
    session: AsyncSession, items: list[LlmExecutionRead]
) -> list[AdminLlmExecutionRead]:
    names = await UserService(session).usernames_for_ids([row.user_id for row in items])
    return [
        AdminLlmExecutionRead(username=names.get(row.user_id), **row.model_dump()) for row in items
    ]


@router.get("/executions")
async def recent_executions(
    period: Annotated[PeriodParams, Depends()],
    page: Annotated[PageParams, Depends()],
    query: Annotated[_ExecutionQuery, Depends(_execution_query)],
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[LlmService, Depends(_llm)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Page[AdminLlmExecutionRead]:
    """Cross-user execution rows, newest first, with optional filters."""
    filters = await _execution_filters(session, query)
    items, total = await service.list_executions_admin(
        filters,
        period_start=period.period_start,
        period_end=period.period_end,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(
        items=await _decorate_executions(session, items),
        total=total,
        limit=page.limit,
        offset=page.offset,
    )
