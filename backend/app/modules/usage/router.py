"""Self-serve usage endpoint. Identity comes from the session cookie ONLY."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.deps import get_current_user, get_db
from app.modules.usage.schemas import MeUsageResponse
from app.modules.usage.self_service import SelfUsageService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/me", tags=["usage"])


@router.get("/usage")
async def my_usage(
    user: Annotated[UserRead, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MeUsageResponse:
    """Tier + per-kind hybrid usage vs limits for the authenticated user."""
    return await SelfUsageService(session, settings).usage_for(user)
