"""Auth business logic: Google sign-in and session-token issue/validation.

Identity *matching* rules live in `users` — this module only orchestrates the
OAuth exchange and mints the session token. It never touches `users` ORM
entities (CLAUDE.md: module A calls module B's service, never its models).
"""

from __future__ import annotations

from uuid import UUID

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import create_access_token, decode_access_token
from app.modules.auth.exceptions import GoogleAuthError, NotAuthenticatedError
from app.modules.auth.google import GoogleOAuthClient
from app.modules.users.exceptions import (
    GoogleIdentityConflictError,
    UserAccountDisabledError,
    UserNotFoundError,
)
from app.modules.users.schemas import UserRead
from app.modules.users.service import UserService


class AuthService:
    """Authenticate users and issue/validate session tokens."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._users = UserService(session)
        self._settings = settings

    async def login_with_google(self, code: str) -> tuple[UserRead, str]:
        """Complete the Google code flow and return (user, jwt)."""
        client = GoogleOAuthClient(self._settings)
        id_token = await client.exchange_code(code)
        claims = await client.verify_id_token(id_token)
        try:
            user = await self._users.resolve_google_identity(
                google_sub=claims.sub,
                email=str(claims.email),
                admin_username=self._settings.auth.admin_username,
                picture_url=claims.picture,
            )
        except GoogleIdentityConflictError as exc:
            # Re-raised as the auth-domain error so the wire reason (and the
            # frontend's `reason` string) is unchanged by where the rule lives.
            raise GoogleAuthError("google_identity_conflict") from exc
        except UserAccountDisabledError as exc:
            # A soft-deleted account: a decided, terminal outcome, so the popup
            # must report it as one (HTTP 400 + reason) rather than fall into
            # the catch-all below and claim `internal_error`. The login page has
            # no message for this reason on purpose — it renders its generic
            # fallback instead of confirming to an unauthenticated visitor that
            # the account exists but was disabled.
            raise GoogleAuthError("account_disabled") from exc
        except Exception:
            # Leave the request-scoped session usable before propagating. A DB
            # error here — e.g. two concurrent first-logins colliding on the
            # google_sub unique index — poisons the transaction, and the router
            # deliberately converts unexpected exceptions into a popup response
            # rather than re-raising. Without this rollback the session's commit
            # would then fail during dependency teardown, replacing that popup
            # with the bare 500 the popup contract exists to prevent.
            await self._session.rollback()
            raise
        token = create_access_token(
            user_id=user.id,
            username=user.username,
            settings=self._settings,
        )
        return user, token

    async def user_from_token(self, token: str) -> UserRead:
        """Resolve the authenticated user from a JWT."""
        try:
            payload = decode_access_token(token, self._settings)
            user_id = UUID(str(payload["sub"]))
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            raise NotAuthenticatedError from exc
        try:
            return await self._users.get_by_id(user_id)
        except UserNotFoundError as exc:
            raise NotAuthenticatedError from exc
