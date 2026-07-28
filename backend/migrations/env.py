"""Alembic migration environment (async SQLAlchemy)."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from app.core.config import get_settings
from app.core.db import Base

# Import models so Alembic autogenerate can see metadata.
from app.modules.books.models import Book as BookModel  # noqa: F401
from app.modules.chapters.models import Chapter as ChapterModel  # noqa: F401
from app.modules.downloads.models import DownloadJob as DownloadJobModel  # noqa: F401
from app.modules.library.models import UserBook as UserBookModel  # noqa: F401
from app.modules.llm.models import (  # noqa: F401
    Conversation as ConversationModel,
)
from app.modules.reader.models import ReadingProgress as ProgressModel  # noqa: F401
from app.modules.scraping.models import ScrapingJob as ScrapingJobModel  # noqa: F401
from app.modules.scraping.models import ScrapingJobItem as ScrapingJobItemModel  # noqa: F401
from app.modules.scraping.models import ScrapingSource as ScrapingSourceModel  # noqa: F401
from app.modules.users.models import User as UserModel  # noqa: F401
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations using a sync connection bridge."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
