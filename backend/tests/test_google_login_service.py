"""Integration tests for Google login matching rules (needs Postgres)."""

from collections.abc import AsyncIterator

import pytest
from app.core.bootstrap import seed_admin_user
from app.core.config import get_settings
from app.modules.auth.exceptions import GoogleAuthError
from app.modules.auth.google import GoogleClaims, GoogleOAuthClient
from app.modules.auth.service import AuthService
from app.modules.users.exceptions import GoogleIdentityConflictError
from app.modules.users.membership import Membership
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
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
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


def _patch_google(
    monkeypatch: pytest.MonkeyPatch, sub: str, email: str, picture: str | None = None
) -> None:
    async def fake_exchange(self: GoogleOAuthClient, code: str) -> str:
        return "raw-id-token"

    async def fake_verify(self: GoogleOAuthClient, raw_token: str) -> GoogleClaims:
        return GoogleClaims(sub=sub, email=email, email_verified=True, picture=picture)

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
    await seed_admin_user(session)  # exactly how the row exists in production
    _patch_google(monkeypatch, "sub-admin", "owner@example.com")
    user, token = await _service(session).login_with_google("code")
    assert user.username == settings.auth.admin_username
    assert user.email == "owner@example.com"
    assert user.is_admin is True
    assert user.membership == Membership.FREE
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
async def test_repeat_login_refreshes_changed_picture(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    users = UserService(session)
    await users.create_from_google("sub-pic", "pic@example.com", "https://old.example.com/a.jpg")
    _patch_google(
        monkeypatch, "sub-pic", "pic@example.com", picture="https://new.example.com/b.jpg"
    )
    user, _ = await _service(session).login_with_google("code")
    assert user.picture_url == "https://new.example.com/b.jpg"


@pytest.mark.integration
async def test_missing_picture_claim_keeps_stored_picture(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    users = UserService(session)
    await users.create_from_google("sub-keep", "keep@example.com", "https://old.example.com/a.jpg")
    _patch_google(monkeypatch, "sub-keep", "keep@example.com")
    user, _ = await _service(session).login_with_google("code")
    assert user.picture_url == "https://old.example.com/a.jpg"


@pytest.mark.integration
async def test_first_login_stores_picture_on_admin_claim(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    await UserService(session).create(
        UserCreate(username=settings.auth.admin_username, password="password123")
    )
    _patch_google(
        monkeypatch, "sub-admin", "owner@example.com", picture="https://p.example.com/me"
    )
    user, _ = await _service(session).login_with_google("code")
    assert user.picture_url == "https://p.example.com/me"


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
    await seed_admin_user(session)
    await UserService(session).create_from_google("sub-one", "one@example.com")
    _patch_google(monkeypatch, "sub-two", "two@example.com")
    user, _ = await _service(session).login_with_google("code")
    assert user.username == "two"
    assert user.username != settings.auth.admin_username
    assert user.is_admin is False


@pytest.mark.integration
async def test_email_match_is_case_insensitive(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mixed-case stored email must still be matched (linked), not forked.

    Without case-insensitive matching the email rule misses and the login
    silently provisions a second, parallel account — stranding the original
    account's library.
    """
    users = UserService(session)
    await users.create_from_google("sub-first", "first@example.com")  # rule 3 spent
    await users.create(
        UserCreate(
            username="mixedcase",
            password="password123",
            email="Owner@Example.com",
        )
    )
    _patch_google(monkeypatch, "sub-mixed", "owner@example.com")
    user, _ = await _service(session).login_with_google("code")
    assert user.username == "mixedcase"
    assert await users.get_entity_by_google_sub("sub-mixed") is not None


@pytest.mark.integration
async def test_resolve_google_identity_raises_users_domain_conflict(
    session: AsyncSession,
) -> None:
    """The rule lives in `users`, so the guard raises the users-domain error.

    AuthService translates it back to GoogleAuthError("google_identity_conflict")
    — see test_email_match_conflicting_google_sub_rejected for the wire contract.
    """
    users = UserService(session)
    await users.create(
        UserCreate(username="direct", password="password123", email="d@example.com")
    )
    entity = await users.get_entity_by_email("d@example.com")
    assert entity is not None
    await users.link_google(entity, "sub-old", "d@example.com")
    with pytest.raises(GoogleIdentityConflictError):
        await users.resolve_google_identity(
            google_sub="sub-new", email="d@example.com", admin_username="admin"
        )


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
