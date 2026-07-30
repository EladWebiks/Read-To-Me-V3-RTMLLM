"""Pytest bootstrap: hermetic env for settings + isolated test database."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

import pytest
from dotenv import dotenv_values

# Must run before any app.core.config / alembic import.
_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
_DEFAULT_TEST_DB = "postgresql+asyncpg://rtm:rtm@localhost:5432/rtm_test"
# Infra keys only. The repo-root `.env` also holds real secrets (GOOGLE_*,
# GEMINI_API_KEY); importing those would silently configure tests that assert
# a feature is *unconfigured*, and would make results depend on the developer's
# `.env`. Settings built by `tests.factories` read os.environ for anything not
# passed explicitly, so what lands here has to stay boring.
_INFRA_PREFIXES = ("DATABASE_URL", "TEST_DATABASE_URL", "REDIS_URL", "MINIO_")

# 1) Real dev values from the repo-root .env (if present) win over dummies,
#    so integration tests keep talking to the local stack's credentials.
if _ROOT_ENV.exists():
    for _key, _value in dotenv_values(_ROOT_ENV).items():
        if _value is not None and _key.startswith(_INFRA_PREFIXES):
            os.environ.setdefault(_key, _value)

# 2) The two remaining no-default vars, so a clean checkout (or a
#    docker-compose .env, which must not contain them) still boots.
for _key, _value in {
    "REDIS_URL": "redis://localhost:6379/0",
    "MINIO_ENDPOINT": "localhost:9000",
}.items():
    os.environ.setdefault(_key, _value)

# 3) Integration tests must never touch the app database.
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


@pytest.fixture(autouse=True)
def _warm_model_catalog() -> Iterator[None]:
    """Pre-warm the model-catalog snapshot with the seed defaults.

    The runtime catalog is DB-backed; warming it from MODEL_CATALOG keeps
    unit tests hermetic and gives every existing test exactly the catalog it
    saw when the registry was static. DB-facing catalog tests call
    catalog.invalidate() themselves (see tests/llm/conftest.py).
    """
    from app.modules.llm import catalog
    from app.modules.llm.registry import MODEL_CATALOG

    catalog.put_snapshot(MODEL_CATALOG)
    yield
    catalog.invalidate()
