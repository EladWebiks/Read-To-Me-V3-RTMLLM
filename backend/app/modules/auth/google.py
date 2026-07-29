"""Google OAuth 2.0 / OIDC client (server-side authorization-code flow).

The only place that talks to Google. Domain code sees `GoogleClaims` only.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from pydantic import BaseModel, EmailStr

from app.core.config import Settings
from app.modules.auth.exceptions import GoogleAuthError, GoogleNotConfiguredError

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 — public URL, not a secret
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_ACCEPTED_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
_JWKS_TTL_SECONDS = 3600
_HTTP_TIMEOUT_SECONDS = 10.0

_jwks_cache: dict[str, Any] = {"jwks": None, "fetched_at": 0.0}


class GoogleClaims(BaseModel):
    """Verified identity claims from a Google ID token."""

    sub: str
    email: EmailStr
    email_verified: bool = False
    name: str | None = None


def reset_jwks_cache() -> None:
    """Test hook: forget cached Google signing keys."""
    _jwks_cache["jwks"] = None
    _jwks_cache["fetched_at"] = 0.0


class GoogleOAuthClient:
    """Builds consent URLs, exchanges codes, verifies ID tokens."""

    def __init__(self, settings: Settings) -> None:
        if not (
            settings.google_client_id
            and settings.google_client_secret
            and settings.google_redirect_uri
        ):
            raise GoogleNotConfiguredError
        self._client_id = settings.google_client_id
        self._client_secret = settings.google_client_secret
        self._redirect_uri = settings.google_redirect_uri

    def build_auth_url(self, state: str) -> str:
        """Return the Google consent-screen URL for the popup redirect."""
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> str:
        """Exchange an authorization code for a raw ID token."""
        data = {
            "code": code,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "redirect_uri": self._redirect_uri,
            "grant_type": "authorization_code",
        }
        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.post(GOOGLE_TOKEN_URL, data=data)
        except httpx.HTTPError as exc:
            raise GoogleAuthError("token_exchange_failed") from exc
        if response.status_code != httpx.codes.OK:
            raise GoogleAuthError("token_exchange_failed")
        id_token = response.json().get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise GoogleAuthError("missing_id_token")
        return id_token

    async def verify_id_token(self, raw_token: str) -> GoogleClaims:
        """Verify signature/aud/exp/iss and return the identity claims."""
        key = await self._signing_key(raw_token)
        try:
            payload: dict[str, Any] = jwt.decode(
                raw_token,
                key=key,
                algorithms=["RS256"],
                audience=self._client_id,
                options={"require": ["exp", "aud", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise GoogleAuthError("invalid_id_token") from exc
        if payload.get("iss") not in _ACCEPTED_ISSUERS:
            raise GoogleAuthError("invalid_issuer")
        claims = GoogleClaims.model_validate(payload)
        if not claims.email_verified:
            raise GoogleAuthError("email_not_verified")
        return claims

    async def _signing_key(self, raw_token: str) -> Any:
        try:
            kid = jwt.get_unverified_header(raw_token).get("kid")
        except jwt.PyJWTError as exc:
            raise GoogleAuthError("invalid_id_token") from exc
        jwks = await _fetch_jwks()
        for entry in jwks.get("keys", []):
            if entry.get("kid") == kid:
                return jwt.PyJWK(entry).key
        raise GoogleAuthError("unknown_signing_key")


async def _fetch_jwks() -> dict[str, Any]:
    now = time.time()
    cached = _jwks_cache["jwks"]
    if cached is not None and now - float(_jwks_cache["fetched_at"]) < _JWKS_TTL_SECONDS:
        return dict(cached)
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            response = await client.get(GOOGLE_JWKS_URL)
    except httpx.HTTPError as exc:
        raise GoogleAuthError("jwks_fetch_failed") from exc
    if response.status_code != httpx.codes.OK:
        raise GoogleAuthError("jwks_fetch_failed")
    jwks: dict[str, Any] = response.json()
    _jwks_cache["jwks"] = jwks
    _jwks_cache["fetched_at"] = now
    return jwks
