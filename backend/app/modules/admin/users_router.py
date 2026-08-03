"""Backoffice user management routes. HTTP only; logic in UserService."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_admin
from app.modules.admin.schemas import Page
from app.modules.users.admin_list import AdminUserListParams
from app.modules.users.schemas import UserAdminPatch, UserAdminRead, UserRead
from app.modules.users.service import UserService

router = APIRouter(prefix="/users")


def _service(session: Annotated[AsyncSession, Depends(get_db)]) -> UserService:
    return UserService(session)


@router.get("")
async def list_users(
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[UserService, Depends(_service)],
    query: AdminUserListParams,
) -> Page[UserAdminRead]:
    """Users with optional search/filters/sort (soft-deleted included by default)."""
    items, total = await service.list_users_admin(query)
    return Page(items=items, total=total, limit=query.limit, offset=query.offset)


@router.patch("/{user_id}")
async def patch_user(
    user_id: UUID,
    body: UserAdminPatch,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[UserService, Depends(_service)],
) -> UserAdminRead:
    """Toggle is_admin / change membership (operator override; Stripe later)."""
    return await service.update_user_admin(actor_id=admin.id, user_id=user_id, patch=body)


@router.delete("/{user_id}")
async def soft_delete_user(
    user_id: UUID,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[UserService, Depends(_service)],
) -> UserAdminRead:
    """Soft-delete a user (row stays visible in the backoffice, marked)."""
    return await service.soft_delete_user_admin(actor_id=admin.id, user_id=user_id)


@router.post("/{user_id}/restore")
async def restore_user(
    user_id: UUID,
    admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[UserService, Depends(_service)],
) -> UserAdminRead:
    """Clear a user's soft-delete marker."""
    return await service.restore_user_admin(actor_id=admin.id, user_id=user_id)
