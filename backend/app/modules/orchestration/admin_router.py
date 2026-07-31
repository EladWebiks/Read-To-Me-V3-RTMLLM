"""Admin CRUD for membership AI policies. HTTP only; logic in PolicyService.

PATCH-only by design: rows mirror the Membership enum (no create/delete).
Follows the runtime_config admin router pattern.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.deps import get_db, get_effective_settings, require_admin
from app.modules.orchestration.policy import PolicyService
from app.modules.orchestration.schemas import (
    MembershipPoliciesResponse,
    MembershipPolicyPatch,
    MembershipPolicyRead,
)
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/admin/membership-policies", tags=["admin"])


def _service(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_effective_settings)],
) -> PolicyService:
    return PolicyService(session, settings)


@router.get("")
async def list_policies(
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[PolicyService, Depends(_service)],
) -> MembershipPoliciesResponse:
    """Every tier row plus the current inherited (effective) defaults."""
    rows = await service.list_policies()
    return MembershipPoliciesResponse(
        policies=[MembershipPolicyRead.model_validate(row) for row in rows],
        inherited=service.inherited_defaults(),
    )


@router.patch("/{membership}")
async def patch_policy(
    membership: Membership,
    body: MembershipPolicyPatch,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[PolicyService, Depends(_service)],
) -> MembershipPolicyRead:
    """Update one tier; omitted fields unchanged, explicit null clears."""
    row = await service.patch_policy(membership, body, actor_id=admin.id)
    return MembershipPolicyRead.model_validate(row)
