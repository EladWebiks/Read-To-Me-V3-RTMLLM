"""list_available_chapters — chapter index for an owned book."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.chapters.service import ChapterService
from app.modules.library.exceptions import BookAccessDeniedError
from app.modules.library.service import LibraryService
from app.modules.tools.base import BaseTool, RiskLevel, ToolContext
from app.modules.tools.exceptions import ToolAuthzError


class ListAvailableChaptersInput(BaseModel):
    """Book whose chapters to list."""

    book_id: UUID = Field(description="UUID of a book the user owns")


class ChapterIndexItem(BaseModel):
    """One chapter without full text."""

    id: UUID
    chapter_number: int
    title: str
    word_count: int


class ListAvailableChaptersOutput(BaseModel):
    """Chapter index for a book."""

    book_id: UUID
    chapters: list[ChapterIndexItem]
    total: int


class ListAvailableChaptersTool(BaseTool):
    """List chapter numbers/titles for an owned book."""

    name = "list_available_chapters"
    description = (
        "List available chapters for an owned book (number, title, word count). "
        "Does not return full chapter text — use get_chapter_content for that."
    )
    input_model = ListAvailableChaptersInput
    output_model = ListAvailableChaptersOutput
    risk_level = RiskLevel.READ_ONLY
    read_only = True
    touches_external = False
    allowed_in_internal_only = True
    timeout_ms = 10_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        data = ListAvailableChaptersInput.model_validate(inp.model_dump())
        try:
            await LibraryService(ctx.session).assert_access(ctx.user_id, data.book_id)
        except BookAccessDeniedError as exc:
            raise ToolAuthzError(str(exc)) from exc

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        data = ListAvailableChaptersInput.model_validate(inp.model_dump())
        rows = await ChapterService(ctx.session).list_summaries(data.book_id)
        chapters = [
            ChapterIndexItem(
                id=row.id,
                chapter_number=row.chapter_number,
                title=row.title,
                word_count=row.word_count,
            )
            for row in rows
        ]
        return ListAvailableChaptersOutput(
            book_id=data.book_id,
            chapters=chapters,
            total=len(chapters),
        )
