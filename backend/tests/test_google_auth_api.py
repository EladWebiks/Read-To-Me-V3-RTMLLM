"""End-to-end Google auth endpoint tests (needs Postgres; Google mocked via respx)."""

import json
import re
import time
from collections.abc import AsyncIterator, Callable
from typing import Any
from urllib.parse import parse_qsl
from uuid import uuid4

import jwt
import pytest
import respx
from app.core.config import get_settings
from app.core.deps import get_db
from app.main import app
from app.modules.auth.google import GOOGLE_JWKS_URL, GOOGLE_TOKEN_URL, reset_jwks_cache
from app.modules.auth.service import AuthService
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

CLIENT_ID = "test-client-id"
CLIENT_SECRET = "test-secret"
REDIRECT_URI = "http://test/api/auth/google/callback"

KID = "test-kid"
_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PRIVATE_PEM = _PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)


def _jwks() -> dict[str, Any]:
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(_PRIVATE_KEY.public_key()))
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    return {"keys": [jwk]}


def _id_token(client_id: str) -> str:
    now = int(time.time())
    payload = {
        "iss": "https://accounts.google.com",
        "aud": client_id,
        "sub": "google-sub-e2e",
        "email": "e2e@example.com",
        "email_verified": True,
        "iat": now,
        "exp": now + 600,
    }
    return jwt.encode(payload, _PRIVATE_PEM, algorithm="RS256", headers={"kid": KID})


def _make_db_override(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[], AsyncIterator[AsyncSession]]:
    async def _override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return _override_db


async def _clear_users(engine: AsyncEngine) -> None:
    # Guards against orphaned rows left by unrelated test modules violating
    # the users FK on DELETE. Mirrors the cleanup pattern used in
    # test_auth_api.py / test_google_login_service.py.
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM scraping_job_items"))
        await conn.execute(text("DELETE FROM scraping_jobs"))
        await conn.execute(text("DELETE FROM download_jobs"))
        await conn.execute(text("DELETE FROM reading_progress"))
        await conn.execute(text("DELETE FROM chapters"))
        await conn.execute(text("DELETE FROM user_books"))
        await conn.execute(text("DELETE FROM books"))
        await conn.execute(text("DELETE FROM cost_records"))
        await conn.execute(text("DELETE FROM llm_executions"))
        await conn.execute(text("DELETE FROM tool_calls"))
        await conn.execute(text("DELETE FROM conversation_messages"))
        await conn.execute(text("DELETE FROM conversations"))
        await conn.execute(text("DELETE FROM users"))


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    settings = get_settings()
    monkeypatch.setattr(settings.google, "client_id", CLIENT_ID)
    monkeypatch.setattr(settings.google, "client_secret", CLIENT_SECRET)
    monkeypatch.setattr(settings.google, "redirect_uri", REDIRECT_URI)
    reset_jwks_cache()
    engine = create_async_engine(settings.database.url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await _clear_users(engine)
    app.dependency_overrides[get_db] = _make_db_override(session_factory)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()
    await _clear_users(engine)
    await engine.dispose()


_PAYLOAD_RE = re.compile(r"var payload = (\{.*?\});")


def _popup_payload(response: Response) -> dict[str, Any]:
    """Parse the result payload out of the popup page.

    Asserting on the parsed object (rather than on raw substrings like
    '"ok": true') keeps these tests independent of json.dumps whitespace and
    of the \\uXXXX escaping the router applies before embedding the JSON in an
    inline <script>.
    """
    match = _PAYLOAD_RE.search(response.text)
    assert match is not None, response.text
    payload: dict[str, Any] = json.loads(match.group(1))
    return payload


def _assert_popup(response: Response, *, ok: bool, reason: str | None) -> None:
    assert response.headers["cache-control"] == "no-store"
    assert _popup_payload(response) == {"type": "rtm-google-auth", "ok": ok, "reason": reason}
    # Both delivery paths must be present: BroadcastChannel is the one that
    # survives Google's Cross-Origin-Opener-Policy severing window.opener;
    # opener.postMessage stays as the fallback for browsers without COOP swaps.
    assert "new BroadcastChannel('rtm-google-auth').postMessage(payload)" in response.text
    assert "window.opener.postMessage(payload, window.location.origin)" in response.text


def _state_cookie_header(response: Response) -> str:
    (header,) = [
        h for h in response.headers.get_list("set-cookie") if h.startswith("rtm_oauth_state=")
    ]
    return header


@pytest.mark.integration
async def test_google_login_redirects_with_state(client: AsyncClient) -> None:
    response = await client.get("/api/auth/google/login")
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "rtm_oauth_state" in response.cookies
    assert response.cookies["rtm_oauth_state"] in location

    header = _state_cookie_header(response)
    assert "HttpOnly" in header
    assert "Max-Age=600" in header
    assert "Path=/api/auth/google" in header
    assert "SameSite=lax" in header


@pytest.mark.integration
@respx.mock
async def test_google_callback_full_flow(client: AsyncClient) -> None:
    token_route = respx.post(GOOGLE_TOKEN_URL).mock(
        return_value=Response(200, json={"id_token": _id_token(CLIENT_ID)})
    )
    respx.get(GOOGLE_JWKS_URL).mock(return_value=Response(200, json=_jwks()))

    start = await client.get("/api/auth/google/login")
    state = start.cookies["rtm_oauth_state"]
    callback = await client.get(
        "/api/auth/google/callback", params={"code": "auth-code", "state": state}
    )
    assert callback.status_code == 200
    _assert_popup(callback, ok=True, reason=None)
    assert "rtm_token" in callback.cookies

    # Assert the *outbound* exchange, not just our handling of the canned
    # response: a wrong grant_type, a dropped client_secret or a redirect_uri
    # that doesn't match the one registered with Google would otherwise pass
    # the entire suite and fail only against the real provider.
    request = token_route.calls.last.request
    assert request.headers["content-type"] == "application/x-www-form-urlencoded"
    assert dict(parse_qsl(request.content.decode())) == {
        "code": "auth-code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "e2e@example.com"


@pytest.mark.integration
@respx.mock
async def test_google_callback_rejects_replayed_state(client: AsyncClient) -> None:
    """The state cookie is single-use: replaying a spent state must be refused."""
    token_route = respx.post(GOOGLE_TOKEN_URL).mock(
        return_value=Response(200, json={"id_token": _id_token(CLIENT_ID)})
    )
    respx.get(GOOGLE_JWKS_URL).mock(return_value=Response(200, json=_jwks()))

    start = await client.get("/api/auth/google/login")
    state = start.cookies["rtm_oauth_state"]
    first = await client.get(
        "/api/auth/google/callback", params={"code": "auth-code", "state": state}
    )
    assert first.status_code == 200
    assert token_route.call_count == 1

    replay = await client.get(
        "/api/auth/google/callback", params={"code": "auth-code", "state": state}
    )
    assert replay.status_code == 400
    _assert_popup(replay, ok=False, reason="state_mismatch")
    # The successful callback deleted the state cookie, so the replay can't
    # even reach the code exchange.
    assert token_route.call_count == 1


@pytest.mark.integration
@respx.mock
async def test_google_callback_rejects_state_mismatch(client: AsyncClient) -> None:
    token_route = respx.post(GOOGLE_TOKEN_URL).mock(
        return_value=Response(200, json={"id_token": _id_token(CLIENT_ID)})
    )
    await client.get("/api/auth/google/login")
    response = await client.get(
        "/api/auth/google/callback", params={"code": "auth-code", "state": "wrong"}
    )
    assert response.status_code == 400
    _assert_popup(response, ok=False, reason="state_mismatch")
    assert "rtm_token" not in response.cookies
    # The single most important property of this test: Google is never
    # contacted when the state doesn't match, since that would mean a code
    # exchange happened before the CSRF check.
    assert token_route.call_count == 0


@pytest.mark.integration
@respx.mock
async def test_google_callback_rejects_non_ascii_state(client: AsyncClient) -> None:
    """A non-ASCII state must yield the normal popup error, not an unhandled 500.

    secrets.compare_digest raises TypeError on non-ASCII str operands; without
    the ASCII guard this request escapes the popup contract entirely.
    """
    token_route = respx.post(GOOGLE_TOKEN_URL).mock(
        return_value=Response(200, json={"id_token": _id_token(CLIENT_ID)})
    )
    await client.get("/api/auth/google/login")
    response = await client.get(
        "/api/auth/google/callback", params={"code": "auth-code", "state": "é"}
    )
    assert response.status_code == 400
    _assert_popup(response, ok=False, reason="state_mismatch")
    assert token_route.call_count == 0


@pytest.mark.integration
async def test_google_callback_unexpected_error_is_still_a_popup(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An exception the endpoint doesn't map must still close the popup.

    Without the catch-all, the central JSON error body renders *inside* the
    popup, which then never posts a message and never closes.
    """

    async def _boom(self: AuthService, code: str) -> tuple[object, str]:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(AuthService, "login_with_google", _boom)

    start = await client.get("/api/auth/google/login")
    state = start.cookies["rtm_oauth_state"]
    response = await client.get(
        "/api/auth/google/callback", params={"code": "auth-code", "state": state}
    )
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("text/html")
    _assert_popup(response, ok=False, reason="internal_error")
    assert "rtm_token" not in response.cookies


async def _insert_google_sub_squatter(google_sub: str) -> None:
    """Soft-delete a user holding `google_sub`, invisible to every repository read.

    The unique index on google_sub is not partial, so provisioning still
    collides — the same IntegrityError two concurrent first-logins would hit,
    reachable deterministically through the real code path.
    """
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                # is_admin / membership come from their server defaults.
                "INSERT INTO users (id, username, email, google_sub, deleted_at)"
                " VALUES (:id, 'ghost', 'ghost@example.com', :sub, now())"
            ),
            {"id": str(uuid4()), "sub": google_sub},
        )
    await engine.dispose()


@pytest.mark.integration
@respx.mock
async def test_google_callback_db_error_is_still_a_popup(client: AsyncClient) -> None:
    """An IntegrityError must not resurface as a bare 500 during teardown.

    A failed flush poisons the request transaction; the catch-all returns a
    popup, and then the request-scoped session commits in dependency teardown.
    Unless the aborted transaction is rolled back first, that commit raises
    *after* the popup was produced and the client sees a plain 500 instead.
    """
    respx.post(GOOGLE_TOKEN_URL).mock(
        return_value=Response(200, json={"id_token": _id_token(CLIENT_ID)})
    )
    respx.get(GOOGLE_JWKS_URL).mock(return_value=Response(200, json=_jwks()))
    await _insert_google_sub_squatter("google-sub-e2e")

    start = await client.get("/api/auth/google/login")
    state = start.cookies["rtm_oauth_state"]
    response = await client.get(
        "/api/auth/google/callback", params={"code": "auth-code", "state": state}
    )
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("text/html")
    _assert_popup(response, ok=False, reason="internal_error")


@pytest.mark.integration
@respx.mock
async def test_google_callback_handles_google_auth_error(client: AsyncClient) -> None:
    """A GoogleAuthError from the service (e.g. a failed token exchange) must
    surface as ok: false with its machine-readable reason, and must not set
    the session cookie."""
    respx.post(GOOGLE_TOKEN_URL).mock(return_value=Response(400, json={"error": "invalid_grant"}))

    start = await client.get("/api/auth/google/login")
    state = start.cookies["rtm_oauth_state"]
    response = await client.get(
        "/api/auth/google/callback", params={"code": "auth-code", "state": state}
    )
    assert response.status_code == 400
    _assert_popup(response, ok=False, reason="token_exchange_failed")
    assert "rtm_token" not in response.cookies


@pytest.mark.integration
async def test_google_callback_handles_denied(client: AsyncClient) -> None:
    response = await client.get("/api/auth/google/callback", params={"error": "access_denied"})
    assert response.status_code == 400
    _assert_popup(response, ok=False, reason="google_denied")


@pytest.mark.integration
async def test_popup_reason_cannot_break_out_of_the_script_block(client: AsyncClient) -> None:
    """Every '<' in the embedded JSON is \\u003c-escaped.

    Guards the inline <script> against a reason value that would otherwise push
    the HTML tokenizer into the script-data-double-escaped state.
    """
    from app.modules.auth.router import _popup_response

    body = _popup_response(ok=False, reason="<!--<script>", status_code=400).body
    page = bytes(body).decode()
    assert "<!--" not in page
    assert page.count("<script>") == 1
    assert _popup_payload(Response(400, text=page))["reason"] == "<!--<script>"


@pytest.mark.integration
async def test_google_login_unconfigured_returns_503(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings().google, "client_id", None)
    response = await client.get("/api/auth/google/login")
    assert response.status_code == 503
