"""Unit tests for password hashing and JWT helpers."""

from uuid import uuid4

import jwt
import pytest
from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


@pytest.mark.unit
def test_password_hash_roundtrip() -> None:
    """Hashed passwords verify; wrong passwords fail."""
    hashed = hash_password("correct-horse")
    assert verify_password(hashed, "correct-horse")
    assert not verify_password(hashed, "wrong-password")


@pytest.mark.unit
def test_access_token_roundtrip() -> None:
    """JWT encode/decode preserves subject and username."""
    settings = Settings(jwt_secret="test-secret-with-enough-length-32b")
    user_id = uuid4()
    token = create_access_token(user_id=user_id, username="admin", settings=settings)
    payload = decode_access_token(token, settings)
    assert payload["sub"] == str(user_id)
    assert payload["username"] == "admin"


@pytest.mark.unit
def test_access_token_rejects_bad_secret() -> None:
    """Tokens signed with another secret are rejected."""
    settings = Settings(jwt_secret="test-secret-with-enough-length-32b")
    other = Settings(jwt_secret="other-secret-with-enough-length-32")
    token = create_access_token(user_id=uuid4(), username="admin", settings=settings)
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token, other)
