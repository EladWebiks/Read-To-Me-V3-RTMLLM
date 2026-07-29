"""Shared chapter lookup helpers for tools."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.modules.chapters.exceptions import ChapterNotFoundError
from app.modules.chapters.schemas import ChapterRead
from app.modules.chapters.service import ChapterService
from app.modules.tools.base import ToolContext
from app.modules.tools.exceptions import ToolValidationError


class ChapterRefInput(BaseModel):
    """Identify a chapter by id, or by book_id + chapter_number."""

    chapter_id: UUID | None = Field(default=None, description="Chapter UUID if known")
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
    def _require_identity(self) -> ChapterRefInput:
        if self.chapter_id is not None:
            return self
        if self.book_id is not None and self.chapter_number is not None:
            return self
        raise ValueError("Provide chapter_id, or book_id together with chapter_number")


async def load_chapter(data: ChapterRefInput, ctx: ToolContext) -> ChapterRead:
    """Load chapter or raise ToolValidationError."""
    chapters = ChapterService(ctx.session)
    try:
        if data.chapter_id is not None:
            return await chapters.get(data.chapter_id)
        if data.book_id is None or data.chapter_number is None:
            raise ToolValidationError("book_id and chapter_number required")
        return await chapters.get_by_number(data.book_id, data.chapter_number)
    except ChapterNotFoundError as exc:
        raise ToolValidationError(str(exc)) from exc


async def book_id_for_ref(data: ChapterRefInput, ctx: ToolContext) -> UUID:
    """Resolve book_id for authz before execute."""
    if data.book_id is not None:
        return data.book_id
    chapter = await load_chapter(data, ctx)
    return chapter.book_id
