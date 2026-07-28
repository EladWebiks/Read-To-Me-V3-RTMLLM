"""get_recently_read_chapters — recent reading activity."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.reader.service import ReaderService
from app.modules.tools.base import BaseTool, RiskLevel, ToolContext


class GetRecentlyReadInput(BaseModel):
    """How many recent positions to return."""

    limit: int = Field(
        default=10,
        ge=1,
        le=30,
        description="Max number of recent reading positions to return",
    )


class RecentReadItem(BaseModel):
    """One recent reading position."""

    book_id: UUID
    chapter_id: UUID
    chapter_number: int
    updated_at: datetime


class GetRecentlyReadOutput(BaseModel):
    """Recent reading activity for the user."""

    items: list[RecentReadItem]
    total: int


class GetRecentlyReadChaptersTool(BaseTool):
    """List books/chapters the user read most recently."""

    name = "get_recently_read_chapters"
    description = (
        "List the user's most recently updated reading positions "
        "(which books/chapters they were last reading)."
    )
    input_model = GetRecentlyReadInput
    output_model = GetRecentlyReadOutput
    risk_level = RiskLevel.READ_ONLY
    read_only = True
    touches_external = False
    allowed_in_internal_only = True
    timeout_ms = 10_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        """Scoped to ctx.user_id."""

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        data = GetRecentlyReadInput.model_validate(inp.model_dump())
        rows = await ReaderService(ctx.session).list_recent(
            ctx.user_id,
            limit=data.limit,
        )
        items = [
            RecentReadItem(
                book_id=row.book_id,
                chapter_id=row.chapter_id,
                chapter_number=row.chapter_number,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
        return GetRecentlyReadOutput(items=items, total=len(items))
