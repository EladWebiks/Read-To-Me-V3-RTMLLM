"""Admin CRUD for quota rules. Set/clear pattern mirrors runtime_config.

Two routers: tier rules under /admin/membership-quotas and per-user
overrides under /admin/users/{user_id}/quotas (an override wins over the
tier rule for its kind, looser or tighter).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_admin
from app.modules.quotas.kinds import KIND_REGISTRY, QuotaKind
from app.modules.quotas.schemas import (
    MembershipQuotaRead,
    MembershipQuotasResponse,
    QuotaKindInfo,
    QuotaLimitWrite,
    UserQuotaOverrideRead,
    UserQuotasResponse,
)
from app.modules.quotas.service import QuotaService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/admin/membership-quotas", tags=["admin"])


def _service(session: Annotated[AsyncSession, Depends(get_db)]) -> QuotaService:
    return QuotaService(session)


@router.get("")
async def list_quotas(
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[QuotaService, Depends(_service)],
) -> MembershipQuotasResponse:
    """Kind registry + every configured rule (absent pair = unlimited)."""
    rows = await service.list_quotas()
    return MembershipQuotasResponse(
        kinds=[
            QuotaKindInfo(kind=kind, label=m.label, unit=m.unit, window=m.window)
            for kind, m in KIND_REGISTRY.items()
        ],
        quotas=[MembershipQuotaRead.model_validate(row) for row in rows],
    )


@router.put("/{membership}/{kind}")
async def put_quota(
    membership: str,
    kind: QuotaKind,
    body: QuotaLimitWrite,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[QuotaService, Depends(_service)],
) -> MembershipQuotaRead:
    """Set or replace one quota rule."""
    row = await service.set_quota(membership, kind, body.limit_value, actor_id=admin.id)
    return MembershipQuotaRead.model_validate(row)


@router.delete("/{membership}/{kind}", status_code=204)
async def delete_quota(
    membership: str,
    kind: QuotaKind,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[QuotaService, Depends(_service)],
) -> None:
    """Remove one rule; that (membership, kind) becomes unlimited again."""
    await service.clear_quota(membership, kind, actor_id=admin.id)


user_router = APIRouter(prefix="/admin/users", tags=["admin"])


@user_router.get("/{user_id}/quotas")
async def get_user_quotas(
    user_id: UUID,
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[QuotaService, Depends(_service)],
) -> UserQuotasResponse:
    """Registry + tier limits + this user's override rows."""
    membership, tier_limits, overrides = await service.user_quotas(user_id)
    return UserQuotasResponse(
        membership=membership,
        kinds=[
            QuotaKindInfo(kind=kind, label=m.label, unit=m.unit, window=m.window)
            for kind, m in KIND_REGISTRY.items()
        ],
        tier_limits=tier_limits,
        overrides=[UserQuotaOverrideRead.model_validate(row) for row in overrides],
    )


@user_router.put("/{user_id}/quotas/{kind}")
async def put_user_quota(
    user_id: UUID,
    kind: QuotaKind,
    body: QuotaLimitWrite,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[QuotaService, Depends(_service)],
) -> UserQuotaOverrideRead:
    """Set or replace this user's override for one kind."""
    row = await service.set_user_quota(user_id, kind, body.limit_value, actor_id=admin.id)
    return UserQuotaOverrideRead.model_validate(row)


@user_router.delete("/{user_id}/quotas/{kind}", status_code=204)
async def delete_user_quota(
    user_id: UUID,
    kind: QuotaKind,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[QuotaService, Depends(_service)],
) -> None:
    """Drop this user's override; their tier limit applies again."""
    await service.clear_user_quota(user_id, kind, actor_id=admin.id)
