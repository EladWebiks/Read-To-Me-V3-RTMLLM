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
FORGED_KID = "forged-kid"

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PRIVATE_PEM = _PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)

# A second, unrelated key pair used to simulate a forged/attacker-controlled
# token. Its public half is never published in the mocked JWKS.
_FORGED_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_FORGED_PRIVATE_PEM = _FORGED_PRIVATE_KEY.private_bytes(
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


def _forged_id_token(*, kid: str = FORGED_KID, **overrides: Any) -> str:
    """A token signed by a key the mocked JWKS never publishes."""
    now = int(time.time())
    payload: dict[str, Any] = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "attacker-sub",
        "email": "attacker@example.com",
        "email_verified": True,
        "iat": now,
        "exp": now + 600,
    }
    payload.update(overrides)
    return jwt.encode(payload, _FORGED_PRIVATE_PEM, algorithm="RS256", headers={"kid": kid})


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


@pytest.mark.unit
@respx.mock
async def test_verify_id_token_rejects_unknown_kid_after_forced_refetch() -> None:
    """A token whose kid is absent from the JWKS (forged or rotated-out) is rejected.

    Confirms the forced-refetch-on-unknown-kid path (finding 3): the JWKS
    endpoint is hit twice — the normal cache-miss fetch, then one forced
    re-fetch before giving up — rather than trusting a stale cache forever.
    """
    route = respx.get(GOOGLE_JWKS_URL).mock(return_value=Response(200, json=_jwks()))
    with pytest.raises(GoogleAuthError) as excinfo:
        await GoogleOAuthClient(_settings()).verify_id_token(_forged_id_token())
    assert excinfo.value.reason == "unknown_signing_key"
    assert route.call_count == 2


@pytest.mark.unit
@respx.mock
async def test_unknown_kid_forced_refetch_is_rate_limited() -> None:
    """A second unknown-kid token shortly after does not trigger another refetch."""
    route = respx.get(GOOGLE_JWKS_URL).mock(return_value=Response(200, json=_jwks()))
    client = GoogleOAuthClient(_settings())
    with pytest.raises(GoogleAuthError):
        await client.verify_id_token(_forged_id_token())
    assert route.call_count == 2
    with pytest.raises(GoogleAuthError):
        await client.verify_id_token(_forged_id_token(kid=FORGED_KID))
    assert route.call_count == 2  # rate-limited: no extra forced refetch


@pytest.mark.unit
@respx.mock
async def test_unknown_kid_forced_refetch_failure_still_consumes_rate_limit() -> None:
    """A failed forced refetch must still consume the rate-limit window.

    Otherwise an upstream JWKS outage would let every subsequent unknown-kid
    token re-trigger a live forced fetch with no rate limiting at all.
    """
    route = respx.get(GOOGLE_JWKS_URL).mock(
        side_effect=[Response(200, json=_jwks()), Response(500)]
    )
    client = GoogleOAuthClient(_settings())
    with pytest.raises(GoogleAuthError) as excinfo:
        await client.verify_id_token(_forged_id_token())
    assert excinfo.value.reason == "jwks_fetch_failed"
    assert route.call_count == 2
    with pytest.raises(GoogleAuthError) as excinfo2:
        await client.verify_id_token(_forged_id_token())
    assert excinfo2.value.reason == "unknown_signing_key"
    assert route.call_count == 2  # the failed forced attempt still consumed the window


@pytest.mark.unit
@respx.mock
async def test_verify_id_token_rejects_forged_signature_with_known_kid() -> None:
    """A token claiming a real kid but signed with an unrelated key must still fail."""
    respx.get(GOOGLE_JWKS_URL).mock(return_value=Response(200, json=_jwks()))
    forged_but_known_kid = _forged_id_token(kid=KID)
    with pytest.raises(GoogleAuthError) as excinfo:
        await GoogleOAuthClient(_settings()).verify_id_token(forged_but_known_kid)
    assert excinfo.value.reason == "invalid_id_token"


@pytest.mark.unit
@respx.mock
async def test_verify_id_token_jwks_fetch_failure_raises() -> None:
    respx.get(GOOGLE_JWKS_URL).mock(return_value=Response(500))
    with pytest.raises(GoogleAuthError) as excinfo:
        await GoogleOAuthClient(_settings()).verify_id_token(_id_token())
    assert excinfo.value.reason == "jwks_fetch_failed"


@pytest.mark.unit
@respx.mock
async def test_verify_id_token_jwks_malformed_json_raises() -> None:
    respx.get(GOOGLE_JWKS_URL).mock(return_value=Response(200, content=b"not-json"))
    with pytest.raises(GoogleAuthError) as excinfo:
        await GoogleOAuthClient(_settings()).verify_id_token(_id_token())
    assert excinfo.value.reason == "jwks_fetch_failed"


@pytest.mark.unit
@respx.mock
async def test_verify_id_token_rejects_malformed_claims() -> None:
    """A signature-valid token missing a required claim (email) fails validation."""
    respx.get(GOOGLE_JWKS_URL).mock(return_value=Response(200, json=_jwks()))
    now = int(time.time())
    payload = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "google-sub-123",
        "iat": now,
        "exp": now + 600,
    }
    token = jwt.encode(payload, _PRIVATE_PEM, algorithm="RS256", headers={"kid": KID})
    with pytest.raises(GoogleAuthError) as excinfo:
        await GoogleOAuthClient(_settings()).verify_id_token(token)
    assert excinfo.value.reason == "invalid_id_token"


@pytest.mark.unit
@respx.mock
async def test_exchange_code_missing_id_token_raises() -> None:
    respx.post(GOOGLE_TOKEN_URL).mock(return_value=Response(200, json={}))
    with pytest.raises(GoogleAuthError) as excinfo:
        await GoogleOAuthClient(_settings()).exchange_code("auth-code")
    assert excinfo.value.reason == "missing_id_token"


@pytest.mark.unit
@respx.mock
async def test_exchange_code_malformed_json_raises() -> None:
    respx.post(GOOGLE_TOKEN_URL).mock(return_value=Response(200, content=b"not-json"))
    with pytest.raises(GoogleAuthError) as excinfo:
        await GoogleOAuthClient(_settings()).exchange_code("auth-code")
    assert excinfo.value.reason == "token_exchange_failed"
