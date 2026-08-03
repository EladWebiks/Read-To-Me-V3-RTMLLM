"""Backoffice tool-call audit routes. HTTP only; logic in LlmService."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.deps import get_db, require_admin
from app.modules.admin.params import PageParams
from app.modules.admin.schemas import AdminToolCallRead, Page
from app.modules.llm.schemas import ToolCallAdminFilters, ToolCallAdminRead
from app.modules.llm.service import LlmService
from app.modules.users.schemas import UserRead
from app.modules.users.service import UserService

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
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Page[AdminToolCallRead]:
    """Cross-user tool_call audit rows, newest first."""
    items, total = await service.list_tool_calls_admin(
        filters, limit=page.limit, offset=page.offset
    )
    return Page(
        items=await _decorate_tool_calls(session, items),
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


async def _decorate_tool_calls(
    session: AsyncSession, items: list[ToolCallAdminRead]
) -> list[AdminToolCallRead]:
    ids = [row.user_id for row in items if row.user_id is not None]
    identities = await UserService(session).identities_for_ids(ids)
    decorated: list[AdminToolCallRead] = []
    for row in items:
        username, email = (None, None)
        if row.user_id is not None:
            identity = identities.get(row.user_id)
            if identity is not None:
                username, email = identity
        decorated.append(AdminToolCallRead(username=username, email=email, **row.model_dump()))
    return decorated
