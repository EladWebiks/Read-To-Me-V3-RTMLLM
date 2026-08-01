"""Backoffice tool-call audit routes. HTTP only; logic in LlmService."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.deps import get_db, require_admin
from app.modules.admin.params import PageParams
from app.modules.admin.schemas import Page
from app.modules.llm.schemas import ToolCallAdminFilters, ToolCallAdminRead
from app.modules.llm.service import LlmService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/tool-calls")


def _llm(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LlmService:
    return LlmService(session, settings)


def _filters(
    tool_name: str | None = None,
    status: str | None = None,
    risk_level: str | None = None,
    period_start: Annotated[datetime | None, Query(alias="from")] = None,
    period_end: Annotated[datetime | None, Query(alias="to")] = None,
) -> ToolCallAdminFilters:
    return ToolCallAdminFilters(
        tool_name=tool_name,
        status=status,
        risk_level=risk_level,
        period_start=period_start,
        period_end=period_end,
    )


@router.get("")
async def list_tool_calls(
    filters: Annotated[ToolCallAdminFilters, Depends(_filters)],
    page: Annotated[PageParams, Depends()],
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[LlmService, Depends(_llm)],
) -> Page[ToolCallAdminRead]:
    """Cross-user tool_call audit rows, newest first."""
    items, total = await service.list_tool_calls_admin(
        filters, limit=page.limit, offset=page.offset
    )
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)
