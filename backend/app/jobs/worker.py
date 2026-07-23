"""arq worker entrypoint."""

from typing import ClassVar

from app.core.orm import import_all_models
from app.jobs.queue import redis_settings
from app.jobs.tasks import run_download_job
from app.modules.scraping.worker import run_scrape_job


async def on_startup(_ctx: object) -> None:
    """Register ORM models before jobs run."""
    import_all_models()


class WorkerSettings:
    """arq WorkerSettings consumed by `arq app.jobs.worker.WorkerSettings`."""

    functions: ClassVar[list[object]] = [run_download_job, run_scrape_job]
    redis_settings = redis_settings()
    on_startup = on_startup
