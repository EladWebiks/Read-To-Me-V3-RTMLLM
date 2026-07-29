"""User business logic."""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.users.exceptions import UserAlreadyExistsError, UserNotFoundError
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate, UserRead


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
            role=data.role,
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

    async def link_google(self, user: User, google_sub: str, email: str) -> User:
        """Attach a Google identity to an existing user."""
        user.google_sub = google_sub
        if user.email is None:
            user.email = email
        return await self._repo.save(user)

    async def create_from_google(self, google_sub: str, email: str) -> User:
        """Provision a new user from a verified Google identity."""
        username = await self._unique_username(email.split("@")[0])
        user = User(
            username=username,
            email=email,
            password_hash=None,
            google_sub=google_sub,
            role="user",
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
