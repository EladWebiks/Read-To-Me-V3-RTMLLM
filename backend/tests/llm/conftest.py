"""Shared fixtures for DB-catalog llm tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest


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
