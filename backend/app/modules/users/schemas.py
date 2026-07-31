"""User API / service schemas."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

if TYPE_CHECKING:
    from app.modules.users.models import MembershipTier, User


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
    membership: str
    created_at: datetime


class UserAdminRead(BaseModel):
    """Backoffice view of one user (soft-deleted rows included, marked)."""

    id: UUID
    username: str
    email: str | None
    is_admin: bool
    membership: str
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
            membership=user.membership,
            google_linked=user.google_sub is not None,
            created_at=user.created_at,
            deleted_at=user.deleted_at,
        )


class UserAdminPatch(BaseModel):
    """PATCH /api/admin/users/{id} body — only supplied fields change."""

    is_admin: bool | None = None
    membership: str | None = None


class MembershipCreate(BaseModel):
    """POST /api/admin/memberships body. Slug is immutable after creation."""

    slug: str = Field(pattern=r"^[a-z0-9_-]{1,32}$")
    label: str = Field(min_length=1, max_length=64)
    rank: int = 0
    description: str | None = None
    price_label: str | None = Field(default=None, max_length=32)


class MembershipPatch(BaseModel):
    """PATCH body — only supplied fields change; explicit null clears text.

    is_default/is_active only accept True: crowning moves the flag, and
    deactivation goes through the dedicated endpoint (it needs a target).
    """

    label: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = None
    price_label: str | None = Field(default=None, max_length=32)
    rank: int | None = None
    is_default: Literal[True] | None = None
    is_active: Literal[True] | None = None


class MembershipAdminRead(BaseModel):
    """Backoffice view of one tier, with how many users sit on it."""

    slug: str
    label: str
    description: str | None
    price_label: str | None
    rank: int
    is_active: bool
    is_default: bool
    user_count: int
    updated_at: datetime

    @classmethod
    def from_tier(cls, tier: MembershipTier, user_count: int) -> MembershipAdminRead:
        return cls(
            slug=tier.slug,
            label=tier.label,
            description=tier.description,
            price_label=tier.price_label,
            rank=tier.rank,
            is_active=tier.is_active,
            is_default=tier.is_default,
            user_count=user_count,
            updated_at=tier.updated_at,
        )


class MembershipsResponse(BaseModel):
    memberships: list[MembershipAdminRead]


class MembershipDeactivate(BaseModel):
    migrate_to: str


class PlanRead(BaseModel):
    """One selectable plan on the self-serve picker."""

    slug: str
    label: str
    description: str | None
    price_label: str | None
    current: bool


class PlansResponse(BaseModel):
    plans: list[PlanRead]
    can_switch: bool


class MembershipSwitch(BaseModel):
    membership: str
