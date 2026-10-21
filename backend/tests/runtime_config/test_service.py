"""Integration tests for override writes, auditing, and effective layering."""

from collections.abc import AsyncIterator

import pytest
from app.core.config import LlmRuntimeSettings, get_settings
from app.modules.runtime_config import cache
from app.modules.runtime_config.exceptions import (
    OverrideNotFoundError,
    SettingValueInvalidError,
    UnknownSettingKeyError,
)
from app.modules.runtime_config.models import AppSetting, AppSettingAudit
from app.modules.runtime_config.registry import TUNABLE_FIELDS
from app.modules.runtime_config.service import RuntimeConfigService
from app.modules.users.models import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.dbcleanup import clear_users
from tests.factories import make_settings


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    cache.invalidate()


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


@pytest.fixture
async def admin(session: AsyncSession) -> User:
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


def _service(session: AsyncSession) -> RuntimeConfigService:
    return RuntimeConfigService(session, make_settings())


@pytest.mark.integration
async def test_empty_table_means_env_values(session: AsyncSession) -> None:
    service = _service(session)
    runtime = await service.get_effective(LlmRuntimeSettings)
    assert runtime.max_tool_iters == 6
    effective = await service.effective_settings()
    assert effective.llm_runtime.max_turn_cost_usd == 0.05


@pytest.mark.integration
async def test_set_override_wins_and_clear_restores(session: AsyncSession, admin: User) -> None:
    service = _service(session)
    override = await service.set_override("llm_runtime.max_tool_iters", 2, admin.id)
    assert override.value == 2
    assert override.updated_by == admin.id
    runtime = await service.get_effective(LlmRuntimeSettings)
    assert runtime.max_tool_iters == 2
    effective = await service.effective_settings()
    assert effective.llm_runtime.max_tool_iters == 2
    assert effective.llm_runtime.max_hitl_rounds == 3  # untouched fields keep env values

    await service.clear_override("llm_runtime.max_tool_iters", admin.id)
    runtime = await service.get_effective(LlmRuntimeSettings)
    assert runtime.max_tool_iters == 6


@pytest.mark.integration
async def test_set_override_upserts_single_row(session: AsyncSession, admin: User) -> None:
    service = _service(session)
    await service.set_override("scrape.delay_seconds", 0.5, admin.id)
    await service.set_override("scrape.delay_seconds", 2.5, admin.id)
    rows = list((await session.execute(select(AppSetting))).scalars())
    assert len(rows) == 1
    assert rows[0].value == 2.5
    assert len(await service.list_overrides()) == 1


@pytest.mark.integration
async def test_every_write_is_audited(session: AsyncSession, admin: User) -> None:
    service = _service(session)
    await service.set_override("llm_runtime.max_tool_iters", 2, admin.id)
    await service.set_override("llm_runtime.max_tool_iters", 3, admin.id)
    await service.clear_override("llm_runtime.max_tool_iters", admin.id)
    audits = list(
        (
            await session.execute(select(AppSettingAudit).order_by(AppSettingAudit.created_at))
        ).scalars()
    )
    assert [(a.action, a.old_value, a.new_value) for a in audits] == [
        ("set", None, 2),
        ("set", 2, 3),
        ("clear", 3, None),
    ]
    assert all(a.actor_id == admin.id for a in audits)


@pytest.mark.integration
async def test_write_rejections(session: AsyncSession, admin: User) -> None:
    service = _service(session)
    with pytest.raises(UnknownSettingKeyError):
        await service.set_override("auth.jwt_secret", "evil", admin.id)
    with pytest.raises(UnknownSettingKeyError):
        await service.set_override("nope.nope", 1, admin.id)
    with pytest.raises(SettingValueInvalidError):
        await service.set_override("llm_runtime.max_tool_iters", "many", admin.id)
    with pytest.raises(SettingValueInvalidError):
        await service.set_override("llm_runtime.max_tool_iters", 0, admin.id)  # ge=1
    with pytest.raises(OverrideNotFoundError):
        await service.clear_override("llm_runtime.max_tool_iters", admin.id)


@pytest.mark.integration
async def test_invalid_stored_row_falls_back_to_env(session: AsyncSession, admin: User) -> None:
    # Simulate a stale row (written before a type/whitelist change).
    session.add(AppSetting(key="llm_runtime.max_tool_iters", value="stale", updated_by=admin.id))
    session.add(AppSetting(key="ghost.key", value=1, updated_by=admin.id))
    await session.flush()
    runtime = await _service(session).get_effective(LlmRuntimeSettings)
    assert runtime.max_tool_iters == 6  # skipped, env value applies


@pytest.mark.integration
async def test_list_effective_reports_overrides(session: AsyncSession, admin: User) -> None:
    service = _service(session)
    await service.set_override("llm_runtime.max_turn_cost_usd", 0.01, admin.id)
    entries = {e.key: e for e in await service.list_effective()}
    assert set(entries) == set(TUNABLE_FIELDS)  # every whitelisted key is listed
    cost = entries["llm_runtime.max_turn_cost_usd"]
    assert cost.overridden is True
    assert cost.effective_value == 0.01
    assert cost.env_value == 0.05
    assert cost.updated_by == admin.id
    iters = entries["llm_runtime.max_tool_iters"]
    assert iters.overridden is False
    assert iters.effective_value == 6
    assert iters.updated_by is None
    assert iters.description is not None
    assert "tool" in iters.description.lower()
