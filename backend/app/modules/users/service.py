"""User business logic."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.users.exceptions import (
    AdminSelfActionError,
    GoogleIdentityConflictError,
    LastAdminError,
    UserAccountDisabledError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserAdminPatch, UserAdminRead, UserCreate, UserRead

logger = logging.getLogger(__name__)


class UserService:
    """Owns user create/lookup rules, Google identity matching, and the
    backoffice admin mutations (privilege, membership, soft-delete/restore).

    Soft-delete policy: a soft-deleted identity stays *reserved*. The
    `username`/`email`/`google_sub` unique constraints span the whole table
    (they are not partial), so the deleted row keeps owning its values while
    every ownership-scoped read filters it out. Collision and sign-in checks
    therefore use the explicit `*_any` repository lookups and raise typed
    errors; nothing here auto-restores a user except the bootstrap admin in
    `ensure_user`, which the application cannot start without.
    """

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
        """Create a user with a hashed password.

        The duplicate check is any-scoped: a soft-deleted row still owns the
        username, so a deleted-filtered check would miss it and turn a 409 into
        an IntegrityError-driven 500.
        """
        existing = await self._repo.get_by_username_any(data.username)
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
        """Idempotent create: return the named user — restoring it if soft-deleted.

        This runs from the startup bootstrap, inside the FastAPI lifespan where
        no handler catches anything. A soft-deleted row holding the configured
        admin username is invisible to the deleted-filtered lookup yet still
        owns the unique username, so inserting would raise IntegrityError and
        crash-loop the app — recoverable only by hand, since the backoffice
        that could restore the row lives in the app that will not start. The
        bootstrap contract is "the configured user exists and is usable", so
        the row is reopened instead. This is the *only* automatic restore;
        every other one is an explicit admin action.
        """
        existing = await self._repo.get_by_username_any(data.username)
        if existing is None:
            return await self.create(data)
        if existing.deleted_at is not None:
            logger.warning(
                "bootstrap user was soft-deleted; restoring",
                extra={"target": str(existing.id), "username": existing.username},
            )
            existing.deleted_at = None
            existing = await self._repo.save(existing)
        return UserRead.model_validate(existing)

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

        Rules 1 and 2 match any-scoped and then reject soft-deleted rows with
        `UserAccountDisabledError`: those identity values are still taken, so
        falling through to rule 4 would try to insert a duplicate `google_sub`
        or `email` and surface a DB error instead of a decision. Sign-in never
        restores an account — only an admin does.

        `admin_username` is passed in rather than read from `Settings` so this
        module stays free of app configuration.
        """
        normalized = email.lower()
        by_sub = await self._repo.get_by_google_sub_any(google_sub)
        if by_sub is not None:
            self._reject_if_disabled(by_sub)
            return UserRead.model_validate(await self._refresh_picture(by_sub, picture_url))
        by_email = await self._repo.get_by_email_any(normalized)
        if by_email is not None:
            self._reject_if_disabled(by_email)
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

    @staticmethod
    def _reject_if_disabled(user: User) -> None:
        """Refuse sign-in for a soft-deleted account (identity stays reserved)."""
        if user.deleted_at is not None:
            raise UserAccountDisabledError(str(user.id))

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
        """Sanitize the email local-part and dedupe with a numeric suffix.

        Any-scoped: a soft-deleted row still holds its username, so a
        deleted-filtered probe would hand back a value the insert cannot use.
        """
        cleaned = re.sub(r"[^a-z0-9._-]", "", base.lower())[:56] or "user"
        candidate = cleaned
        suffix = 1
        while await self._repo.get_by_username_any(candidate) is not None:
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
        changed: dict[str, str | bool] = {}
        if patch.is_admin is not None and patch.is_admin != user.is_admin:
            await self._guard_demotion(actor_id, user, demote=not patch.is_admin)
            user.is_admin = patch.is_admin
            changed["is_admin"] = patch.is_admin
        if patch.membership is not None and patch.membership != user.membership:
            user.membership = patch.membership
            changed["membership"] = patch.membership.value
        row = UserAdminRead.from_user(await self._repo.save(user))
        if changed:
            self._audit("admin changed user", actor_id, user_id, **changed)
        return row

    async def soft_delete_user_admin(self, *, actor_id: UUID, user_id: UUID) -> UserAdminRead:
        """Soft-delete a user; blocked for self and for the last active admin."""
        user = await self._require_any(user_id)
        if user.id == actor_id:
            raise AdminSelfActionError("self-delete")
        if user.is_admin and user.deleted_at is None:
            await self._guard_last_admin()
        if user.deleted_at is None:
            user.deleted_at = datetime.now(UTC)
        self._audit("admin soft-deleted user", actor_id, user_id, was_admin=user.is_admin)
        return UserAdminRead.from_user(await self._repo.save(user))

    async def restore_user_admin(self, *, actor_id: UUID, user_id: UUID) -> UserAdminRead:
        """Clear a user's soft-delete marker (the only non-bootstrap restore)."""
        user = await self._require_any(user_id)
        user.deleted_at = None
        self._audit("admin restored user", actor_id, user_id, was_admin=user.is_admin)
        return UserAdminRead.from_user(await self._repo.save(user))

    @staticmethod
    def _audit(event: str, actor_id: UUID, user_id: UUID, **fields: str | bool) -> None:
        """Leave a trace of a privileged user mutation: who did what to whom.

        Ids only — no credentials and no secrets. There is no audit_log table
        yet, so the structured log line is the record.
        """
        logger.info(event, extra={"actor": str(actor_id), "target": str(user_id), **fields})

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
