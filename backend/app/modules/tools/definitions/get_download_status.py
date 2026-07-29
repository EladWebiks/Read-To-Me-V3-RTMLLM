"""get_download_status — status of the user's MP3 download jobs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.downloads.exceptions import DownloadJobNotFoundError
from app.modules.downloads.schemas import DownloadJobRead
from app.modules.downloads.service import DownloadService
from app.modules.library.exceptions import BookAccessDeniedError
from app.modules.tools.base import BaseTool, RiskLevel, ToolContext
from app.modules.tools.exceptions import ToolAuthzError, ToolValidationError


class GetDownloadStatusInput(BaseModel):
    """Look up one job, or list jobs (optionally for one book)."""

    job_id: UUID | None = Field(
        default=None,
        description="Specific download job UUID",
    )
    book_id: UUID | None = Field(
        default=None,
        description="If set (and job_id omitted), list jobs for this owned book",
    )


class DownloadStatusItem(BaseModel):
    """Compact download job status for the model."""

    id: UUID
    book_id: UUID
    chapter_from: int
    chapter_to: int
    status: str
    ready_count: int
    total_count: int
    error: str | None = None
    expires_at: datetime | None = None


class GetDownloadStatusOutput(BaseModel):
    """One or more download jobs."""

    jobs: list[DownloadStatusItem]
    total: int


class GetDownloadStatusTool(BaseTool):
    """Check download/TTS job status for the user."""

    name = "get_download_status"
    description = (
        "Get status of the user's chapter MP3 download jobs. "
        "Pass job_id for one job, or book_id to list jobs for a book, "
        "or neither to list recent jobs."
    )
    input_model = GetDownloadStatusInput
    output_model = GetDownloadStatusOutput
    risk_level = RiskLevel.READ_ONLY
    read_only = True
    touches_external = False
    allowed_in_internal_only = True
    timeout_ms = 10_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        """Ownership enforced inside DownloadService."""

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        data = GetDownloadStatusInput.model_validate(inp.model_dump())
        service = DownloadService(ctx.session)
        try:
            jobs = await _fetch_jobs(service, ctx.user_id, data)
        except DownloadJobNotFoundError as exc:
            raise ToolValidationError(str(exc)) from exc
        except BookAccessDeniedError as exc:
            raise ToolAuthzError(str(exc)) from exc
        items = [_to_item(job) for job in jobs]
        return GetDownloadStatusOutput(jobs=items, total=len(items))


async def _fetch_jobs(
    service: DownloadService,
    user_id: UUID,
    data: GetDownloadStatusInput,
) -> list[DownloadJobRead]:
    if data.job_id is not None:
        return [await service.get(user_id, data.job_id)]
    return await service.list_jobs(user_id, data.book_id)


def _to_item(job: DownloadJobRead) -> DownloadStatusItem:
    return DownloadStatusItem(
        id=job.id,
        book_id=job.book_id,
        chapter_from=job.chapter_from,
        chapter_to=job.chapter_to,
        status=job.status,
        ready_count=job.ready_count,
        total_count=job.total_count,
        error=job.error,
        expires_at=job.expires_at,
    )
