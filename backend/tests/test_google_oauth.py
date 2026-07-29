"""Unit tests for the Google OAuth client (no real network; respx mocks)."""

import json
import time
from typing import Any

import jwt
import pytest
import respx
from app.core.config import Settings
from app.modules.auth.exceptions import GoogleAuthError, GoogleNotConfiguredError
from app.modules.auth.google import (
    GOOGLE_JWKS_URL,
    GOOGLE_TOKEN_URL,
    GoogleOAuthClient,
    reset_jwks_cache,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import Response

CLIENT_ID = "test-client-id.apps.googleusercontent.com"
KID = "test-kid"

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PRIVATE_PEM = _PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        google_client_id=CLIENT_ID,
        google_client_secret="test-secret",
        google_redirect_uri="http://localhost:5173/api/auth/google/callback",
    )


def _jwks() -> dict[str, Any]:
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(_PRIVATE_KEY.public_key()))
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    return {"keys": [jwk]}


def _id_token(**overrides: Any) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "google-sub-123",
        "email": "reader@example.com",
        "email_verified": True,
        "iat": now,
        "exp": now + 600,
    }
    payload.update(overrides)
    return jwt.encode(payload, _PRIVATE_PEM, algorithm="RS256", headers={"kid": KID})


@pytest.fixture(autouse=True)
def _fresh_jwks_cache() -> None:
    reset_jwks_cache()


@pytest.mark.unit
def test_missing_config_raises() -> None:
    settings = Settings(_env_file=None)
    with pytest.raises(GoogleNotConfiguredError):
        GoogleOAuthClient(settings)


@pytest.mark.unit
def test_build_auth_url_contains_required_params() -> None:
    url = GoogleOAuthClient(_settings()).build_auth_url("state-abc")
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "state=state-abc" in url
    assert "response_type=code" in url
    assert "scope=openid+email+profile" in url
    assert "prompt=select_account" in url


@pytest.mark.unit
@respx.mock
async def test_exchange_code_returns_id_token() -> None:
    respx.post(GOOGLE_TOKEN_URL).mock(return_value=Response(200, json={"id_token": "raw-token"}))
    token = await GoogleOAuthClient(_settings()).exchange_code("auth-code")
    assert token == "raw-token"


@pytest.mark.unit
@respx.mock
async def test_exchange_code_failure_raises() -> None:
    respx.post(GOOGLE_TOKEN_URL).mock(return_value=Response(400, json={"error": "bad"}))
    with pytest.raises(GoogleAuthError) as excinfo:
        await GoogleOAuthClient(_settings()).exchange_code("auth-code")
    assert excinfo.value.reason == "token_exchange_failed"


@pytest.mark.unit
@respx.mock
async def test_verify_id_token_returns_claims() -> None:
    respx.get(GOOGLE_JWKS_URL).mock(return_value=Response(200, json=_jwks()))
    claims = await GoogleOAuthClient(_settings()).verify_id_token(_id_token())
    assert claims.sub == "google-sub-123"
    assert claims.email == "reader@example.com"


@pytest.mark.unit
@respx.mock
@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"aud": "other-client"}, "invalid_id_token"),
        ({"iss": "https://evil.example.com"}, "invalid_issuer"),
        ({"exp": int(time.time()) - 60}, "invalid_id_token"),
        ({"email_verified": False}, "email_not_verified"),
    ],
)
async def test_verify_id_token_rejects_bad_claims(overrides: dict[str, Any], reason: str) -> None:
    respx.get(GOOGLE_JWKS_URL).mock(return_value=Response(200, json=_jwks()))
    with pytest.raises(GoogleAuthError) as excinfo:
        await GoogleOAuthClient(_settings()).verify_id_token(_id_token(**overrides))
    assert excinfo.value.reason == reason
