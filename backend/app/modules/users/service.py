"""User business logic."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.users.exceptions import (
    AdminSelfActionError,
    GoogleIdentityConflictError,
    LastAdminError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserAdminPatch, UserAdminRead, UserCreate, UserRead


class UserService:
    """Owns user create/lookup rules."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = UserRepository(session)

    async def get_by_id(self, user_id: UUID) -> UserRead:
        """Fetch a user or raise UserNotFoundError."""
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(str(user_id))
        return UserRead.model_validate(user)

    async def get_entity_by_username(self, username: str) -> User | None:
        """Return the ORM user for auth verification (internal use)."""
        return await self._repo.get_by_username(username)

    async def get_entity_by_id(self, user_id: UUID) -> User | None:
        """Return the ORM user by id (internal use)."""
        return await self._repo.get_by_id(user_id)

    async def create(self, data: UserCreate) -> UserRead:
        """Create a user with a hashed password."""
        existing = await self._repo.get_by_username(data.username)
        if existing is not None:
            raise UserAlreadyExistsError(data.username)
        user = User(
            username=data.username,
            email=str(data.email) if data.email else None,
            password_hash=hash_password(data.password),
            is_admin=data.is_admin,
        )
        created = await self._repo.add(user)
        return UserRead.model_validate(created)

    async def ensure_user(self, data: UserCreate) -> UserRead:
        """Idempotent create: return existing username or create new."""
        existing = await self._repo.get_by_username(data.username)
        if existing is not None:
            return UserRead.model_validate(existing)
        return await self.create(data)

    async def get_entity_by_email(self, email: str) -> User | None:
        """Return the ORM user by email (internal use)."""
        return await self._repo.get_by_email(email)

    async def get_entity_by_google_sub(self, google_sub: str) -> User | None:
        """Return the ORM user by Google subject id (internal use)."""
        return await self._repo.get_by_google_sub(google_sub)

    async def any_google_linked(self) -> bool:
        """True when any user already signed in with Google."""
        return await self._repo.any_google_linked()

    async def resolve_google_identity(
        self,
        *,
        google_sub: str,
        email: str,
        admin_username: str,
        picture_url: str | None = None,
    ) -> UserRead:
        """Map a verified Google identity onto a user row, provisioning if needed.

        Rules, in precedence order:
        1. match by `google_sub` (a returning user, even if their email changed);
        2. match by email — link the Google identity to that existing account;
        3. first Google login overall claims the seeded admin row named by
           `admin_username` (accepted risk: no email allowlist gates this);
        4. otherwise provision a fresh user.

        `admin_username` is passed in rather than read from `Settings` so this
        module stays free of app configuration.
        """
        normalized = email.lower()
        by_sub = await self._repo.get_by_google_sub(google_sub)
        if by_sub is not None:
            return UserRead.model_validate(await self._refresh_picture(by_sub, picture_url))
        by_email = await self._repo.get_by_email(normalized)
        if by_email is not None:
            linked = await self._link_or_reject_conflict(
                by_email, google_sub, normalized, picture_url
            )
            return UserRead.model_validate(linked)
        if not await self._repo.any_google_linked():
            admin = await self._repo.get_by_username(admin_username)
            if admin is not None:
                return UserRead.model_validate(
                    await self.link_google(admin, google_sub, normalized, picture_url)
                )
        return UserRead.model_validate(
            await self.create_from_google(google_sub, normalized, picture_url)
        )

    async def _link_or_reject_conflict(
        self, user: User, google_sub: str, email: str, picture_url: str | None = None
    ) -> User:
        """Refuse to rebind an email match already linked to a different sub."""
        # The `!= google_sub` half is unreachable in the current call path: the
        # `google_sub` lookup above already missed, so a non-NULL `google_sub`
        # here is necessarily a different one. Kept as a defensive invariant so
        # the guard stays correct if this helper is ever called from elsewhere.
        if user.google_sub is not None and user.google_sub != google_sub:
            raise GoogleIdentityConflictError(email)
        return await self.link_google(user, google_sub, email, picture_url)

    async def _refresh_picture(self, user: User, picture_url: str | None) -> User:
        """Keep the stored Google picture fresh; a missing claim changes nothing."""
        if picture_url is None or user.picture_url == picture_url:
            return user
        user.picture_url = picture_url
        return await self._repo.save(user)

    async def link_google(
        self, user: User, google_sub: str, email: str, picture_url: str | None = None
    ) -> User:
        """Attach a Google identity to an existing user."""
        user.google_sub = google_sub
        if user.email is None:
            user.email = email.lower()
        if picture_url is not None:
            user.picture_url = picture_url
        return await self._repo.save(user)

    async def create_from_google(
        self, google_sub: str, email: str, picture_url: str | None = None
    ) -> User:
        """Provision a new user from a verified Google identity."""
        normalized = email.lower()
        username = await self._unique_username(normalized.split("@")[0])
        user = User(
            username=username,
            email=normalized,
            password_hash=None,
            google_sub=google_sub,
            picture_url=picture_url,
        )
        return await self._repo.add(user)

    async def _unique_username(self, base: str) -> str:
        """Sanitize the email local-part and dedupe with a numeric suffix."""
        cleaned = re.sub(r"[^a-z0-9._-]", "", base.lower())[:56] or "user"
        candidate = cleaned
        suffix = 1
        while await self._repo.get_by_username(candidate) is not None:
            suffix += 1
            candidate = f"{cleaned}{suffix}"
        return candidate

    async def list_users_admin(
        self, *, limit: int, offset: int
    ) -> tuple[list[UserAdminRead], int]:
        """Backoffice page over all users, soft-deleted included."""
        users, total = await self._repo.list_all(limit=limit, offset=offset)
        return [UserAdminRead.from_user(user) for user in users], total

    async def update_user_admin(
        self, *, actor_id: UUID, user_id: UUID, patch: UserAdminPatch
    ) -> UserAdminRead:
        """Apply is_admin/membership changes with backoffice safety rails."""
        user = await self._require_any(user_id)
        if patch.is_admin is not None and patch.is_admin != user.is_admin:
            await self._guard_demotion(actor_id, user, demote=not patch.is_admin)
            user.is_admin = patch.is_admin
        if patch.membership is not None:
            user.membership = patch.membership
        return UserAdminRead.from_user(await self._repo.save(user))

    async def soft_delete_user_admin(self, *, actor_id: UUID, user_id: UUID) -> UserAdminRead:
        """Soft-delete a user; blocked for self and for the last active admin."""
        user = await self._require_any(user_id)
        if user.id == actor_id:
            raise AdminSelfActionError("self-delete")
        if user.is_admin and user.deleted_at is None:
            await self._guard_last_admin()
        if user.deleted_at is None:
            user.deleted_at = datetime.now(UTC)
        return UserAdminRead.from_user(await self._repo.save(user))

    async def restore_user_admin(self, user_id: UUID) -> UserAdminRead:
        """Clear a user's soft-delete marker."""
        user = await self._require_any(user_id)
        user.deleted_at = None
        return UserAdminRead.from_user(await self._repo.save(user))

    async def _require_any(self, user_id: UUID) -> User:
        user = await self._repo.get_by_id_any(user_id)
        if user is None:
            raise UserNotFoundError(str(user_id))
        return user

    async def _guard_demotion(self, actor_id: UUID, user: User, *, demote: bool) -> None:
        if not demote:
            return
        if user.id == actor_id:
            raise AdminSelfActionError("self-demote")
        if user.deleted_at is None:
            await self._guard_last_admin()

    async def _guard_last_admin(self) -> None:
        if await self._repo.count_active_admins() <= 1:
            raise LastAdminError("at least one active admin must remain")
