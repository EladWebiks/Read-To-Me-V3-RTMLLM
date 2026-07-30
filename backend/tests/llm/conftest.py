"""Shared fixtures for DB-catalog llm tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from app.core.db import SessionLocal
from app.modules.llm import catalog
from app.modules.llm.seed import seed_llm_models
from sqlalchemy import text


@pytest.fixture(autouse=True)
async def _fresh_global_engine() -> AsyncIterator[None]:
    """Rebuild app.core.db's pool around each test.

    Tests here drive the module-global SessionLocal (that is what production
    seeding and the arq worker use). Its asyncpg pool pins connections to the
    event loop that opened them, and pytest-asyncio gives every test a fresh
    loop, so a pooled connection carried across tests fails with
    "'NoneType' object has no attribute 'send'". Disposing on both sides keeps
    each test's connections on its own loop.
    """
    from app.core.db import engine

    await engine.dispose()
    yield
    await engine.dispose()


async def _reset_catalog_rows() -> None:
    async with SessionLocal() as session:
        await session.execute(text("DELETE FROM model_configurations"))
        await session.execute(text("DELETE FROM model_providers"))
        await session.commit()


@pytest.fixture
async def seeded_catalog() -> AsyncIterator[None]:
    """Pristine seeded catalog rows + cold snapshot; restores both afterwards."""
    await _reset_catalog_rows()
    await seed_llm_models()
    catalog.invalidate()
    yield
    await _reset_catalog_rows()
    await seed_llm_models()
    catalog.invalidate()
