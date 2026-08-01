"""Backoffice membership tier routes. HTTP only; logic in MembershipService.

Composition: tier creation also ensures the orchestration policy row exists
(same request transaction) so the new tier appears on the policies screen
immediately — router-layer composition, no service-to-service import cycle.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.deps import get_db, get_effective_settings, require_admin
from app.modules.orchestration.policy import PolicyService
from app.modules.users.membership_service import MembershipService
from app.modules.users.schemas import (
    MembershipAdminRead,
    MembershipCreate,
    MembershipDeactivate,
    MembershipPatch,
    MembershipsResponse,
    UserRead,
)

router = APIRouter(prefix="/memberships")


def _service(session: Annotated[AsyncSession, Depends(get_db)]) -> MembershipService:
    return MembershipService(session)


@router.get("")
async def list_memberships(
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[MembershipService, Depends(_service)],
) -> MembershipsResponse:
    """Every tier (active and inactive) with live user counts, rank order."""
    return MembershipsResponse(memberships=await service.list_tiers())


@router.post("")
async def create_membership(
    body: MembershipCreate,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[MembershipService, Depends(_service)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_effective_settings)],
) -> MembershipAdminRead:
    """Create a tier; also seeds its all-NULL per-turn policy row."""
    tier = await service.create_tier(body, actor_id=admin.id)
    await PolicyService(session, settings).ensure_row(tier.slug)
    return MembershipAdminRead.from_tier(tier, 0)


@router.patch("/{slug}")
async def patch_membership(
    slug: str,
    body: MembershipPatch,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[MembershipService, Depends(_service)],
) -> MembershipAdminRead:
    """Edit presentation/rank/default, or reactivate. Slug is immutable."""
    tier = await service.update_tier(slug, body, actor_id=admin.id)
    counts = await service.list_tiers()
    count = next((t.user_count for t in counts if t.slug == slug), 0)
    return MembershipAdminRead.from_tier(tier, count)


@router.post("/{slug}/deactivate")
async def deactivate_membership(
    slug: str,
    body: MembershipDeactivate,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[MembershipService, Depends(_service)],
) -> MembershipAdminRead:
    """Migrate every user to body.migrate_to, then deactivate. One transaction."""
    tier, _moved = await service.deactivate_tier(slug, body.migrate_to, actor_id=admin.id)
    return MembershipAdminRead.from_tier(tier, 0)
