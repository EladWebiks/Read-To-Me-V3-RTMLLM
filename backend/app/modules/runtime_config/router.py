"""Admin CRUD for runtime config overrides. HTTP only; logic in the service."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.deps import get_db, require_admin
from app.modules.runtime_config.schemas import (
    OverrideRead,
    SettingsListResponse,
    SettingValueWrite,
)
from app.modules.runtime_config.service import RuntimeConfigService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/admin/settings", tags=["admin"])


def _service(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RuntimeConfigService:
    return RuntimeConfigService(session, settings)


@router.get("")
async def list_settings(
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[RuntimeConfigService, Depends(_service)],
) -> SettingsListResponse:
    """Every whitelisted key: effective value, env value, override status."""
    return SettingsListResponse(settings=await service.list_effective())


@router.put("/{key}")
async def put_override(
    key: str,
    body: SettingValueWrite,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[RuntimeConfigService, Depends(_service)],
) -> OverrideRead:
    """Set or replace one override; attributed to the authenticated admin."""
    return await service.set_override(key, body.value, updated_by=admin.id)


@router.delete("/{key}", status_code=204)
async def delete_override(
    key: str,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[RuntimeConfigService, Depends(_service)],
) -> None:
    """Remove one override; the env value applies again."""
    await service.clear_override(key, updated_by=admin.id)
