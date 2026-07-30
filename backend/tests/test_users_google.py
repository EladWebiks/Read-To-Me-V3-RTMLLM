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
    await service.create(UserCreate(username="reader", password="password123", role="admin"))
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
async def test_create_from_google_stores_picture(session: AsyncSession) -> None:
    service = UserService(session)
    user = await service.create_from_google(
        "sub-pic", "pic@example.com", "https://lh3.example.com/photo.jpg"
    )
    assert user.picture_url == "https://lh3.example.com/photo.jpg"


@pytest.mark.integration
async def test_link_google_stores_picture(session: AsyncSession) -> None:
    service = UserService(session)
    created = await service.create(
        UserCreate(username="pictured", password="password123", role="admin")
    )
    entity = await service.get_entity_by_id(created.id)
    assert entity is not None
    linked = await service.link_google(
        entity, "sub-pic-2", "pictured@example.com", "https://lh3.example.com/p2.jpg"
    )
    assert linked.picture_url == "https://lh3.example.com/p2.jpg"


@pytest.mark.integration
async def test_any_google_linked(session: AsyncSession) -> None:
    service = UserService(session)
    assert await service.any_google_linked() is False
    await service.create_from_google("sub-4", "someone@example.com")
    assert await service.any_google_linked() is True
