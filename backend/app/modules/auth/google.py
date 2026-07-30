"""Google OAuth 2.0 / OIDC client (server-side authorization-code flow).

The only place that talks to Google. Domain code sees `GoogleClaims` only.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from pydantic import BaseModel, EmailStr, ValidationError

from app.core.config import Settings
from app.modules.auth.exceptions import GoogleAuthError, GoogleNotConfiguredError

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 — public URL, not a secret
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_ACCEPTED_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
_JWKS_TTL_SECONDS = 3600
# Minimum gap between forced (cache-bypassing) JWKS refetches triggered by an
# unrecognized `kid`. Bounds request amplification from tokens carrying random
# `kid` values while still letting legitimate key rotation resolve promptly.
_JWKS_FORCED_REFRESH_MIN_GAP_SECONDS = 300
_HTTP_TIMEOUT_SECONDS = 10.0

_jwks_cache: dict[str, Any] = {"jwks": None, "fetched_at": 0.0, "forced_at": 0.0}


class GoogleClaims(BaseModel):
    """Verified identity claims from a Google ID token."""

    sub: str
    email: EmailStr
    email_verified: bool = False
    name: str | None = None
    picture: str | None = None


def reset_jwks_cache() -> None:
    """Test hook: forget cached Google signing keys."""
    _jwks_cache["jwks"] = None
    _jwks_cache["fetched_at"] = 0.0
    _jwks_cache["forced_at"] = 0.0


class GoogleOAuthClient:
    """Builds consent URLs, exchanges codes, verifies ID tokens."""

    def __init__(self, settings: Settings) -> None:
        if not (
            settings.google.client_id
            and settings.google.client_secret
            and settings.google.redirect_uri
        ):
            raise GoogleNotConfiguredError
        self._client_id = settings.google.client_id
        self._client_secret = settings.google.client_secret
        self._redirect_uri = settings.google.redirect_uri

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
        try:
            body = response.json()
        except ValueError as exc:
            raise GoogleAuthError("token_exchange_failed") from exc
        id_token = body.get("id_token")
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
        try:
            claims = GoogleClaims.model_validate(payload)
        except ValidationError as exc:
            raise GoogleAuthError("invalid_id_token") from exc
        if not claims.email_verified:
            raise GoogleAuthError("email_not_verified")
        return claims

    async def _signing_key(self, raw_token: str) -> Any:
        try:
            kid = jwt.get_unverified_header(raw_token).get("kid")
        except jwt.PyJWTError as exc:
            raise GoogleAuthError("invalid_id_token") from exc
        jwks = await _fetch_jwks()
        key = _find_key(jwks, kid)
        if key is not None:
            return key
        # Unrecognized kid: the cached JWKS may be stale (key rotation). Force
        # exactly one re-fetch, rate-limited, before giving up. Stamp the
        # rate-limit window synchronously (no `await` between the check and
        # the stamp, so this is atomic under asyncio's cooperative scheduling)
        # and *before* the network call, so a failed refetch still consumes
        # the window instead of leaving the gate open.
        if not _forced_refresh_allowed():
            raise GoogleAuthError("unknown_signing_key")
        _jwks_cache["forced_at"] = time.time()
        jwks = await _fetch_jwks(force=True)
        key = _find_key(jwks, kid)
        if key is None:
            raise GoogleAuthError("unknown_signing_key")
        return key


def _find_key(jwks: dict[str, Any], kid: str | None) -> Any:
    for entry in jwks.get("keys", []):
        if entry.get("kid") == kid:
            return jwt.PyJWK(entry).key
    return None


def _forced_refresh_allowed() -> bool:
    elapsed = time.time() - float(_jwks_cache["forced_at"])
    return elapsed >= _JWKS_FORCED_REFRESH_MIN_GAP_SECONDS


async def _fetch_jwks(*, force: bool = False) -> dict[str, Any]:
    now = time.time()
    cached = _jwks_cache["jwks"]
    is_fresh = cached is not None and now - float(_jwks_cache["fetched_at"]) < _JWKS_TTL_SECONDS
    if is_fresh and not force:
        return dict(cached)
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            response = await client.get(GOOGLE_JWKS_URL)
    except httpx.HTTPError as exc:
        raise GoogleAuthError("jwks_fetch_failed") from exc
    if response.status_code != httpx.codes.OK:
        raise GoogleAuthError("jwks_fetch_failed")
    try:
        jwks: dict[str, Any] = response.json()
    except ValueError as exc:
        raise GoogleAuthError("jwks_fetch_failed") from exc
    _jwks_cache["jwks"] = jwks
    _jwks_cache["fetched_at"] = now
    return jwks
