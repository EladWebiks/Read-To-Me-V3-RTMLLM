"""Periodic cleanup of expired download MP3 jobs."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.downloads.service import DownloadService

logger = logging.getLogger(__name__)


async def purge_expired_download_jobs(_ctx: object) -> None:
    """arq cron: remove expired download jobs and their MinIO objects."""
    from app.core.orm import import_all_models

    import_all_models()
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with factory() as session:
            deleted = await DownloadService(session).purge_all_expired()
        if deleted:
            logger.info("Purged %s expired download job(s)", deleted)
    finally:
        await engine.dispose()
