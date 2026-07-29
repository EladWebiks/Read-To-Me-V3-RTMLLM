"""Integration tests for Google login matching rules (needs Postgres)."""

from collections.abc import AsyncIterator

import pytest
from app.core.config import get_settings
from app.modules.auth.exceptions import GoogleAuthError
from app.modules.auth.google import GoogleClaims, GoogleOAuthClient
from app.modules.auth.service import AuthService
from app.modules.users.schemas import UserCreate
from app.modules.users.service import UserService
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


async def _clear_users(sess: AsyncSession) -> None:
    # Guards against orphaned rows left by unrelated test modules (e.g. tests
    # that seed a user + book without cleanup) violating the users FK on
    # DELETE. Mirrors the cleanup pattern used in test_auth_api.py /
    # test_library_api.py / test_reader_api.py.
    await sess.execute(text("DELETE FROM user_books"))
    await sess.execute(text("DELETE FROM users"))


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as sess:
        await _clear_users(sess)
        await sess.commit()
        yield sess
        await sess.rollback()
    async with factory() as cleanup:
        await _clear_users(cleanup)
        await cleanup.commit()
    await engine.dispose()


def _patch_google(monkeypatch: pytest.MonkeyPatch, sub: str, email: str) -> None:
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
        UserCreate(username=settings.admin_username, password="password123", role="admin")
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
        UserCreate(username=settings.admin_username, password="password123", role="admin")
    )
    await UserService(session).create_from_google("sub-one", "one@example.com")
    _patch_google(monkeypatch, "sub-two", "two@example.com")
    user, _ = await _service(session).login_with_google("code")
    assert user.username == "two"
    assert user.username != settings.admin_username


@pytest.mark.integration
async def test_email_match_conflicting_google_sub_rejected(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An email match already linked to a *different* Google sub must not be rebound."""
    users = UserService(session)
    await users.create(
        UserCreate(
            username="conflictuser",
            password="password123",
            email="x@example.com",
            role="user",
        )
    )
    entity = await users.get_entity_by_email("x@example.com")
    assert entity is not None
    await users.link_google(entity, "sub-old", "x@example.com")
    _patch_google(monkeypatch, "sub-new", "x@example.com")
    with pytest.raises(GoogleAuthError) as exc_info:
        await _service(session).login_with_google("code")
    assert exc_info.value.reason == "google_identity_conflict"
    reloaded = await users.get_entity_by_email("x@example.com")
    assert reloaded is not None
    assert reloaded.google_sub == "sub-old"
