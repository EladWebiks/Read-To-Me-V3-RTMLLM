"""Membership tier lifecycle: create / edit / deactivate-with-migration.

Write paths validate against the DB (always fresh); hot read paths use the
membership_registry snapshot. Every write calls registry.invalidate().
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users import membership_registry
from app.modules.users.exceptions import (
    DuplicateMembershipError,
    MembershipLifecycleError,
    UnknownMembershipError,
    UserNotFoundError,
)
from app.modules.users.membership import DEFAULT_SLUG
from app.modules.users.membership_repository import MembershipRepository
from app.modules.users.models import MembershipTier
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import (
    MembershipAdminRead,
    MembershipCreate,
    MembershipPatch,
    PlanRead,
    UserRead,
)

logger = logging.getLogger(__name__)


class MembershipService:
    """Owns tier registry rules; tiers are deactivated, never deleted."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = MembershipRepository(session)
        self._users = UserRepository(session)

    async def list_tiers(self) -> list[MembershipAdminRead]:
        counts = await self._repo.user_counts()
        rows = await self._repo.list_all()
        return [MembershipAdminRead.from_tier(row, counts.get(row.slug, 0)) for row in rows]

    async def require_tier(self, slug: str) -> MembershipTier:
        row = await self._repo.get_by_slug(slug)
        if row is None:
            raise UnknownMembershipError(slug)
        return row

    async def require_assignable(self, slug: str) -> MembershipTier:
        """Assignment paths only accept active tiers (spec §3)."""
        row = await self.require_tier(slug)
        if not row.is_active:
            raise UnknownMembershipError(slug)
        return row

    async def default_slug(self) -> str:
        row = await self._repo.get_default()
        if row is None:  # partial unique index + seed make this near-impossible
            logger.warning(
                "no default membership tier; falling back", extra={"slug": DEFAULT_SLUG}
            )
            return DEFAULT_SLUG
        return row.slug

    async def create_tier(self, data: MembershipCreate, *, actor_id: UUID) -> MembershipTier:
        if await self._repo.get_by_slug(data.slug) is not None:
            raise DuplicateMembershipError(data.slug)
        row = MembershipTier(
            slug=data.slug,
            label=data.label,
            rank=data.rank,
            description=data.description,
            price_label=data.price_label,
            is_active=True,
            is_default=False,
        )
        self._repo.add(row)
        saved = await self._repo.save(row)
        membership_registry.invalidate()
        logger.info("membership tier created", extra={"slug": data.slug, "actor": str(actor_id)})
        return saved

    async def update_tier(
        self, slug: str, patch: MembershipPatch, *, actor_id: UUID
    ) -> MembershipTier:
        row = await self.require_tier(slug)
        changes = patch.model_dump(exclude_unset=True)
        if changes.pop("is_default", None):
            await self._repo.clear_default()
            row.is_default = True
        for field, value in changes.items():
            setattr(row, field, value)
        saved = await self._repo.save(row)
        membership_registry.invalidate()
        logger.info(
            "membership tier updated",
            extra={"slug": slug, "actor": str(actor_id), "changes": list(changes)},
        )
        return saved

    async def deactivate_tier(
        self, slug: str, migrate_to: str, *, actor_id: UUID
    ) -> tuple[MembershipTier, int]:
        """Reassign every user to the target, then deactivate. One transaction."""
        row = await self.require_tier(slug)
        if row.is_default:
            raise MembershipLifecycleError(
                "Cannot deactivate the default tier — set another default first."
            )
        if migrate_to == slug:
            raise MembershipLifecycleError("Migration target must be a different tier.")
        target = await self.require_tier(migrate_to)
        if not target.is_active:
            raise MembershipLifecycleError("Migration target must be an active tier.")
        moved = await self._repo.reassign_users(slug, migrate_to)
        row.is_active = False
        saved = await self._repo.save(row)
        membership_registry.invalidate()
        logger.info(
            "membership tier deactivated",
            extra={
                "slug": slug,
                "migrated_to": migrate_to,
                "moved": moved,
                "actor": str(actor_id),
            },
        )
        return saved, moved

    async def active_plans(self, current_slug: str) -> list[PlanRead]:
        """Active tiers in rank order for the self-serve picker."""
        rows = await self._repo.list_all()
        return [
            PlanRead(
                slug=row.slug,
                label=row.label,
                description=row.description,
                price_label=row.price_label,
                current=row.slug == current_slug,
            )
            for row in rows
            if row.is_active
        ]

    async def switch_user(self, user_id: UUID, slug: str) -> UserRead:
        """Self-serve tier switch (no billing). Validates active; audited."""
        await self.require_assignable(slug)
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(str(user_id))
        user.membership = slug
        await self._users.save(user)
        logger.info("user switched membership", extra={"actor": str(user_id), "membership": slug})
        return UserRead.model_validate(user)
