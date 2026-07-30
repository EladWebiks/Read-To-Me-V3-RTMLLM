# Google-only SSO Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace username/password login with Google sign-in via a backend-owned OAuth 2.0 authorization-code flow, triggered from a frontend button that opens a small popup window.

**Architecture:** Two new endpoints in the existing `auth` module drive the whole flow: `GET /api/auth/google/login` redirects a popup to Google's consent screen (with a CSRF `state` cookie); `GET /api/auth/google/callback` exchanges the code server-side, verifies the ID token against Google's JWKS, resolves/provisions the user, sets the existing `rtm_token` HttpOnly cookie, and returns a tiny HTML page that `postMessage`s the opener and closes itself. The frontend never loads Google JavaScript. Password login is removed last, after the frontend has switched over.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, httpx, PyJWT (+`cryptography` for RS256), respx (test mock), React 19, react-query, vitest.

**Spec:** `docs/superpowers/specs/2026-07-29-google-sso-design.md` (approved).

## Global Constraints

- All backend gates must pass per task: `uv run ruff check . --fix && uv run ruff format .`, `uv run mypy .`, `uv run pytest -m "unit or integration"` (run from `backend/`).
- Frontend gates: `npm run lint`, `npm run build`, `npm run test` (run from `frontend/`).
- Integration tests need Postgres/Redis/MinIO and `TEST_DATABASE_URL` pointing at a separate test DB — never the app DB.
- Commit with `bash scripts/git-commit-clean.sh /tmp/msg.txt` (write the message to `/tmp/msg.txt` first). **Never** add `Co-authored-by`/`Made-with` trailers. Verify with `git log -1 --format=%B`.
- Ruff limits: complexity ≤10, statements ≤20, branches ≤6, args ≤6. Frontend ESLint: file ≤110 lines, function ≤60 lines, nesting ≤3.
- Full type hints; strict mypy. No bare `except`. Never log tokens, codes, or claims.
- Module dependency direction: router → service → repository. `auth` service may call `users` **service** only (never its repository directly). `users` must not import from `auth` (pass primitives, not `GoogleClaims`, into `UserService`).
- Session cookie name is `rtm_token`; the flow must reuse `_set_auth_cookie` / `create_access_token` unchanged.
- Frontend API paths go through the `/api` proxy (Vite dev :5173, docker :3000) — the popup URL is the relative `/api/auth/google/login`, never an absolute backend URL.

---

### Task 1: Backend settings + dependencies + env plumbing

**Files:**
- Modify: `backend/app/core/config.py` (add 3 fields after the `admin_password` line)
- Modify: `backend/pyproject.toml` (deps)
- Modify: `.env.example`
- Modify: `docker-compose.yml` (backend **and** worker `environment` blocks)
- Modify: `README.md` (config table/section — add the three variables where other env vars are documented)
- Test: `backend/tests/test_google_config.py`

**Interfaces:**
- Produces: `Settings.google_client_id: str | None`, `Settings.google_client_secret: str | None`, `Settings.google_redirect_uri: str | None` (all default `None`). Later tasks read these.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_google_config.py
"""Google OAuth settings exist and default to unset."""

import pytest

from app.core.config import Settings


@pytest.mark.unit
def test_google_settings_default_to_none() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]  # pydantic-settings runtime kwarg
    )
    assert settings.google_client_id is None
    assert settings.google_client_secret is None
    assert settings.google_redirect_uri is None
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `uv run pytest tests/test_google_config.py -v`
Expected: FAIL with `AttributeError` (or pydantic `ValidationError`) — fields don't exist.

- [ ] **Step 3: Add the settings fields**

In `backend/app/core/config.py`, after the `admin_password` line, add:

```python
    # Google SSO (server-side authorization-code flow). All three are required
    # for login to work; endpoints return 503 when unset.
    google_client_id: str | None = None
    google_client_secret: str | None = None
    # Browser-facing callback, e.g. http://localhost:5173/api/auth/google/callback
    google_redirect_uri: str | None = None
```

- [ ] **Step 4: Add dependencies**

In `backend/pyproject.toml`:
- Change `"pyjwt>=2.10.0"` to `"pyjwt[crypto]>=2.10.0"` (RS256 verification needs `cryptography`).
- In `[dependency-groups] dev`, add `"respx>=0.22.0"`.

Run: `uv sync`

- [ ] **Step 5: Env plumbing**

In `.env.example`, extend the `# Auth` block:

```bash
# Google SSO (create an OAuth 2.0 Web client in Google Cloud console;
# register BOTH redirect URIs below as Authorized redirect URIs)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
# Dev (Vite): http://localhost:5173/api/auth/google/callback
# Docker:     http://localhost:3000/api/auth/google/callback
GOOGLE_REDIRECT_URI=http://localhost:5173/api/auth/google/callback
```

In `docker-compose.yml`, add to **both** the `backend` and `worker` `environment` blocks (keep them in sync, after the `ADMIN_PASSWORD` line in backend; after `SAPI_PROXY_ENABLED` in worker):

```yaml
      GOOGLE_CLIENT_ID: ${GOOGLE_CLIENT_ID:-}
      GOOGLE_CLIENT_SECRET: ${GOOGLE_CLIENT_SECRET:-}
      GOOGLE_REDIRECT_URI: ${GOOGLE_REDIRECT_URI:-http://localhost:3000/api/auth/google/callback}
```

In `README.md`, document the three variables next to the existing auth env docs, including a short "Google Cloud console setup" note: APIs & Services → Credentials → Create OAuth client ID → Web application → add both redirect URIs above.

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_google_config.py -v`
Expected: PASS

- [ ] **Step 7: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m unit
printf 'feat: add Google SSO settings and env plumbing\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
git log -1 --format=%B
```

---

### Task 2: Users model change + Alembic migration

**Files:**
- Modify: `backend/app/modules/users/models.py`
- Create: `backend/migrations/versions/<generated>_add_users_google_sub_nullable_password.py`

**Interfaces:**
- Produces: `User.google_sub: str | None` (unique, indexed), `User.password_hash: str | None` (now nullable). Later tasks rely on both.

- [ ] **Step 1: Update the model**

In `backend/app/modules/users/models.py`, change `password_hash` and add `google_sub` right after it:

```python
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_sub: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=True,
    )
```

- [ ] **Step 2: Generate the migration skeleton**

Run (from `backend/`): `uv run alembic revision -m "add users google_sub and nullable password_hash"`
The generated file already carries the correct `down_revision` (verify with `uv run alembic heads` — exactly one head).

- [ ] **Step 3: Fill in upgrade/downgrade**

Replace the generated `upgrade`/`downgrade` bodies:

```python
def upgrade() -> None:
    op.add_column("users", sa.Column("google_sub", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_users_google_sub"), "users", ["google_sub"], unique=True)
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=True,
    )


def downgrade() -> None:
    # Google-provisioned users have no password; use an unusable sentinel so
    # the NOT NULL constraint can be restored.
    op.execute(sa.text("UPDATE users SET password_hash = '' WHERE password_hash IS NULL"))
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.drop_index(op.f("ix_users_google_sub"), table_name="users")
    op.drop_column("users", "google_sub")
```

- [ ] **Step 4: Verify the migration is reversible**

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

Expected: all three succeed. Also apply it to the test DB so integration tests in later tasks see the new columns — run the same `upgrade head` with `DATABASE_URL` set to your `TEST_DATABASE_URL` value.

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m unit
printf 'feat: add users.google_sub and make password_hash nullable\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 3: Google OAuth client (`google.py`) + new auth exceptions

**Files:**
- Modify: `backend/app/modules/auth/exceptions.py`
- Create: `backend/app/modules/auth/google.py`
- Modify: `backend/app/core/exceptions.py` (register `GoogleNotConfiguredError` → 503)
- Test: `backend/tests/test_google_oauth.py`

**Interfaces:**
- Consumes: `Settings.google_client_id/google_client_secret/google_redirect_uri` (Task 1).
- Produces (used by Tasks 5–6):
  - `class GoogleClaims(BaseModel)`: `sub: str`, `email: EmailStr`, `email_verified: bool = False`, `name: str | None = None`
  - `class GoogleOAuthClient`: `__init__(settings: Settings)` (raises `GoogleNotConfiguredError` when any setting missing), `build_auth_url(state: str) -> str`, `async exchange_code(code: str) -> str` (returns raw ID token), `async verify_id_token(raw_token: str) -> GoogleClaims`
  - `class GoogleAuthError(AuthError)` with `.reason: str`; `class GoogleNotConfiguredError(AuthError)`
  - Module constants `GOOGLE_TOKEN_URL`, `GOOGLE_JWKS_URL` (tests mock these URLs)
  - `reset_jwks_cache() -> None` (test hook)

- [ ] **Step 1: Add exceptions**

Append to `backend/app/modules/auth/exceptions.py`:

```python
class GoogleAuthError(AuthError):
    """Google OAuth flow failed; `reason` is a machine-readable code."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class GoogleNotConfiguredError(AuthError):
    """Google OAuth settings are missing."""
```

- [ ] **Step 2: Write the failing tests**

```python
# backend/tests/test_google_oauth.py
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
        _env_file=None,  # type: ignore[call-arg]  # pydantic-settings runtime kwarg
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
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
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
    respx.post(GOOGLE_TOKEN_URL).mock(
        return_value=Response(200, json={"id_token": "raw-token"})
    )
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
async def test_verify_id_token_rejects_bad_claims(
    overrides: dict[str, Any], reason: str
) -> None:
    respx.get(GOOGLE_JWKS_URL).mock(return_value=Response(200, json=_jwks()))
    with pytest.raises(GoogleAuthError) as excinfo:
        await GoogleOAuthClient(_settings()).verify_id_token(_id_token(**overrides))
    assert excinfo.value.reason == reason
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_google_oauth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.modules.auth.google'`

- [ ] **Step 4: Implement `google.py`**

```python
# backend/app/modules/auth/google.py
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
```

- [ ] **Step 5: Register the 503 handler**

In `backend/app/core/exceptions.py`, import `GoogleNotConfiguredError` from `app.modules.auth.exceptions` and add to `_register_auth_handlers`:

```python
    @app.exception_handler(GoogleNotConfiguredError)
    async def _google_not_configured(
        _request: Request,
        _exc: GoogleNotConfiguredError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": "Google sign-in is not configured"},
        )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_google_oauth.py -v`
Expected: PASS (8 tests)

- [ ] **Step 7: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m unit
printf 'feat: add Google OAuth client with JWKS ID-token verification\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 4: UserService lookup/link/provision methods

**Files:**
- Modify: `backend/app/modules/users/repository.py`
- Modify: `backend/app/modules/users/service.py`
- Test: `backend/tests/test_users_google.py`

**Interfaces:**
- Consumes: `User.google_sub` / nullable `password_hash` (Task 2).
- Produces (used by Task 5) — all on `UserService`:
  - `async get_entity_by_email(email: str) -> User | None`
  - `async get_entity_by_google_sub(google_sub: str) -> User | None`
  - `async any_google_linked() -> bool`
  - `async link_google(user: User, google_sub: str, email: str) -> User` (stamps `google_sub`; fills `email` only if currently `None`)
  - `async create_from_google(google_sub: str, email: str) -> User` (username = sanitized email local-part, deduped with numeric suffix; role `"user"`; `password_hash=None`)

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_users_google.py
"""Integration tests for Google-related user lookups/provisioning (needs Postgres)."""

from collections.abc import AsyncIterator

import pytest
from app.core.config import get_settings
from app.modules.users.schemas import UserCreate
from app.modules.users.service import UserService
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as sess:
        await sess.execute(text("DELETE FROM users"))
        await sess.commit()
        yield sess
        await sess.rollback()
    async with factory() as cleanup:
        await cleanup.execute(text("DELETE FROM users"))
        await cleanup.commit()
    await engine.dispose()


@pytest.mark.integration
async def test_create_from_google_sets_identity(session: AsyncSession) -> None:
    service = UserService(session)
    user = await service.create_from_google("sub-1", "casual.reader@example.com")
    assert user.google_sub == "sub-1"
    assert user.email == "casual.reader@example.com"
    assert user.username == "casual.reader"
    assert user.password_hash is None
    assert user.role == "user"


@pytest.mark.integration
async def test_create_from_google_dedupes_username(session: AsyncSession) -> None:
    service = UserService(session)
    await service.create(
        UserCreate(username="reader", password="password123", role="admin")
    )
    user = await service.create_from_google("sub-2", "reader@example.com")
    assert user.username == "reader2"


@pytest.mark.integration
async def test_link_google_stamps_sub_and_backfills_email(
    session: AsyncSession,
) -> None:
    service = UserService(session)
    created = await service.create(
        UserCreate(username="admin", password="password123", role="admin")
    )
    entity = await service.get_entity_by_id(created.id)
    assert entity is not None
    linked = await service.link_google(entity, "sub-3", "admin@example.com")
    assert linked.google_sub == "sub-3"
    assert linked.email == "admin@example.com"
    assert await service.get_entity_by_google_sub("sub-3") is not None
    assert await service.get_entity_by_email("admin@example.com") is not None


@pytest.mark.integration
async def test_any_google_linked(session: AsyncSession) -> None:
    service = UserService(session)
    assert await service.any_google_linked() is False
    await service.create_from_google("sub-4", "someone@example.com")
    assert await service.any_google_linked() is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_users_google.py -v`
Expected: FAIL with `AttributeError: 'UserService' object has no attribute 'create_from_google'`

- [ ] **Step 3: Add repository methods**

Append to `UserRepository` in `backend/app/modules/users/repository.py`:

```python
    async def get_by_email(self, email: str) -> User | None:
        """Return a non-deleted user by email."""
        stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_google_sub(self, google_sub: str) -> User | None:
        """Return a non-deleted user by Google subject id."""
        stmt = select(User).where(
            User.google_sub == google_sub,
            User.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def any_google_linked(self) -> bool:
        """True when any non-deleted user has a Google identity."""
        stmt = (
            select(User.id)
            .where(User.google_sub.is_not(None), User.deleted_at.is_(None))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def save(self, user: User) -> User:
        """Flush pending changes on an already-tracked user."""
        await self._session.flush()
        await self._session.refresh(user)
        return user
```

- [ ] **Step 4: Add service methods**

Append to `UserService` in `backend/app/modules/users/service.py` (add `import re` at the top):

```python
    async def get_entity_by_email(self, email: str) -> User | None:
        """Return the ORM user by email (internal use)."""
        return await self._repo.get_by_email(email)

    async def get_entity_by_google_sub(self, google_sub: str) -> User | None:
        """Return the ORM user by Google subject id (internal use)."""
        return await self._repo.get_by_google_sub(google_sub)

    async def any_google_linked(self) -> bool:
        """True when any user already signed in with Google."""
        return await self._repo.any_google_linked()

    async def link_google(self, user: User, google_sub: str, email: str) -> User:
        """Attach a Google identity to an existing user."""
        user.google_sub = google_sub
        if user.email is None:
            user.email = email
        return await self._repo.save(user)

    async def create_from_google(self, google_sub: str, email: str) -> User:
        """Provision a new user from a verified Google identity."""
        username = await self._unique_username(email.split("@")[0])
        user = User(
            username=username,
            email=email,
            password_hash=None,
            google_sub=google_sub,
            role="user",
        )
        return await self._repo.add(user)

    async def _unique_username(self, base: str) -> str:
        """Sanitize the email local-part and dedupe with a numeric suffix."""
        cleaned = re.sub(r"[^a-z0-9._-]", "", base.lower())[:56] or "user"
        candidate = cleaned
        suffix = 1
        while await self._repo.get_by_username(candidate) is not None:
            suffix += 1
            candidate = f"{cleaned}{suffix}"
        return candidate
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_users_google.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add Google identity lookup/link/provision to users module\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 5: `AuthService.login_with_google` (matching rules)

**Files:**
- Modify: `backend/app/modules/auth/service.py`
- Test: `backend/tests/test_google_login_service.py`

**Interfaces:**
- Consumes: `GoogleOAuthClient`, `GoogleClaims` (Task 3); `UserService` methods (Task 4).
- Produces (used by Task 6): `async AuthService.login_with_google(code: str) -> tuple[UserRead, str]` — exchanges + verifies + resolves user per spec rules, returns `(user, jwt)` exactly like the old `login` did.

- [ ] **Step 1: Write the failing tests**

Tests patch the network edge (`exchange_code`, `verify_id_token`) and exercise the matching rules against the real DB:

```python
# backend/tests/test_google_login_service.py
"""Integration tests for Google login matching rules (needs Postgres)."""

from collections.abc import AsyncIterator

import pytest
from app.core.config import get_settings
from app.modules.auth.google import GoogleClaims, GoogleOAuthClient
from app.modules.auth.service import AuthService
from app.modules.users.schemas import UserCreate
from app.modules.users.service import UserService
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as sess:
        await sess.execute(text("DELETE FROM users"))
        await sess.commit()
        yield sess
        await sess.rollback()
    async with factory() as cleanup:
        await cleanup.execute(text("DELETE FROM users"))
        await cleanup.commit()
    await engine.dispose()


def _patch_google(
    monkeypatch: pytest.MonkeyPatch, sub: str, email: str
) -> None:
    async def fake_exchange(self: GoogleOAuthClient, code: str) -> str:
        return "raw-id-token"

    async def fake_verify(self: GoogleOAuthClient, raw_token: str) -> GoogleClaims:
        return GoogleClaims(sub=sub, email=email, email_verified=True)

    monkeypatch.setattr(GoogleOAuthClient, "__init__", lambda self, settings: None)
    monkeypatch.setattr(GoogleOAuthClient, "exchange_code", fake_exchange)
    monkeypatch.setattr(GoogleOAuthClient, "verify_id_token", fake_verify)


def _service(session: AsyncSession) -> AuthService:
    return AuthService(session, get_settings())


@pytest.mark.integration
async def test_first_google_login_claims_admin(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    await UserService(session).create(
        UserCreate(
            username=settings.admin_username, password="password123", role="admin"
        )
    )
    _patch_google(monkeypatch, "sub-admin", "owner@example.com")
    user, token = await _service(session).login_with_google("code")
    assert user.username == settings.admin_username
    assert user.email == "owner@example.com"
    assert token


@pytest.mark.integration
async def test_repeat_login_matches_by_sub(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    users = UserService(session)
    await users.create_from_google("sub-repeat", "repeat@example.com")
    _patch_google(monkeypatch, "sub-repeat", "changed-email@example.com")
    user, _ = await _service(session).login_with_google("code")
    assert user.email == "repeat@example.com"  # sub wins over email


@pytest.mark.integration
async def test_email_match_links_existing_user(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    users = UserService(session)
    await users.create_from_google("sub-first", "first@example.com")  # rule 3 spent
    await users.create(
        UserCreate(
            username="emailuser",
            password="password123",
            email="match@example.com",
            role="user",
        )
    )
    _patch_google(monkeypatch, "sub-linked", "match@example.com")
    user, _ = await _service(session).login_with_google("code")
    assert user.username == "emailuser"


@pytest.mark.integration
async def test_second_google_account_provisions_new_user(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    await UserService(session).create(
        UserCreate(
            username=settings.admin_username, password="password123", role="admin"
        )
    )
    await UserService(session).create_from_google("sub-one", "one@example.com")
    _patch_google(monkeypatch, "sub-two", "two@example.com")
    user, _ = await _service(session).login_with_google("code")
    assert user.username == "two"
    assert user.username != settings.admin_username
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_google_login_service.py -v`
Expected: FAIL with `AttributeError: 'AuthService' object has no attribute 'login_with_google'`

- [ ] **Step 3: Implement**

In `backend/app/modules/auth/service.py`, add imports:

```python
from app.modules.auth.google import GoogleClaims, GoogleOAuthClient
from app.modules.users.models import User
```

Add to `AuthService`:

```python
    async def login_with_google(self, code: str) -> tuple[UserRead, str]:
        """Complete the Google code flow and return (user, jwt)."""
        client = GoogleOAuthClient(self._settings)
        id_token = await client.exchange_code(code)
        claims = await client.verify_id_token(id_token)
        user = await self._resolve_google_user(claims)
        token = create_access_token(
            user_id=user.id,
            username=user.username,
            settings=self._settings,
        )
        return UserRead.model_validate(user), token

    async def _resolve_google_user(self, claims: GoogleClaims) -> User:
        """Spec matching rules: sub → email → first-login admin claim → provision."""
        email = str(claims.email)
        user = await self._users.get_entity_by_google_sub(claims.sub)
        if user is not None:
            return user
        by_email = await self._users.get_entity_by_email(email)
        if by_email is not None:
            return await self._users.link_google(by_email, claims.sub, email)
        if not await self._users.any_google_linked():
            admin = await self._users.get_entity_by_username(
                self._settings.admin_username
            )
            if admin is not None:
                return await self._users.link_google(admin, claims.sub, email)
        return await self._users.create_from_google(claims.sub, email)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_google_login_service.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add AuthService.login_with_google with account matching rules\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 6: Google auth endpoints + popup page

**Files:**
- Modify: `backend/app/modules/auth/router.py`
- Test: `backend/tests/test_google_auth_api.py`

**Interfaces:**
- Consumes: `AuthService.login_with_google` (Task 5), `GoogleOAuthClient.build_auth_url` (Task 3), existing `_set_auth_cookie`.
- Produces:
  - `GET /api/auth/google/login` → 302 to Google, sets `rtm_oauth_state` cookie (HttpOnly, 10 min, path `/api/auth/google`).
  - `GET /api/auth/google/callback?code&state` → HTML popup page; on success sets `rtm_token` cookie. Page posts `{type: 'rtm-google-auth', ok: boolean, reason: string | null}` to `window.opener` with `window.location.origin` as target origin, then closes. The frontend (Task 8) depends on this exact message shape.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_google_auth_api.py
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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
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
    session_factory = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM users"))
    app.dependency_overrides[get_db] = _make_db_override(session_factory)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM users"))
    await engine.dispose()


@pytest.mark.integration
async def test_google_login_redirects_with_state(client: AsyncClient) -> None:
    response = await client.get("/api/auth/google/login")
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "rtm_oauth_state" in response.cookies
    assert response.cookies["rtm_oauth_state"] in location


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
async def test_google_callback_rejects_state_mismatch(client: AsyncClient) -> None:
    await client.get("/api/auth/google/login")
    response = await client.get(
        "/api/auth/google/callback", params={"code": "auth-code", "state": "wrong"}
    )
    assert response.status_code == 400
    assert '"ok": false' in response.text
    assert "state_mismatch" in response.text
    assert "rtm_token" not in response.cookies


@pytest.mark.integration
async def test_google_callback_handles_denied(client: AsyncClient) -> None:
    response = await client.get(
        "/api/auth/google/callback", params={"error": "access_denied"}
    )
    assert response.status_code == 400
    assert "google_denied" in response.text


@pytest.mark.integration
async def test_google_login_unconfigured_returns_503(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "google_client_id", None)
    response = await client.get("/api/auth/google/login")
    assert response.status_code == 503
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_google_auth_api.py -v`
Expected: FAIL — 404 for `/api/auth/google/login` (route missing).

- [ ] **Step 3: Implement the routes**

In `backend/app/modules/auth/router.py`, add imports at the top:

```python
import json
import secrets

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.modules.auth.exceptions import GoogleAuthError
from app.modules.auth.google import GoogleOAuthClient
```

Add below `_set_auth_cookie`:

```python
STATE_COOKIE_NAME = "rtm_oauth_state"
STATE_COOKIE_PATH = "/api/auth/google"
STATE_TTL_SECONDS = 600


def _popup_response(*, ok: bool, reason: str | None, status_code: int) -> HTMLResponse:
    """Tiny page that reports the result to the opener window and closes."""
    payload = json.dumps(
        {"type": "rtm-google-auth", "ok": ok, "reason": reason}, indent=1
    )
    html = (
        "<!doctype html><html><body><script>"
        f"if (window.opener) {{ window.opener.postMessage({payload}, window.location.origin); }}"
        "window.close();"
        "</script><p>You can close this window.</p></body></html>"
    )
    return HTMLResponse(content=html, status_code=status_code)


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
        samesite=settings.cookie_samesite,
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
        return _popup_response(ok=False, reason="google_denied", status_code=400)
    expected = request.cookies.get(STATE_COOKIE_NAME)
    if not state or not expected or state != expected:
        return _popup_response(ok=False, reason="state_mismatch", status_code=400)
    try:
        _user, token = await service.login_with_google(code)
    except GoogleAuthError as exc:
        return _popup_response(ok=False, reason=exc.reason, status_code=400)
    response = _popup_response(ok=True, reason=None, status_code=200)
    _set_auth_cookie(response, token, settings)
    response.delete_cookie(key=STATE_COOKIE_NAME, path=STATE_COOKIE_PATH)
    return response
```

Note: `json.dumps(..., indent=1)` makes the payload contain `"ok": true` with a space, matching the test assertions; `GoogleNotConfiguredError` propagates from `GoogleOAuthClient(settings)` to the global 503 handler registered in Task 3.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_google_auth_api.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat: add Google OAuth login/callback endpoints with popup result page\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 7: Frontend — popup logic + API/type cleanup

**Files:**
- Create: `frontend/src/features/auth/logic/googlePopup.ts`
- Create: `frontend/src/features/auth/logic/googlePopup.test.ts`
- Modify: `frontend/src/features/auth/api/api.ts` (remove `login`, add `GOOGLE_LOGIN_URL`)
- Modify: `frontend/src/features/auth/types.ts` (remove `LoginResponse`)

**Interfaces:**
- Consumes: the callback page's message `{type: 'rtm-google-auth', ok, reason}` (Task 6).
- Produces (used by Task 8):
  - `const GOOGLE_LOGIN_URL = '/api/auth/google/login'` (from `@/features/auth/api`)
  - `type PopupResult = { status: 'success' } | { status: 'error'; reason: string }`
  - `openGooglePopup(url: string, onResult: (result: PopupResult) => void): () => void` — opens the popup, resolves exactly once via `onResult` (message, blocked, or closed-early), returns a cleanup function.

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/src/features/auth/logic/googlePopup.test.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { openGooglePopup, type PopupResult } from './googlePopup'

type FakePopup = { closed: boolean }

function fakePopup(): FakePopup {
  return { closed: false }
}

function mockOpen(popup: FakePopup | null) {
  // Only `closed` is read by the implementation; strict TS needs the double cast.
  return vi.spyOn(window, 'open').mockReturnValue(popup as unknown as Window)
}

function dispatchAuthMessage(data: unknown, origin = window.location.origin) {
  window.dispatchEvent(new MessageEvent('message', { data, origin }))
}

describe('openGooglePopup', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('reports success when the popup posts ok:true', () => {
    mockOpen(fakePopup())
    const results: PopupResult[] = []
    openGooglePopup('/api/auth/google/login', (r) => results.push(r))
    dispatchAuthMessage({ type: 'rtm-google-auth', ok: true, reason: null })
    expect(results).toEqual([{ status: 'success' }])
  })

  it('reports the backend reason when ok:false', () => {
    mockOpen(fakePopup())
    const results: PopupResult[] = []
    openGooglePopup('/api/auth/google/login', (r) => results.push(r))
    dispatchAuthMessage({ type: 'rtm-google-auth', ok: false, reason: 'state_mismatch' })
    expect(results).toEqual([{ status: 'error', reason: 'state_mismatch' }])
  })

  it('ignores messages from other origins and unrelated shapes', () => {
    mockOpen(fakePopup())
    const results: PopupResult[] = []
    openGooglePopup('/api/auth/google/login', (r) => results.push(r))
    dispatchAuthMessage({ type: 'rtm-google-auth', ok: true }, 'https://evil.example')
    dispatchAuthMessage({ hello: 'world' })
    expect(results).toEqual([])
  })

  it('reports popup_blocked when window.open returns null', () => {
    mockOpen(null)
    const results: PopupResult[] = []
    openGooglePopup('/api/auth/google/login', (r) => results.push(r))
    expect(results).toEqual([{ status: 'error', reason: 'popup_blocked' }])
  })

  it('reports popup_closed when the window closes without a message', () => {
    const popup = fakePopup()
    mockOpen(popup)
    const results: PopupResult[] = []
    openGooglePopup('/api/auth/google/login', (r) => results.push(r))
    popup.closed = true
    vi.advanceTimersByTime(600)
    expect(results).toEqual([{ status: 'error', reason: 'popup_closed' }])
  })

  it('settles only once', () => {
    const popup = fakePopup()
    mockOpen(popup)
    const results: PopupResult[] = []
    openGooglePopup('/api/auth/google/login', (r) => results.push(r))
    dispatchAuthMessage({ type: 'rtm-google-auth', ok: true, reason: null })
    popup.closed = true
    vi.advanceTimersByTime(600)
    expect(results).toHaveLength(1)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `frontend/`): `npm run test -- googlePopup`
Expected: FAIL — module `./googlePopup` not found.

- [ ] **Step 3: Implement `googlePopup.ts`**

```typescript
// frontend/src/features/auth/logic/googlePopup.ts
export type GoogleAuthMessage = {
  type: 'rtm-google-auth'
  ok: boolean
  reason: string | null
}

export type PopupResult = { status: 'success' } | { status: 'error'; reason: string }

const POPUP_NAME = 'rtm-google-auth'
const POPUP_FEATURES = 'width=500,height=600,popup=yes'
const CLOSED_POLL_MS = 500

function isGoogleAuthMessage(data: unknown): data is GoogleAuthMessage {
  return (
    typeof data === 'object' &&
    data !== null &&
    (data as { type?: unknown }).type === 'rtm-google-auth'
  )
}

export function openGooglePopup(
  url: string,
  onResult: (result: PopupResult) => void,
): () => void {
  const popup = window.open(url, POPUP_NAME, POPUP_FEATURES)
  if (!popup) {
    onResult({ status: 'error', reason: 'popup_blocked' })
    return () => {}
  }
  let settled = false
  const cleanup = () => {
    window.removeEventListener('message', onMessage)
    window.clearInterval(timer)
  }
  const settle = (result: PopupResult) => {
    if (settled) return
    settled = true
    cleanup()
    onResult(result)
  }
  const onMessage = (event: MessageEvent) => {
    if (event.origin !== window.location.origin) return
    if (!isGoogleAuthMessage(event.data)) return
    settle(
      event.data.ok
        ? { status: 'success' }
        : { status: 'error', reason: event.data.reason ?? 'unknown' },
    )
  }
  const timer = window.setInterval(() => {
    if (popup.closed) settle({ status: 'error', reason: 'popup_closed' })
  }, CLOSED_POLL_MS)
  window.addEventListener('message', onMessage)
  return cleanup
}
```

- [ ] **Step 4: Update the API module and types**

Replace `frontend/src/features/auth/api/api.ts` with:

```typescript
import { apiGet, apiPost } from '@/shared/lib/api'
import type { MeResponse } from '@/features/auth/types'

export const GOOGLE_LOGIN_URL = '/api/auth/google/login'

export function fetchMe(): Promise<MeResponse> {
  return apiGet<MeResponse>('/api/auth/me')
}

export function logout(): Promise<void> {
  return apiPost<void>('/api/auth/logout')
}
```

In `frontend/src/features/auth/types.ts`, delete the `LoginResponse` type (keep `User` and `MeResponse`).

Note: `frontend/src/features/auth/hooks/hooks.ts` still imports `login` at this point — Task 8 fixes it; `npm run build` is expected to fail until then, so this task's gate is tests only.

- [ ] **Step 5: Run tests to verify they pass**

Run: `npm run test -- googlePopup`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
printf 'feat: add Google popup flow logic and login API cleanup\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 8: Frontend — `useGoogleLogin` hook, GoogleButton, LoginPage rewrite

**Files:**
- Create: `frontend/src/features/auth/hooks/useGoogleLogin.ts`
- Modify: `frontend/src/features/auth/hooks/hooks.ts` (remove `useLogin` and the `login` import)
- Modify: `frontend/src/features/auth/hooks/index.ts`
- Create: `frontend/src/features/auth/components/GoogleButton.tsx`
- Modify: `frontend/src/features/auth/components/LoginPage.tsx` (full rewrite)

**Interfaces:**
- Consumes: `openGooglePopup`, `PopupResult`, `GOOGLE_LOGIN_URL` (Task 7); `meQueryKey` (existing, in `hooks.ts`).
- Produces: `useGoogleLogin(): { state: GoogleLoginState; start: () => void }` where `GoogleLoginState = { status: 'idle' | 'pending' } | { status: 'error'; reason: string }`.

- [ ] **Step 1: Implement `useGoogleLogin.ts`**

```typescript
// frontend/src/features/auth/hooks/useGoogleLogin.ts
import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { GOOGLE_LOGIN_URL } from '@/features/auth/api'
import { openGooglePopup, type PopupResult } from '@/features/auth/logic/googlePopup'
import { meQueryKey } from './hooks'

export type GoogleLoginState =
  | { status: 'idle' | 'pending' }
  | { status: 'error'; reason: string }

export function useGoogleLogin() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [state, setState] = useState<GoogleLoginState>({ status: 'idle' })
  const cleanupRef = useRef<(() => void) | null>(null)

  useEffect(() => () => cleanupRef.current?.(), [])

  const start = useCallback(() => {
    cleanupRef.current?.()
    setState({ status: 'pending' })
    cleanupRef.current = openGooglePopup(GOOGLE_LOGIN_URL, (result: PopupResult) => {
      if (result.status === 'success') {
        void queryClient.invalidateQueries({ queryKey: meQueryKey })
        void navigate('/reader', { replace: true })
        return
      }
      setState({ status: 'error', reason: result.reason })
    })
  }, [navigate, queryClient])

  return { state, start }
}
```

- [ ] **Step 2: Remove `useLogin` from `hooks.ts` and update the barrel**

In `frontend/src/features/auth/hooks/hooks.ts`: delete the entire `useLogin` function, and change the api import line to `import { fetchMe, logout } from '@/features/auth/api'`.

Replace `frontend/src/features/auth/hooks/index.ts` with:

```typescript
export * from './hooks'
export * from './useGoogleLogin'
```

- [ ] **Step 3: Implement `GoogleButton.tsx`**

```tsx
// frontend/src/features/auth/components/GoogleButton.tsx
type GoogleButtonProps = {
  disabled: boolean
  onClick: () => void
}

export function GoogleButton({ disabled, onClick }: GoogleButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="flex w-full items-center justify-center gap-3 rounded border border-border bg-background px-3 py-2 text-sm font-medium text-foreground hover:bg-accent disabled:opacity-60"
    >
      <GoogleLogo />
      {disabled ? 'Waiting for Google…' : 'Sign in with Google'}
    </button>
  )
}

function GoogleLogo() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  )
}
```

- [ ] **Step 4: Rewrite `LoginPage.tsx`**

```tsx
// frontend/src/features/auth/components/LoginPage.tsx
import { useGoogleLogin } from '@/features/auth/hooks'
import { GoogleButton } from './GoogleButton'

const ERROR_MESSAGES: Record<string, string> = {
  popup_blocked: 'Your browser blocked the sign-in window. Allow popups and try again.',
  popup_closed: 'The sign-in window was closed before finishing.',
  email_not_verified: 'This Google account has no verified email address.',
  google_denied: 'Google sign-in was cancelled.',
}
const FALLBACK_ERROR = 'Google sign-in failed. Please try again.'

export function LoginPage() {
  const { state, start } = useGoogleLogin()
  const errorMessage =
    state.status === 'error' ? (ERROR_MESSAGES[state.reason] ?? FALLBACK_ERROR) : null

  return (
    <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-4">
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">Sign in to RTM</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Continue with your Google account.
      </p>
      <GoogleButton disabled={state.status === 'pending'} onClick={start} />
      {errorMessage ? (
        <p className="mt-4 text-sm text-destructive">{errorMessage}</p>
      ) : null}
    </div>
  )
}
```

- [ ] **Step 5: Verify frontend gates**

Run (from `frontend/`):

```bash
npm run lint
npm run build
npm run test
```

Expected: all pass (build succeeding proves the `login`/`LoginResponse` removals left no dangling imports).

- [ ] **Step 6: Manual smoke test (requires real Google credentials in `.env`)**

Start backend + frontend (`uv run uvicorn app.main:app --reload --port 8000`, `npm run dev`), open `http://localhost:5173/login`, click the button: a ~500×600 popup opens on Google's account chooser; after choosing an account the popup closes and the app navigates to `/reader`. If you skip this (no credentials yet), note it in the commit-adjacent PR/summary — do not claim it was verified.

- [ ] **Step 7: Commit**

```bash
printf 'feat: replace password login UI with Google sign-in popup\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 9: Remove password login from the backend

**Files:**
- Modify: `backend/app/modules/auth/router.py` (delete `/login` route)
- Modify: `backend/app/modules/auth/service.py` (delete `login`)
- Modify: `backend/app/modules/auth/schemas.py` (delete `LoginRequest`, `LoginResponse`)
- Modify: `backend/app/modules/auth/exceptions.py` (delete `InvalidCredentialsError`)
- Modify: `backend/app/core/security.py` (delete `verify_password`)
- Modify: `backend/app/core/exceptions.py` (delete the `InvalidCredentialsError` handler + import)
- Modify: `backend/tests/test_auth_api.py` (rewrite login-dependent tests)

**Interfaces:**
- Consumes: nothing new.
- Produces: `POST /api/auth/login` no longer exists (404). `logout`/`me` unchanged. `hash_password` and admin seeding (`seed_admin_user`) remain — the admin row anchors the first-login claim rule.

- [ ] **Step 1: Rewrite the auth API tests first**

Replace the two test functions at the bottom of `backend/tests/test_auth_api.py` (keep the fixtures/helpers) with:

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_me_and_logout_with_minted_token(client: AsyncClient) -> None:
    """A directly-minted session token works for /me; logout clears it."""
    from app.core.security import create_access_token
    from app.modules.users.service import UserService

    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        user = await UserService(session).get_entity_by_username(
            settings.admin_username
        )
        assert user is not None
        token = create_access_token(
            user_id=user.id, username=user.username, settings=settings
        )
    await engine.dispose()

    client.cookies.set("rtm_token", token)
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == settings.admin_username

    logout = await client.post("/api/auth/logout")
    assert logout.status_code == 204


@pytest.mark.integration
@pytest.mark.asyncio
async def test_password_login_is_gone(client: AsyncClient) -> None:
    """The old password endpoint no longer exists."""
    settings = get_settings()
    response = await client.post(
        "/api/auth/login",
        json={
            "username": settings.admin_username,
            "password": settings.admin_password,
        },
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify the removal test fails**

Run: `uv run pytest tests/test_auth_api.py -v`
Expected: `test_password_login_is_gone` FAILS (endpoint still returns 200); the minted-token test passes.

- [ ] **Step 3: Delete the password path**

- `router.py`: remove the `login` route function and the now-unused `LoginRequest`/`LoginResponse` imports.
- `service.py`: remove `AuthService.login` and the now-unused `verify_password` / `InvalidCredentialsError` imports.
- `schemas.py`: remove `LoginRequest` and `LoginResponse` (keep `MeResponse`).
- `exceptions.py`: remove `InvalidCredentialsError`.
- `core/security.py`: remove `verify_password` and the now-unused `VerifyMismatchError` import.
- `core/exceptions.py`: remove the `_invalid_credentials` handler and drop `InvalidCredentialsError` from the import.

- [ ] **Step 4: Run the full backend suite**

Run: `uv run pytest -m "unit or integration"`
Expected: PASS, including `test_password_login_is_gone`.

- [ ] **Step 5: Gates + commit**

```bash
uv run ruff check . --fix && uv run ruff format . && uv run mypy . && uv run pytest -m "unit or integration"
printf 'feat!: remove password login; Google SSO is the only sign-in\n' > /tmp/msg.txt
git add -A
bash scripts/git-commit-clean.sh /tmp/msg.txt
```

---

### Task 10: Final verification sweep

**Files:** none new — verification only.

- [ ] **Step 1: Full backend gates**

From `backend/`:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy .
uv run pytest -m "unit or integration"
```

Expected: all clean.

- [ ] **Step 2: Full frontend gates**

From `frontend/`:

```bash
npm run lint
npm run build
npm run test
```

Expected: all clean.

- [ ] **Step 3: Docker config sanity**

`docker compose config` parses; confirm `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` appear in both `backend` and `worker` resolved environments.

- [ ] **Step 4: Migration round-trip on a scratch check**

```bash
uv run alembic downgrade -1 && uv run alembic upgrade head
```

Expected: succeeds.

- [ ] **Step 5: Commit any stragglers and summarize**

Report per superpowers:verification-before-completion — show actual command output for each gate before claiming done. Then follow superpowers:finishing-a-development-branch.
