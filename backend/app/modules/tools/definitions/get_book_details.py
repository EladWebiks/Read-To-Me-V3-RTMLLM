"""get_book_details — one owned book."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.library.exceptions import BookAccessDeniedError
from app.modules.library.service import LibraryService
from app.modules.tools.base import BaseTool, RiskLevel, ToolContext
from app.modules.tools.exceptions import ToolAuthzError


class GetBookDetailsInput(BaseModel):
    """Identify a book in the user's library."""

    book_id: UUID = Field(description="UUID of a book the user owns")


class GetBookDetailsOutput(BaseModel):
    """Book metadata for an owned library entry."""

    id: UUID
    title: str
    author: str
    description: str
    language: str
    chapter_count: int
    status: str
    starting_chapter_number: int
    last_read_chapter_number: int | None = None


class GetBookDetailsTool(BaseTool):
    """Fetch details for one book the user owns."""

    name = "get_book_details"
    description = (
        "Get details for a single book in the user's library by book_id. "
        "Fails if the book is not owned by the user."
    )
    input_model = GetBookDetailsInput
    output_model = GetBookDetailsOutput
    risk_level = RiskLevel.READ_ONLY
    read_only = True
    touches_external = False
    allowed_in_internal_only = True
    timeout_ms = 10_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        data = GetBookDetailsInput.model_validate(inp.model_dump())
        try:
            await LibraryService(ctx.session).assert_access(ctx.user_id, data.book_id)
        except BookAccessDeniedError as exc:
            raise ToolAuthzError(str(exc)) from exc

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        data = GetBookDetailsInput.model_validate(inp.model_dump())
        book = await LibraryService(ctx.session).get_book(ctx.user_id, data.book_id)
        return GetBookDetailsOutput(
            id=book.id,
            title=book.title,
            author=book.author,
            description=book.description,
            language=book.language,
            chapter_count=book.chapter_count,
            status=book.status,
            starting_chapter_number=book.starting_chapter_number,
            last_read_chapter_number=book.last_read_chapter_number,
        )
