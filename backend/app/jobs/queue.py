"""Arq job enqueue helpers."""

from __future__ import annotations

from uuid import UUID

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import get_settings

_pool: ArqRedis | None = None


def redis_settings() -> RedisSettings:
    """Build arq Redis settings from app config."""
    return RedisSettings.from_dsn(get_settings().redis_url)


async def get_arq_pool() -> ArqRedis:
    """Lazy shared arq pool for the API process."""
    global _pool
    if _pool is None:
        _pool = await create_pool(redis_settings())
    return _pool


async def enqueue_download_job(job_id: UUID) -> None:
    """Enqueue run_download_job for a download_jobs row."""
    pool = await get_arq_pool()
    await pool.enqueue_job("run_download_job", str(job_id))


async def enqueue_scrape_job(job_id: UUID) -> None:
    """Enqueue run_scrape_job for a scraping_jobs row."""
    pool = await get_arq_pool()
    await pool.enqueue_job("run_scrape_job", str(job_id))
