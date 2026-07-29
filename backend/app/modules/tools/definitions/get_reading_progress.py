"""get_reading_progress — saved position for one owned book."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.library.exceptions import BookAccessDeniedError
from app.modules.library.service import LibraryService
from app.modules.reader.exceptions import ProgressNotFoundError
from app.modules.reader.service import ReaderService
from app.modules.tools.base import BaseTool, RiskLevel, ToolContext
from app.modules.tools.exceptions import ToolAuthzError


class GetReadingProgressInput(BaseModel):
    """Book to look up progress for."""

    book_id: UUID = Field(description="UUID of a book the user owns")


class GetReadingProgressOutput(BaseModel):
    """Progress if any has been saved."""

    found: bool
    book_id: UUID
    chapter_id: UUID | None = None
    chapter_number: int | None = None
    paragraph_index: int | None = None
    word_index: int | None = None
    updated_at: datetime | None = None


class GetReadingProgressTool(BaseTool):
    """Return the user's saved reading position for a book."""

    name = "get_reading_progress"
    description = (
        "Get the user's saved reading progress for one owned book "
        "(chapter number and position). found=false if they have not started it."
    )
    input_model = GetReadingProgressInput
    output_model = GetReadingProgressOutput
    risk_level = RiskLevel.READ_ONLY
    read_only = True
    touches_external = False
    allowed_in_internal_only = True
    timeout_ms = 10_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        data = GetReadingProgressInput.model_validate(inp.model_dump())
        try:
            await LibraryService(ctx.session).assert_access(ctx.user_id, data.book_id)
        except BookAccessDeniedError as exc:
            raise ToolAuthzError(str(exc)) from exc

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        data = GetReadingProgressInput.model_validate(inp.model_dump())
        try:
            progress = await ReaderService(ctx.session).get_progress(
                ctx.user_id,
                data.book_id,
            )
        except ProgressNotFoundError:
            return GetReadingProgressOutput(found=False, book_id=data.book_id)
        return GetReadingProgressOutput(
            found=True,
            book_id=progress.book_id,
            chapter_id=progress.chapter_id,
            chapter_number=progress.chapter_number,
            paragraph_index=progress.paragraph_index,
            word_index=progress.word_index,
            updated_at=progress.updated_at,
        )
