"""Integration tests for app_settings tables (needs Postgres)."""

from collections.abc import AsyncIterator

import pytest
from app.core.config import get_settings
from app.modules.runtime_config.models import AppSetting, AppSettingAudit
from app.modules.users.models import User
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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


async def _make_admin(session: AsyncSession) -> User:
    user = User(
        username="cfg-admin",
        email="cfg-admin@example.com",
        password_hash=None,
        google_sub="cfg-admin-sub",
        is_admin=True,
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.integration
async def test_setting_and_audit_round_trip(session: AsyncSession) -> None:
    admin = await _make_admin(session)
    session.add(AppSetting(key="llm_runtime.max_tool_iters", value=4, updated_by=admin.id))
    session.add(
        AppSettingAudit(
            key="llm_runtime.max_tool_iters",
            action="set",
            old_value=None,
            new_value=4,
            actor_id=admin.id,
        )
    )
    await session.commit()

    row = (await session.execute(select(AppSetting))).scalar_one()
    assert row.value == 4
    assert row.updated_by == admin.id
    assert row.created_at is not None
    audit = (await session.execute(select(AppSettingAudit))).scalar_one()
    assert audit.action == "set"
    assert audit.new_value == 4


@pytest.mark.integration
async def test_key_is_unique(session: AsyncSession) -> None:
    admin = await _make_admin(session)
    session.add(AppSetting(key="scrape.delay_seconds", value=1.0, updated_by=admin.id))
    await session.flush()
    session.add(AppSetting(key="scrape.delay_seconds", value=2.0, updated_by=admin.id))
    with pytest.raises(IntegrityError):
        await session.flush()
