"""Auth business logic (login / token)."""

from __future__ import annotations

from uuid import UUID

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    verify_password,
)
from app.modules.auth.exceptions import InvalidCredentialsError, NotAuthenticatedError
from app.modules.users.schemas import UserRead
from app.modules.users.service import UserService


class AuthService:
    """Authenticate users and issue/validate session tokens."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._users = UserService(session)
        self._settings = settings

    async def login(self, username: str, password: str) -> tuple[UserRead, str]:
        """Validate credentials and return (user, jwt)."""
        user = await self._users.get_entity_by_username(username)
        if (
            user is None
            or user.password_hash is None
            or not verify_password(user.password_hash, password)
        ):
            raise InvalidCredentialsError
        token = create_access_token(
            user_id=user.id,
            username=user.username,
            settings=self._settings,
        )
        return UserRead.model_validate(user), token

    async def user_from_token(self, token: str) -> UserRead:
        """Resolve the authenticated user from a JWT."""
        try:
            payload = decode_access_token(token, self._settings)
            user_id = UUID(str(payload["sub"]))
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            raise NotAuthenticatedError from exc
        user = await self._users.get_entity_by_id(user_id)
        if user is None:
            raise NotAuthenticatedError
        return UserRead.model_validate(user)
