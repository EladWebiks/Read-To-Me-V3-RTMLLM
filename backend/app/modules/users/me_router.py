"""Self-serve membership routes. Identity comes from the session cookie ONLY.

The switch endpoint exists for manual testing pre-Stripe; the runtime flag
membership.self_switch_enabled (runtime-config tunable) turns it off without
a redeploy once real billing owns tier changes.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.deps import get_current_user, get_db, get_effective_settings
from app.modules.auth.exceptions import NotAuthorizedError
from app.modules.users.membership_service import MembershipService
from app.modules.users.schemas import MembershipSwitch, PlansResponse, UserRead

router = APIRouter(prefix="/me", tags=["users"])


@router.get("/plans")
async def my_plans(
    user: Annotated[UserRead, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_effective_settings)],
) -> PlansResponse:
    """Active tiers (rank order) + whether self-switching is enabled."""
    plans = await MembershipService(session).active_plans(user.membership)
    return PlansResponse(plans=plans, can_switch=settings.membership.self_switch_enabled)


@router.post("/membership")
async def switch_membership(
    body: MembershipSwitch,
    user: Annotated[UserRead, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_effective_settings)],
) -> UserRead:
    """Flag-gated manual tier switch (403 when disabled)."""
    if not settings.membership.self_switch_enabled:
        raise NotAuthorizedError
    return await MembershipService(session).switch_user(user.id, body.membership)
