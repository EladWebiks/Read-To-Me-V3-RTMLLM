"""resume_book — jump to saved (or latest) reading position."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.chapters.exceptions import ChapterNotFoundError
from app.modules.chapters.service import ChapterService
from app.modules.library.exceptions import BookAccessDeniedError
from app.modules.library.service import LibraryService
from app.modules.reader.exceptions import ProgressNotFoundError
from app.modules.reader.schemas import ProgressRead, ProgressUpsert
from app.modules.reader.service import ReaderService
from app.modules.tools.base import BaseTool, RiskLevel, ToolContext
from app.modules.tools.exceptions import ToolAuthzError


class ResumeBookInput(BaseModel):
    """Optional book; omit to resume the most recently read book."""

    book_id: UUID | None = Field(
        default=None,
        description="Book to resume; if omitted, use the most recently read book",
    )


class ResumeBookOutput(BaseModel):
    """Resume intent for the client."""

    action: str = "resume_book"
    found: bool
    book_id: UUID | None = None
    chapter_id: UUID | None = None
    chapter_number: int | None = None
    message: str


class ResumeBookTool(BaseTool):
    """Resume reading at the saved position."""

    name = "resume_book"
    description = (
        "Resume reading where the user left off. Pass book_id for a specific book, "
        "or omit it to resume the most recently read book. Updates the current pointer."
    )
    input_model = ResumeBookInput
    output_model = ResumeBookOutput
    risk_level = RiskLevel.LOW_RISK
    read_only = False
    touches_external = False
    allowed_in_internal_only = True
    timeout_ms = 10_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        data = ResumeBookInput.model_validate(inp.model_dump())
        if data.book_id is None:
            return
        try:
            await LibraryService(ctx.session).assert_access(ctx.user_id, data.book_id)
        except BookAccessDeniedError as exc:
            raise ToolAuthzError(str(exc)) from exc

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        data = ResumeBookInput.model_validate(inp.model_dump())
        reader = ReaderService(ctx.session)
        progress = await _load_progress(reader, ctx.user_id, data.book_id)
        if progress is None:
            return ResumeBookOutput(
                found=False,
                book_id=data.book_id,
                message="No saved reading progress yet.",
            )
        await reader.upsert_progress(
            ctx.user_id,
            progress.book_id,
            ProgressUpsert(
                chapter_id=progress.chapter_id,
                chapter_number=progress.chapter_number,
                paragraph_index=progress.paragraph_index,
                word_index=progress.word_index,
            ),
        )
        title = await _chapter_title(ctx, progress.chapter_id)
        suffix = f" ({title})" if title else ""
        return ResumeBookOutput(
            found=True,
            book_id=progress.book_id,
            chapter_id=progress.chapter_id,
            chapter_number=progress.chapter_number,
            message=f"Resuming at chapter {progress.chapter_number}{suffix}.",
        )


async def _load_progress(
    reader: ReaderService,
    user_id: UUID,
    book_id: UUID | None,
) -> ProgressRead | None:
    if book_id is None:
        return await reader.continue_reading(user_id)
    try:
        return await reader.get_progress(user_id, book_id)
    except ProgressNotFoundError:
        return None


async def _chapter_title(ctx: ToolContext, chapter_id: UUID) -> str:
    try:
        chapter = await ChapterService(ctx.session).get(chapter_id)
    except ChapterNotFoundError:
        return ""
    return chapter.title
