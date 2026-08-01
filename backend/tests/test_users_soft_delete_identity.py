"""Soft-deleted identities stay reserved (needs Postgres).

The backoffice is the only writer of `users.deleted_at`, while `username`,
`email` and `google_sub` carry FULL unique constraints (not partial ones). A
soft-deleted row therefore still owns its identity values but is invisible to
every deleted-filtered lookup — so any insert that reuses them dies on the
unique index instead of on a typed domain error. These tests pin the
service-layer contract that closes that gap without a schema change.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from app.core.bootstrap import seed_admin_user
from app.core.config import get_settings
from app.modules.users.exceptions import UserAccountDisabledError, UserAlreadyExistsError
from app.modules.users.schemas import UserCreate
from app.modules.users.service import UserService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.dbcleanup import clear_users


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await clear_users(conn)
    async with factory() as sess:
        yield sess
        await sess.rollback()
    async with engine.begin() as conn:
        await clear_users(conn)
    await engine.dispose()


def _user(username: str, *, is_admin: bool = False, email: str | None = None) -> UserCreate:
    return UserCreate(username=username, password="password123", is_admin=is_admin, email=email)


@pytest.mark.integration
async def test_bootstrap_restores_soft_deleted_admin(session: AsyncSession) -> None:
    """The app must still boot after the bootstrap admin was soft-deleted.

    `seed_admin_user()` runs in the FastAPI lifespan, where nothing catches an
    IntegrityError: a soft-deleted row holding the configured admin username
    would crash-loop the app, and only manual SQL could recover it (the
    backoffice that could restore the row lives in the app that will not
    start). The bootstrap contract is "the configured admin exists and is
    usable", so it restores that row instead of trying to insert a second one.
    """
    settings = get_settings()
    service = UserService(session)
    seeded = await service.create(_user(settings.auth.admin_username, is_admin=True))
    actor = await service.create(_user("second-admin", is_admin=True))
    await service.soft_delete_user_admin(actor_id=actor.id, user_id=seeded.id)

    await seed_admin_user(session)

    active = await service.get_entity_by_username(settings.auth.admin_username)
    assert active is not None, "bootstrap admin must be active again"
    assert active.id == seeded.id, "the original row is restored, not duplicated"
    assert active.deleted_at is None


@pytest.mark.integration
async def test_create_rejects_a_soft_deleted_username(session: AsyncSession) -> None:
    """Re-registering a soft-deleted username is a typed 409, not an IntegrityError."""
    service = UserService(session)
    admin = await service.create(_user("boss", is_admin=True))
    victim = await service.create(_user("victim"))
    await service.soft_delete_user_admin(actor_id=admin.id, user_id=victim.id)
    with pytest.raises(UserAlreadyExistsError):
        await service.create(_user("victim"))


@pytest.mark.integration
async def test_google_relogin_by_sub_is_rejected_for_soft_deleted_user(
    session: AsyncSession,
) -> None:
    """A soft-deleted Google user signing in again is refused, never re-provisioned."""
    service = UserService(session)
    admin = await service.create(_user("boss", is_admin=True))
    ghost = await service.create_from_google("sub-ghost", "ghost@example.com")
    await service.soft_delete_user_admin(actor_id=admin.id, user_id=ghost.id)
    with pytest.raises(UserAccountDisabledError):
        await service.resolve_google_identity(
            google_sub="sub-ghost",
            email="ghost@example.com",
            admin_username="boss",
        )


@pytest.mark.integration
async def test_google_login_matching_a_soft_deleted_email_is_rejected(
    session: AsyncSession,
) -> None:
    """The email rule must not link (or fork around) a soft-deleted account."""
    service = UserService(session)
    admin = await service.create(_user("boss", is_admin=True))
    await service.create_from_google("sub-first", "first@example.com")  # admin-claim rule spent
    victim = await service.create(_user("emailuser", email="match@example.com"))
    await service.soft_delete_user_admin(actor_id=admin.id, user_id=victim.id)
    with pytest.raises(UserAccountDisabledError):
        await service.resolve_google_identity(
            google_sub="sub-linked",
            email="match@example.com",
            admin_username="boss",
        )


@pytest.mark.integration
async def test_unique_username_skips_a_soft_deleted_holder(session: AsyncSession) -> None:
    """Provisioning must not hand out a username a soft-deleted row still owns."""
    service = UserService(session)
    admin = await service.create(_user("boss", is_admin=True))
    taken = await service.create(_user("reader"))
    await service.soft_delete_user_admin(actor_id=admin.id, user_id=taken.id)
    provisioned = await service.create_from_google("sub-new", "reader@example.com")
    assert provisioned.username == "reader2"


@pytest.mark.integration
async def test_restore_then_relogin_works(session: AsyncSession) -> None:
    """Restore is the explicit admin action that re-opens sign-in."""
    service = UserService(session)
    admin = await service.create(_user("boss", is_admin=True))
    ghost = await service.create_from_google("sub-back", "back@example.com")
    await service.soft_delete_user_admin(actor_id=admin.id, user_id=ghost.id)
    await service.restore_user_admin(actor_id=admin.id, user_id=ghost.id)
    resolved = await service.resolve_google_identity(
        google_sub="sub-back",
        email="back@example.com",
        admin_username="boss",
    )
    assert resolved.id == ghost.id
