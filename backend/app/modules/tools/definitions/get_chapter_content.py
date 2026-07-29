"""get_chapter_content — full text of one owned chapter (truncated for the model)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.modules.chapters.exceptions import ChapterNotFoundError
from app.modules.chapters.schemas import ChapterRead
from app.modules.chapters.service import ChapterService
from app.modules.library.exceptions import BookAccessDeniedError
from app.modules.library.service import LibraryService
from app.modules.tools.base import BaseTool, RiskLevel, ToolContext
from app.modules.tools.exceptions import ToolAuthzError, ToolValidationError

_MAX_CONTENT_CHARS = 12_000


class GetChapterContentInput(BaseModel):
    """Identify a chapter by id, or by book_id + chapter_number."""

    chapter_id: UUID | None = Field(
        default=None,
        description="Chapter UUID if known",
    )
    book_id: UUID | None = Field(
        default=None,
        description="Book UUID when looking up by chapter_number",
    )
    chapter_number: int | None = Field(
        default=None,
        ge=0,
        description="Chapter number within book_id",
    )

    @model_validator(mode="after")
    def _require_identity(self) -> GetChapterContentInput:
        if self.chapter_id is not None:
            return self
        if self.book_id is not None and self.chapter_number is not None:
            return self
        raise ValueError("Provide chapter_id, or book_id together with chapter_number")


class GetChapterContentOutput(BaseModel):
    """Chapter text for the model (may be truncated)."""

    chapter_id: UUID
    book_id: UUID
    chapter_number: int
    title: str
    content: str
    truncated: bool
    word_count: int


class GetChapterContentTool(BaseTool):
    """Fetch chapter text for an owned book."""

    name = "get_chapter_content"
    description = (
        "Get the text of one chapter the user owns. Prefer chapter_id, or "
        "book_id + chapter_number. Long chapters may be truncated."
    )
    input_model = GetChapterContentInput
    output_model = GetChapterContentOutput
    risk_level = RiskLevel.READ_ONLY
    read_only = True
    touches_external = False
    allowed_in_internal_only = True
    timeout_ms = 15_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        data = GetChapterContentInput.model_validate(inp.model_dump())
        book_id = await _resolve_book_id(data, ctx)
        try:
            await LibraryService(ctx.session).assert_access(ctx.user_id, book_id)
        except BookAccessDeniedError as exc:
            raise ToolAuthzError(str(exc)) from exc

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        data = GetChapterContentInput.model_validate(inp.model_dump())
        chapter = await _load_chapter(data, ctx)
        content, truncated = _truncate(chapter.content)
        return GetChapterContentOutput(
            chapter_id=chapter.id,
            book_id=chapter.book_id,
            chapter_number=chapter.chapter_number,
            title=chapter.title,
            content=content,
            truncated=truncated,
            word_count=chapter.word_count,
        )


async def _resolve_book_id(data: GetChapterContentInput, ctx: ToolContext) -> UUID:
    if data.book_id is not None:
        return data.book_id
    if data.chapter_id is None:
        raise ToolValidationError("chapter_id or book_id required")
    try:
        chapter = await ChapterService(ctx.session).get(data.chapter_id)
    except ChapterNotFoundError as exc:
        raise ToolAuthzError(str(exc)) from exc
    return chapter.book_id


async def _load_chapter(data: GetChapterContentInput, ctx: ToolContext) -> ChapterRead:
    chapters = ChapterService(ctx.session)
    try:
        if data.chapter_id is not None:
            return await chapters.get(data.chapter_id)
        if data.book_id is None or data.chapter_number is None:
            raise ToolValidationError("book_id and chapter_number required")
        return await chapters.get_by_number(data.book_id, data.chapter_number)
    except ChapterNotFoundError as exc:
        raise ToolValidationError(str(exc)) from exc


def _truncate(content: str) -> tuple[str, bool]:
    if len(content) <= _MAX_CONTENT_CHARS:
        return content, False
    return content[:_MAX_CONTENT_CHARS] + "\n…[truncated]", True
