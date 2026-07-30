"""Auth business logic (login / token)."""

from __future__ import annotations

from uuid import UUID

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import create_access_token, decode_access_token
from app.modules.auth.exceptions import GoogleAuthError, NotAuthenticatedError
from app.modules.auth.google import GoogleClaims, GoogleOAuthClient
from app.modules.users.models import User
from app.modules.users.schemas import UserRead
from app.modules.users.service import UserService


class AuthService:
    """Authenticate users and issue/validate session tokens."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._users = UserService(session)
        self._settings = settings

    async def login_with_google(self, code: str) -> tuple[UserRead, str]:
        """Complete the Google code flow and return (user, jwt)."""
        client = GoogleOAuthClient(self._settings)
        id_token = await client.exchange_code(code)
        claims = await client.verify_id_token(id_token)
        user = await self._resolve_google_user(claims)
        token = create_access_token(
            user_id=user.id,
            username=user.username,
            settings=self._settings,
        )
        return UserRead.model_validate(user), token

    async def _resolve_google_user(self, claims: GoogleClaims) -> User:
        """Spec matching rules: sub → email → first-login admin claim → provision."""
        email = str(claims.email)
        user = await self._users.get_entity_by_google_sub(claims.sub)
        if user is not None:
            return user
        by_email = await self._users.get_entity_by_email(email)
        if by_email is not None:
            return await self._link_or_reject_conflict(by_email, claims.sub, email)
        if not await self._users.any_google_linked():
            admin = await self._users.get_entity_by_username(self._settings.admin_username)
            if admin is not None:
                return await self._users.link_google(admin, claims.sub, email)
        return await self._users.create_from_google(claims.sub, email)

    async def _link_or_reject_conflict(self, user: User, google_sub: str, email: str) -> User:
        """Refuse to rebind an email match already linked to a different sub."""
        if user.google_sub is not None and user.google_sub != google_sub:
            raise GoogleAuthError("google_identity_conflict")
        return await self._users.link_google(user, google_sub, email)

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
