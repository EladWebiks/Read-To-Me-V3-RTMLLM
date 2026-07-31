"""Admin CRUD for quota rules. Set/clear pattern mirrors runtime_config."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_admin
from app.modules.quotas.kinds import KIND_REGISTRY, QuotaKind
from app.modules.quotas.schemas import (
    MembershipQuotaRead,
    MembershipQuotasResponse,
    QuotaKindInfo,
    QuotaLimitWrite,
)
from app.modules.quotas.service import QuotaService
from app.modules.users.membership import Membership
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
    membership: Membership,
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
    membership: Membership,
    kind: QuotaKind,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[QuotaService, Depends(_service)],
) -> None:
    """Remove one rule; that (membership, kind) becomes unlimited again."""
    await service.clear_quota(membership, kind, actor_id=admin.id)
