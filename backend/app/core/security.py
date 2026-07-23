"""Password hashing and JWT helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import Settings

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a password with argon2."""
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Return True when password matches the stored hash."""
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(*, user_id: UUID, username: str, settings: Settings) -> str:
    """Create a signed JWT for the given user."""
    now = datetime.now(UTC)
    expires = now + timedelta(days=settings.jwt_expire_days)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": expires,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    """Decode and validate a JWT; raises jwt.PyJWTError on failure."""
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
    if not isinstance(payload, dict):
        msg = "Invalid token payload"
        raise jwt.InvalidTokenError(msg)
    return payload
