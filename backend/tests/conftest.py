"""Pytest bootstrap: isolate integration tests from the app database."""

from __future__ import annotations

import asyncio
import os
from urllib.parse import urlparse

# Must run before any app.core.config / alembic import.
_DEFAULT_TEST_DB = "postgresql+asyncpg://rtm:rtm@localhost:5432/rtm_test"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_DB)


def _dsn_parts(url: str) -> tuple[str, str, str, int, str]:
    parsed = urlparse(url.replace("postgresql+asyncpg://", "postgresql://", 1))
    return (
        parsed.username or "rtm",
        parsed.password or "rtm",
        parsed.hostname or "localhost",
        parsed.port or 5432,
        (parsed.path or "/rtm_test").lstrip("/") or "rtm_test",
    )


async def _ensure_database() -> None:
    import asyncpg  # type: ignore[import-untyped]

    user, password, host, port, db_name = _dsn_parts(os.environ["DATABASE_URL"])
    conn = await asyncpg.connect(
        user=user,
        password=password,
        host=host,
        port=port,
        database="postgres",
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            db_name,
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await conn.close()


def _run_migrations() -> None:
    from alembic import command
    from alembic.config import Config
    from app.core.config import get_settings

    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "head")


def pytest_configure() -> None:
    """Create rtm_test (if needed) and apply migrations once per session."""
    asyncio.run(_ensure_database())
    _run_migrations()
