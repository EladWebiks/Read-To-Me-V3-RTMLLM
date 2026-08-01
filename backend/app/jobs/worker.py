"""arq worker entrypoint."""

from typing import ClassVar, cast

from arq import cron
from arq.typing import WorkerCoroutine

from app.core.orm import import_all_models
from app.jobs.purge_downloads import purge_expired_download_jobs
from app.jobs.queue import redis_settings
from app.jobs.tasks import run_download_job
from app.modules.scraping.worker import run_scrape_job
from app.modules.usage.rollup import roll_usage_window


async def on_startup(_ctx: object) -> None:
    """Register ORM models before jobs run."""
    import_all_models()


class WorkerSettings:
    """arq WorkerSettings consumed by `arq app.jobs.worker.WorkerSettings`."""

    functions: ClassVar[list[object]] = [run_download_job, run_scrape_job]
    cron_jobs: ClassVar[list[object]] = [
        # Lazy purge also runs on list/create; cron keeps disk tidy if UI is idle.
        cron(cast(WorkerCoroutine, purge_expired_download_jobs), minute={0, 30}),
        # Nightly usage rollup: re-rolls the trailing window at 00:10 UTC.
        cron(cast(WorkerCoroutine, roll_usage_window), hour={0}, minute={10}),
    ]
    redis_settings = redis_settings()
    on_startup = on_startup
