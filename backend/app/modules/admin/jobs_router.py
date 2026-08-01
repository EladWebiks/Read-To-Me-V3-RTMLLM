"""Backoffice read-only job monitor routes. HTTP only; logic in owning services."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_admin
from app.modules.admin.params import PageParams
from app.modules.admin.schemas import Page
from app.modules.downloads.schemas import DownloadJobAdminRead
from app.modules.downloads.service import DownloadService
from app.modules.scraping.schemas import ScrapeJobAdminRead
from app.modules.scraping.service import ScrapingService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/jobs")


def _scraping(session: Annotated[AsyncSession, Depends(get_db)]) -> ScrapingService:
    return ScrapingService(session)


def _downloads(session: Annotated[AsyncSession, Depends(get_db)]) -> DownloadService:
    return DownloadService(session)


@router.get("/scraping")
async def list_scraping_jobs(
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[ScrapingService, Depends(_scraping)],
    page: Annotated[PageParams, Depends()],
    status: str | None = None,
) -> Page[ScrapeJobAdminRead]:
    """All users' scraping jobs, newest first (read-only)."""
    items, total = await service.list_jobs_admin(
        status=status, limit=page.limit, offset=page.offset
    )
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/downloads")
async def list_download_jobs(
    _admin: Annotated[UserRead, Depends(require_admin)],
    service: Annotated[DownloadService, Depends(_downloads)],
    page: Annotated[PageParams, Depends()],
    status: str | None = None,
) -> Page[DownloadJobAdminRead]:
    """All users' download jobs, newest first (read-only)."""
    items, total = await service.list_jobs_admin(
        status=status, limit=page.limit, offset=page.offset
    )
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)
