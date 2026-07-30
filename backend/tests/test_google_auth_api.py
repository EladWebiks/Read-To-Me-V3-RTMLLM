"""End-to-end Google auth endpoint tests (needs Postgres; Google mocked via respx)."""

import json
import time
from collections.abc import AsyncIterator, Callable
from typing import Any

import jwt
import pytest
import respx
from app.core.config import get_settings
from app.core.deps import get_db
from app.main import app
from app.modules.auth.google import GOOGLE_JWKS_URL, GOOGLE_TOKEN_URL, reset_jwks_cache
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
    monkeypatch.setattr(settings, "google_client_id", "test-client-id")
    monkeypatch.setattr(settings, "google_client_secret", "test-secret")
    monkeypatch.setattr(
        settings,
        "google_redirect_uri",
        "http://test/api/auth/google/callback",
    )
    reset_jwks_cache()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await _clear_users(engine)
    app.dependency_overrides[get_db] = _make_db_override(session_factory)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()
    await _clear_users(engine)
    await engine.dispose()


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
    respx.post(GOOGLE_TOKEN_URL).mock(
        return_value=Response(200, json={"id_token": _id_token("test-client-id")})
    )
    respx.get(GOOGLE_JWKS_URL).mock(return_value=Response(200, json=_jwks()))

    start = await client.get("/api/auth/google/login")
    state = start.cookies["rtm_oauth_state"]
    callback = await client.get(
        "/api/auth/google/callback", params={"code": "auth-code", "state": state}
    )
    assert callback.status_code == 200
    assert '"ok": true' in callback.text
    assert "rtm_token" in callback.cookies

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "e2e@example.com"


@pytest.mark.integration
@respx.mock
async def test_google_callback_rejects_state_mismatch(client: AsyncClient) -> None:
    token_route = respx.post(GOOGLE_TOKEN_URL).mock(
        return_value=Response(200, json={"id_token": _id_token("test-client-id")})
    )
    await client.get("/api/auth/google/login")
    response = await client.get(
        "/api/auth/google/callback", params={"code": "auth-code", "state": "wrong"}
    )
    assert response.status_code == 400
    assert '"ok": false' in response.text
    assert "state_mismatch" in response.text
    assert "rtm_token" not in response.cookies
    # The single most important property of this test: Google is never
    # contacted when the state doesn't match, since that would mean a code
    # exchange happened before the CSRF check.
    assert token_route.call_count == 0


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
    assert '"ok": false' in response.text
    assert "token_exchange_failed" in response.text
    assert "rtm_token" not in response.cookies


@pytest.mark.integration
async def test_google_callback_handles_denied(client: AsyncClient) -> None:
    response = await client.get("/api/auth/google/callback", params={"error": "access_denied"})
    assert response.status_code == 400
    assert "google_denied" in response.text


@pytest.mark.integration
async def test_google_login_unconfigured_returns_503(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "google_client_id", None)
    response = await client.get("/api/auth/google/login")
    assert response.status_code == 503
