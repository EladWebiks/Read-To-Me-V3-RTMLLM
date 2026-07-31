"""Backoffice AI usage/cost routes. HTTP only; aggregates live in LlmService."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.deps import get_db, require_admin
from app.modules.admin.params import PageParams, PeriodParams
from app.modules.admin.schemas import AdminUserUsageRead, Page
from app.modules.llm.schemas import AdminUsageOverview, LlmExecutionRead, UserUsageRead
from app.modules.llm.service import LlmService
from app.modules.quotas.kinds import QuotaKind
from app.modules.quotas.service import QuotaService
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserRead
from app.modules.users.service import UserService

router = APIRouter(prefix="/usage")


def _llm(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LlmService:
    return LlmService(session, settings)


@router.get("/summary")
async def usage_summary(
    period: Annotated[PeriodParams, Depends()],
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[LlmService, Depends(_llm)],
) -> AdminUsageOverview:
    """Global tokens/cost/executions with model and task breakdowns."""
    return await service.usage_overview_admin(
        period_start=period.period_start, period_end=period.period_end
    )


@router.get("/by-user")
async def usage_by_user(
    period: Annotated[PeriodParams, Depends()],
    page: Annotated[PageParams, Depends()],
    _admin: Annotated[UserRead, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[LlmService, Depends(_llm)],
) -> Page[AdminUserUsageRead]:
    """Per-user usage rows + membership, current-month usage, and LLM quota."""
    rows, total = await service.usage_by_user_admin(
        period_start=period.period_start,
        period_end=period.period_end,
        limit=page.limit,
        offset=page.offset,
    )
    items = await _decorate_rows(session, service, rows)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


async def _decorate_rows(
    session: AsyncSession,
    service: LlmService,
    rows: list[UserUsageRead],
) -> list[AdminUserUsageRead]:
    """Join usernames, tiers, current-month usage, and LLM quota rules."""
    users = UserService(session)
    ids = [row.user_id for row in rows]
    names = await users.usernames_for_ids(ids)
    tiers = await users.memberships_for_ids(ids)
    month_start, month_end = QuotaService.current_month_window(datetime.now(UTC))
    month = await service.usage_for_users_admin(
        ids, period_start=month_start, period_end=month_end
    )
    quotas: dict[tuple[str, str], float] = {
        (q.membership, q.quota_kind): q.limit_value
        for q in await QuotaService(session).list_quotas()
    }
    return [_decorated_row(row, names, tiers, month, quotas) for row in rows]


def _decorated_row(
    row: UserUsageRead,
    names: dict[UUID, str],
    tiers: dict[UUID, Membership],
    month: dict[UUID, UserUsageRead],
    quotas: dict[tuple[str, str], float],
) -> AdminUserUsageRead:
    tier = tiers.get(row.user_id)
    tier_value = tier.value if tier is not None else None
    month_row = month.get(row.user_id)
    return AdminUserUsageRead(
        username=names.get(row.user_id),
        membership=tier_value,
        month_tokens=(month_row.tokens_in + month_row.tokens_out) if month_row else 0,
        month_cost=month_row.total_cost if month_row else 0.0,
        llm_tokens_limit=quotas.get((tier_value or "", QuotaKind.LLM_TOKENS.value)),
        llm_cost_limit=quotas.get((tier_value or "", QuotaKind.LLM_COST_USD.value)),
        **row.model_dump(),
    )


@router.get("/executions")
async def recent_executions(
    period: Annotated[PeriodParams, Depends()],
    page: Annotated[PageParams, Depends()],
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[LlmService, Depends(_llm)],
) -> Page[LlmExecutionRead]:
    """Cross-user execution rows, newest first."""
    items, total = await service.list_executions_admin(
        period_start=period.period_start,
        period_end=period.period_end,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)
