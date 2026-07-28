"""create_chapter_download — single-chapter MP3 job (idempotent)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.modules.downloads.exceptions import InvalidChapterRangeError
from app.modules.downloads.service import DownloadService
from app.modules.library.exceptions import BookAccessDeniedError
from app.modules.library.service import LibraryService
from app.modules.tools.base import BaseTool, RiskLevel, ToolContext
from app.modules.tools.definitions.chapter_ref import (
    ChapterRefInput,
    book_id_for_ref,
    load_chapter,
)
from app.modules.tools.exceptions import ToolAuthzError, ToolValidationError


class CreateChapterDownloadOutput(BaseModel):
    """Created or reused download job for one chapter."""

    job_id: UUID
    book_id: UUID
    chapter_number: int
    status: str
    reused: bool
    message: str


class CreateChapterDownloadTool(BaseTool):
    """Enqueue a single-chapter TTS download; reuse an active job if present."""

    name = "create_chapter_download"
    description = (
        "Create an MP3 download job for a single chapter the user owns. "
        "Idempotent: if a pending/processing/complete job already covers that "
        "chapter alone, reuse it. Identify with chapter_id or book_id + chapter_number. "
        "Use get_download_status to poll. Do not use this for multi-chapter ranges."
    )
    input_model = ChapterRefInput
    output_model = CreateChapterDownloadOutput
    risk_level = RiskLevel.LOW_RISK
    read_only = False
    touches_external = False
    allowed_in_internal_only = True
    timeout_ms = 15_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        data = ChapterRefInput.model_validate(inp.model_dump())
        book_id = await book_id_for_ref(data, ctx)
        try:
            await LibraryService(ctx.session).assert_access(ctx.user_id, book_id)
        except BookAccessDeniedError as exc:
            raise ToolAuthzError(str(exc)) from exc

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        data = ChapterRefInput.model_validate(inp.model_dump())
        chapter = await load_chapter(data, ctx)
        try:
            job, reused = await DownloadService(ctx.session).create_single_chapter(
                ctx.user_id,
                chapter.book_id,
                chapter.chapter_number,
            )
        except InvalidChapterRangeError as exc:
            raise ToolValidationError(str(exc)) from exc
        except BookAccessDeniedError as exc:
            raise ToolAuthzError(str(exc)) from exc
        verb = "Reused existing" if reused else "Created"
        return CreateChapterDownloadOutput(
            job_id=job.id,
            book_id=job.book_id,
            chapter_number=chapter.chapter_number,
            status=job.status,
            reused=reused,
            message=(
                f"{verb} download job for chapter {chapter.chapter_number} "
                f"(status={job.status}). Use get_download_status with job_id to check."
            ),
        )
