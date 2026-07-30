"""Integration tests for users authority/membership fields (needs Postgres)."""

from collections.abc import AsyncIterator

import pytest
from app.core.bootstrap import seed_admin_user
from app.core.config import get_settings
from app.modules.users.membership import Membership
from app.modules.users.schemas import UserCreate
from app.modules.users.service import UserService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.dbcleanup import clear_users as _clear_users


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


@pytest.mark.integration
async def test_create_defaults_to_non_admin_free(session: AsyncSession) -> None:
    user = await UserService(session).create(UserCreate(username="plain", password="password123"))
    assert user.is_admin is False
    assert user.membership == Membership.FREE


@pytest.mark.integration
async def test_create_with_admin_flag(session: AsyncSession) -> None:
    user = await UserService(session).create(
        UserCreate(username="boss", password="password123", is_admin=True)
    )
    assert user.is_admin is True
    assert user.membership == Membership.FREE


@pytest.mark.integration
async def test_seed_admin_user_sets_is_admin(session: AsyncSession) -> None:
    await seed_admin_user(session)
    entity = await UserService(session).get_entity_by_username(get_settings().auth.admin_username)
    assert entity is not None
    assert entity.is_admin is True
    assert entity.membership == Membership.FREE


@pytest.mark.integration
async def test_google_provisioned_user_is_non_admin_free(session: AsyncSession) -> None:
    user = await UserService(session).create_from_google("sub-authz", "tier@example.com")
    assert user.is_admin is False
    assert user.membership == Membership.FREE
    assert user.password_hash is None
