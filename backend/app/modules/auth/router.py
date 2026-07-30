"""Auth HTTP routes: Google login, logout, me."""

import json
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.deps import get_current_user, get_db
from app.modules.auth.exceptions import GoogleAuthError
from app.modules.auth.google import GoogleOAuthClient
from app.modules.auth.schemas import MeResponse
from app.modules.auth.service import AuthService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "rtm_token"


def _auth_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(session, settings)


def _set_auth_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.jwt_expire_days * 24 * 60 * 60,
        path="/",
    )


STATE_COOKIE_NAME = "rtm_oauth_state"
STATE_COOKIE_PATH = "/api/auth/google"
STATE_TTL_SECONDS = 600


def _popup_response(*, ok: bool, reason: str | None, status_code: int) -> HTMLResponse:
    """Tiny page that reports the result to the opener window and closes."""
    payload = json.dumps({"type": "rtm-google-auth", "ok": ok, "reason": reason}, indent=1)
    # `reason` is untrusted-adjacent text embedded inside an inline <script>.
    # Escaping "</" prevents it from prematurely closing the script tag and
    # injecting markup, even though today's reason values are fixed literals.
    payload = payload.replace("</", "<\\/")
    html = (
        "<!doctype html><html><body><script>"
        f"if (window.opener) {{ window.opener.postMessage({payload}, window.location.origin); }}"
        "window.close();"
        "</script><p>You can close this window.</p></body></html>"
    )
    return HTMLResponse(content=html, status_code=status_code)


def _popup_error(reason: str, status_code: int) -> HTMLResponse:
    """Failure variant of the popup response; also clears the spent state cookie.

    The state cookie is single-use — clear it on every terminal failure path,
    not just success, so a stale value can't be replayed for up to its full TTL.
    """
    response = _popup_response(ok=False, reason=reason, status_code=status_code)
    response.delete_cookie(key=STATE_COOKIE_NAME, path=STATE_COOKIE_PATH)
    return response


@router.get("/google/login")
async def google_login(
    settings: Annotated[Settings, Depends(get_settings)],
) -> RedirectResponse:
    """Start the Google OAuth flow: set a state cookie, redirect to consent."""
    client = GoogleOAuthClient(settings)
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(client.build_auth_url(state), status_code=302)
    response.set_cookie(
        key=STATE_COOKIE_NAME,
        value=state,
        httponly=True,
        secure=settings.cookie_secure,
        # Hardcoded, not settings.cookie_samesite: the callback is a cross-site
        # top-level navigation from accounts.google.com, which "Strict" cookies
        # are not sent on. If cookie_samesite were ever set to "strict", every
        # Google login would break with an opaque state_mismatch. "Lax" is
        # required here regardless of the session cookie's own SameSite policy.
        samesite="lax",
        max_age=STATE_TTL_SECONDS,
        path=STATE_COOKIE_PATH,
    )
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    service: Annotated[AuthService, Depends(_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    """Finish the flow: validate state, exchange code, set session cookie."""
    if error or not code:
        return _popup_error("google_denied", 400)
    expected = request.cookies.get(STATE_COOKIE_NAME)
    if not state or not expected or not secrets.compare_digest(state, expected):
        return _popup_error("state_mismatch", 400)
    try:
        _user, token = await service.login_with_google(code)
    except GoogleAuthError as exc:
        return _popup_error(exc.reason, 400)
    response = _popup_response(ok=True, reason=None, status_code=200)
    _set_auth_cookie(response, token, settings)
    response.delete_cookie(key=STATE_COOKIE_NAME, path=STATE_COOKIE_PATH)
    return response


@router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    """Clear the session cookie."""
    response.delete_cookie(key=COOKIE_NAME, path="/")


@router.get("/me", response_model=MeResponse)
async def me(
    current_user: Annotated[UserRead, Depends(get_current_user)],
) -> MeResponse:
    """Return the currently authenticated user."""
    return MeResponse(user=current_user)
