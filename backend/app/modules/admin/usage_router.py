"""Backoffice AI usage/cost routes. HTTP only; aggregates live in LlmService."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.deps import get_db, require_admin
from app.modules.admin.params import PageParams, PeriodParams
from app.modules.admin.schemas import AdminUserUsageRead, Page
from app.modules.llm.schemas import AdminUsageOverview, LlmExecutionRead
from app.modules.llm.service import LlmService
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
    """Per-user usage rows with usernames resolved via the users service."""
    rows, total = await service.usage_by_user_admin(
        period_start=period.period_start,
        period_end=period.period_end,
        limit=page.limit,
        offset=page.offset,
    )
    names = await UserService(session).usernames_for_ids([row.user_id for row in rows])
    items = [
        AdminUserUsageRead(username=names.get(row.user_id), **row.model_dump()) for row in rows
    ]
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


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
