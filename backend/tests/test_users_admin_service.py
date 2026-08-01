"""UserService backoffice methods + safety rails (needs Postgres)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.modules.users.exceptions import AdminSelfActionError, LastAdminError
from app.modules.users.schemas import UserAdminPatch, UserCreate
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


def _user(username: str, *, is_admin: bool = False) -> UserCreate:
    return UserCreate(username=username, password="password123", is_admin=is_admin)


@pytest.mark.integration
async def test_list_users_admin_includes_soft_deleted(session: AsyncSession) -> None:
    service = UserService(session)
    admin = await service.create(_user("boss", is_admin=True))
    victim = await service.create(_user("victim"))
    await service.soft_delete_user_admin(actor_id=admin.id, user_id=victim.id)
    items, total = await service.list_users_admin(limit=10, offset=0)
    assert total == 2
    by_name = {u.username: u for u in items}
    assert by_name["victim"].deleted_at is not None
    assert by_name["boss"].deleted_at is None
    assert by_name["boss"].google_linked is False


@pytest.mark.integration
async def test_self_demotion_blocked(session: AsyncSession) -> None:
    service = UserService(session)
    admin = await service.create(_user("boss", is_admin=True))
    with pytest.raises(AdminSelfActionError):
        await service.update_user_admin(
            actor_id=admin.id, user_id=admin.id, patch=UserAdminPatch(is_admin=False)
        )


@pytest.mark.integration
async def test_self_delete_blocked(session: AsyncSession) -> None:
    service = UserService(session)
    admin = await service.create(_user("boss", is_admin=True))
    with pytest.raises(AdminSelfActionError):
        await service.soft_delete_user_admin(actor_id=admin.id, user_id=admin.id)


@pytest.mark.integration
async def test_last_admin_cannot_be_demoted(session: AsyncSession) -> None:
    service = UserService(session)
    admin = await service.create(_user("only-admin", is_admin=True))
    with pytest.raises(LastAdminError):
        await service.update_user_admin(
            actor_id=uuid4(), user_id=admin.id, patch=UserAdminPatch(is_admin=False)
        )


@pytest.mark.integration
async def test_last_admin_cannot_be_deleted(session: AsyncSession) -> None:
    service = UserService(session)
    admin = await service.create(_user("only-admin", is_admin=True))
    with pytest.raises(LastAdminError):
        await service.soft_delete_user_admin(actor_id=uuid4(), user_id=admin.id)


@pytest.mark.integration
async def test_demoting_one_of_two_admins_works(session: AsyncSession) -> None:
    service = UserService(session)
    actor = await service.create(_user("boss", is_admin=True))
    other = await service.create(_user("other", is_admin=True))
    updated = await service.update_user_admin(
        actor_id=actor.id, user_id=other.id, patch=UserAdminPatch(is_admin=False)
    )
    assert updated.is_admin is False


@pytest.mark.integration
async def test_soft_delete_then_restore(session: AsyncSession) -> None:
    service = UserService(session)
    admin = await service.create(_user("boss", is_admin=True))
    victim = await service.create(_user("victim"))
    deleted = await service.soft_delete_user_admin(actor_id=admin.id, user_id=victim.id)
    assert deleted.deleted_at is not None
    restored = await service.restore_user_admin(actor_id=admin.id, user_id=victim.id)
    assert restored.deleted_at is None
