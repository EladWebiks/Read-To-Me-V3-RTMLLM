"""User API / service schemas."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.users.membership import Membership

if TYPE_CHECKING:
    from app.modules.users.models import User


class UserCreate(BaseModel):
    """Input for creating a user."""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    email: EmailStr | None = None
    is_admin: bool = False


class UserRead(BaseModel):
    """Public user representation (never includes password)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str | None
    picture_url: str | None = None
    is_admin: bool
    membership: Membership
    created_at: datetime


class UserAdminRead(BaseModel):
    """Backoffice view of one user (soft-deleted rows included, marked)."""

    id: UUID
    username: str
    email: str | None
    is_admin: bool
    membership: Membership
    google_linked: bool
    created_at: datetime
    deleted_at: datetime | None

    @classmethod
    def from_user(cls, user: User) -> UserAdminRead:
        """Build the admin row; google_linked derives from google_sub."""
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            is_admin=user.is_admin,
            membership=Membership(user.membership),
            google_linked=user.google_sub is not None,
            created_at=user.created_at,
            deleted_at=user.deleted_at,
        )


class UserAdminPatch(BaseModel):
    """PATCH /api/admin/users/{id} body — only supplied fields change."""

    is_admin: bool | None = None
    membership: Membership | None = None
