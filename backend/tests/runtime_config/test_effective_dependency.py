"""get_effective_settings: layering proof + chat-router wiring pin."""

from collections.abc import AsyncIterator
from typing import get_type_hints

import pytest
from app.core.config import get_settings
from app.modules.llm.types import Usage
from app.modules.orchestration.budget import RunBudget
from app.modules.orchestration.exceptions import BudgetExceededError
from app.modules.runtime_config import cache
from app.modules.runtime_config.service import RuntimeConfigService
from app.modules.users.models import User
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.dbcleanup import clear_users


@pytest.mark.unit
def test_chat_service_dependency_uses_effective_settings() -> None:
    from app.core.deps import get_effective_settings
    from app.modules.llm import router as llm_router

    # `llm.router` uses `from __future__ import annotations`, so the raw
    # signature holds strings — resolve them to reach the Depends marker.
    hints = get_type_hints(llm_router._chat_service, include_extras=True)
    depends = hints["settings"].__metadata__[0]
    assert depends.dependency is get_effective_settings


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


@pytest.mark.integration
async def test_override_changes_budget_enforcement_without_restart(
    session: AsyncSession,
) -> None:
    from app.core.deps import get_effective_settings

    base = get_settings()
    original_cap = base.llm_runtime.max_turn_cost_usd
    new_cap = original_cap / 2

    admin = User(
        username="cfg-admin",
        email="cfg-admin@example.com",
        password_hash=None,
        google_sub="cfg-admin-sub",
        is_admin=True,
    )
    session.add(admin)
    await session.flush()
    await RuntimeConfigService(session, base).set_override(
        "llm_runtime.max_turn_cost_usd", new_cap, admin.id
    )

    effective = await get_effective_settings(session, base)
    budget = RunBudget.from_settings(effective)
    assert budget.max_cost_usd == new_cap
    with pytest.raises(BudgetExceededError):
        budget.add_usage(Usage(1, 1), cost_usd=new_cap * 1.5)

    # Same process, no restart: the env-backed base is untouched, and a
    # budget built from it still enforces the original cap.
    assert base.llm_runtime.max_turn_cost_usd == original_cap
    assert RunBudget.from_settings(base).max_cost_usd == original_cap
