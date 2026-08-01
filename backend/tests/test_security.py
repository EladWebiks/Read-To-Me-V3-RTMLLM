"""Unit tests for password hashing and JWT helpers."""

from uuid import uuid4

import jwt
import pytest
from app.core.security import create_access_token, decode_access_token, hash_password

from tests.factories import make_settings


@pytest.mark.unit
def test_hash_password_produces_a_distinct_hash() -> None:
    """Hashing never returns the plaintext, and is non-deterministic (salted)."""
    hashed = hash_password("correct-horse")
    assert hashed != "correct-horse"
    assert hash_password("correct-horse") != hashed


@pytest.mark.unit
def test_access_token_roundtrip() -> None:
    """JWT encode/decode preserves subject and username."""
    settings = make_settings(jwt_secret="test-secret-with-enough-length-32b")
    user_id = uuid4()
    token = create_access_token(user_id=user_id, username="admin", settings=settings)
    payload = decode_access_token(token, settings)
    assert payload["sub"] == str(user_id)
    assert payload["username"] == "admin"


@pytest.mark.unit
def test_access_token_rejects_bad_secret() -> None:
    """Tokens signed with another secret are rejected."""
    settings = make_settings(jwt_secret="test-secret-with-enough-length-32b")
    other = make_settings(jwt_secret="other-secret-with-enough-length-32")
    token = create_access_token(user_id=uuid4(), username="admin", settings=settings)
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token, other)
