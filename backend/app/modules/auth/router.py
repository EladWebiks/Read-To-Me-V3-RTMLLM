"""Auth HTTP routes: Google login, logout, me."""

import json
import logging
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
from app.modules.users import membership_registry
from app.modules.users.schemas import UserRead

logger = logging.getLogger(__name__)

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
        secure=settings.auth.cookie_secure,
        samesite=settings.auth.cookie_samesite,
        max_age=settings.auth.jwt_expire_days * 24 * 60 * 60,
        path="/",
    )


STATE_COOKIE_NAME = "rtm_oauth_state"
STATE_COOKIE_PATH = "/api/auth/google"
STATE_TTL_SECONDS = 600


# Characters that are harmless in JSON but dangerous (or ambiguous) once the
# JSON is embedded in an inline <script>. `\uXXXX` escapes stay valid JSON, so
# the browser parses the identical object.
_SCRIPT_JSON_ESCAPES = {
    # Escaping every "<" — not just "</" — keeps the HTML tokenizer out of the
    # script-data-double-escaped state that a "<!--" + "<script" pair inside
    # the payload would otherwise trigger, from which "</script>" no longer
    # ends the element.
    "<": "\\u003c",
    # JS line terminators: legal raw inside a JSON string but not inside a JS
    # string literal. Belt-and-braces: json.dumps already escapes them while
    # ensure_ascii keeps its default value.
    "\u2028": "\\u2028",
    "\u2029": "\\u2029",
}


def _script_safe_json(payload: dict[str, object]) -> str:
    """Serialize `payload` for embedding inside an inline <script> block."""
    text = json.dumps(payload)
    for char, escape in _SCRIPT_JSON_ESCAPES.items():
        text = text.replace(char, escape)
    return text


def _popup_response(*, ok: bool, reason: str | None, status_code: int) -> HTMLResponse:
    """Tiny page that reports the result to the opener window and closes.

    Delivery is BroadcastChannel-first: accounts.google.com serves
    Cross-Origin-Opener-Policy: same-origin, which severs the popup/opener pair
    the moment the popup navigates to Google — this page usually loads with
    `window.opener === null`, and only a same-origin channel still reaches the
    app. The opener postMessage is kept as a fallback for user agents that do
    not perform COOP browsing-context-group swaps. `window.close()` may also be
    refused after the swap, hence the visible fallback text.
    """
    payload = _script_safe_json({"type": "rtm-google-auth", "ok": ok, "reason": reason})
    html = (
        "<!doctype html><html><body><script>"
        f"var payload = {payload};"
        "try { new BroadcastChannel('rtm-google-auth').postMessage(payload); } catch (err) {}"
        "if (window.opener) { window.opener.postMessage(payload, window.location.origin); }"
        "window.close();"
        "</script><p>You can close this window.</p></body></html>"
    )
    # The 200 variant carries a Set-Cookie with a live session JWT; no shared
    # cache or browser back/forward store may ever retain any of these pages.
    return HTMLResponse(
        content=html,
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


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
        secure=settings.auth.cookie_secure,
        # Hardcoded, not settings.auth.cookie_samesite: the callback is a cross-site
        # top-level navigation from accounts.google.com, which "Strict" cookies
        # are not sent on. If cookie_samesite were ever set to "strict", every
        # Google login would break with an opaque state_mismatch. "Lax" is
        # required here regardless of the session cookie's own SameSite policy.
        samesite="lax",
        max_age=STATE_TTL_SECONDS,
        path=STATE_COOKIE_PATH,
    )
    return response


def _state_matches(state: str | None, expected: str | None) -> bool:
    """Constant-time comparison of the callback state against the cookie.

    `secrets.compare_digest` raises TypeError on `str` operands that are not
    pure ASCII, so a crafted `?state=<non-ascii>` would otherwise escape the
    popup contract with an unhandled 500. A legitimate state is always
    `secrets.token_urlsafe` output, i.e. ASCII, so a non-ASCII operand simply
    cannot match.
    """
    if not state or not expected:
        return False
    if not state.isascii() or not expected.isascii():
        return False
    return secrets.compare_digest(state, expected)


async def _session_token_or_popup_error(service: AuthService, code: str) -> str | HTMLResponse:
    """Run the Google exchange, returning the session token or a popup error page.

    Split out of the endpoint so that *no* exception can escape as anything
    other than a popup response (see the endpoint's INVARIANT).
    """
    try:
        _user, token = await service.login_with_google(code)
    except GoogleAuthError as exc:
        logger.warning("google_auth_rejected reason=%s", exc.reason)
        return _popup_error(exc.reason, 400)
    except Exception as exc:
        # Reachable at least via GoogleNotConfiguredError (a sibling of
        # GoogleAuthError, not a subclass), an IntegrityError from two
        # concurrent first-logins racing the google_sub unique index, and
        # jwt.PyJWKError on an unparseable JWKS entry.
        #
        # Deliberately *not* logger.exception(): the formatted exception can
        # embed sensitive payload — e.g. a SQLAlchemy IntegrityError's message
        # includes the bound parameters, which here are the Google subject and
        # email claims. Only the exception class name is recorded, so neither
        # the authorization code nor any claim can reach the log.
        logger.error("google_callback_failed", extra={"error_type": type(exc).__name__})
        return _popup_error("internal_error", 500)
    return token


@router.get("/google/callback")
async def google_callback(
    request: Request,
    service: Annotated[AuthService, Depends(_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    """Finish the flow: validate state, exchange code, set session cookie.

    INVARIANT: *every* exit from this endpoint must be a popup response. This
    page only ever runs inside the sign-in popup, and the opener learns the
    outcome solely from the `postMessage` + `window.close()` that the popup
    body performs. Any other response (a central JSON error body, an unhandled
    500) renders in the popup, posts nothing, closes nothing, and leaves the
    user staring at a dead window until the opener's closed-poll eventually
    reports the misleading `popup_closed`. Hence the catch-all below.
    """
    if error or not code:
        return _popup_error("google_denied", 400)
    if not _state_matches(state, request.cookies.get(STATE_COOKIE_NAME)):
        return _popup_error("state_mismatch", 400)
    outcome = await _session_token_or_popup_error(service, code)
    if isinstance(outcome, HTMLResponse):
        return outcome
    response = _popup_response(ok=True, reason=None, status_code=200)
    _set_auth_cookie(response, outcome, settings)
    response.delete_cookie(key=STATE_COOKIE_NAME, path=STATE_COOKIE_PATH)
    return response


@router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    """Clear the session cookie."""
    response.delete_cookie(key=COOKIE_NAME, path="/")


@router.get("/me", response_model=MeResponse)
async def me(
    current_user: Annotated[UserRead, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MeResponse:
    """Return the currently authenticated user, with the tier's display label."""
    label = await membership_registry.label_for(session, current_user.membership)
    return MeResponse(user=current_user, membership_label=label)
