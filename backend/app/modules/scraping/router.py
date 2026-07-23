"""Scraping HTTP routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.modules.scraping.schemas import (
    ScrapeJobCreate,
    ScrapeJobRead,
    ScrapePreviewRequest,
    ScrapePreviewResponse,
)
from app.modules.scraping.service import ScrapingService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/scraping", tags=["scraping"])


def _svc(session: Annotated[AsyncSession, Depends(get_db)]) -> ScrapingService:
    return ScrapingService(session)


@router.post("/preview", response_model=ScrapePreviewResponse)
async def preview_scrape(
    body: ScrapePreviewRequest,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[ScrapingService, Depends(_svc)],
) -> ScrapePreviewResponse:
    _ = user
    return await service.preview(body.url)


@router.post("/jobs", response_model=ScrapeJobRead, status_code=201)
async def create_scrape_job(
    body: ScrapeJobCreate,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[ScrapingService, Depends(_svc)],
) -> ScrapeJobRead:
    return await service.create_job(user.id, body)


@router.get("/jobs", response_model=list[ScrapeJobRead])
async def list_scrape_jobs(
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[ScrapingService, Depends(_svc)],
) -> list[ScrapeJobRead]:
    return await service.list_jobs(user.id)


@router.get("/jobs/{job_id}", response_model=ScrapeJobRead)
async def get_scrape_job(
    job_id: UUID,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[ScrapingService, Depends(_svc)],
) -> ScrapeJobRead:
    return await service.get_job(user.id, job_id)


@router.post("/jobs/{job_id}/cancel", response_model=ScrapeJobRead)
async def cancel_scrape_job(
    job_id: UUID,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[ScrapingService, Depends(_svc)],
) -> ScrapeJobRead:
    return await service.cancel(user.id, job_id)
