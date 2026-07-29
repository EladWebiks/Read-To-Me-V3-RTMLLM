"""get_book_summary — read a fresh persisted summary without an LLM call."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.library.exceptions import BookAccessDeniedError
from app.modules.library.service import LibraryService
from app.modules.summaries.schemas import SummaryKind
from app.modules.summaries.service import SummaryService
from app.modules.tools.base import BaseTool, RiskLevel, ToolContext
from app.modules.tools.exceptions import ToolAuthzError


class GetBookSummaryInput(BaseModel):
    """Select an owned book and summary style."""

    book_id: UUID = Field(description="UUID of a book the user owns")
    kind: Literal["no_spoiler", "full"] = Field(
        default="no_spoiler",
        description="no_spoiler (default) or full",
    )


class GetBookSummaryOutput(BaseModel):
    """Fresh cache state; stale content is never returned."""

    book_id: UUID
    kind: SummaryKind
    found: bool
    stale: bool
    summary: str | None = None
    themes: list[str] = Field(default_factory=list)
    setting: str = ""
    tropes: list[str] = Field(default_factory=list)


class GetBookSummaryTool(BaseTool):
    """Read a cached summary for an owned book."""

    name = "get_book_summary"
    description = (
        "Read a cached summary for an owned book without generating one. "
        "Use no_spoiler unless the user explicitly requests full plot spoilers. "
        "If found=false or stale=true, call summarize_book."
    )
    input_model = GetBookSummaryInput
    output_model = GetBookSummaryOutput
    risk_level = RiskLevel.READ_ONLY
    read_only = True
    touches_external = False
    allowed_in_internal_only = True
    timeout_ms = 15_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        data = GetBookSummaryInput.model_validate(inp.model_dump())
        try:
            await LibraryService(ctx.session).assert_access(ctx.user_id, data.book_id)
        except BookAccessDeniedError as exc:
            raise ToolAuthzError(str(exc)) from exc

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        data = GetBookSummaryInput.model_validate(inp.model_dump())
        kind = SummaryKind(data.kind)
        result = await SummaryService(ctx.session).lookup(ctx.user_id, data.book_id, kind)
        if result.summary is None:
            return GetBookSummaryOutput(
                book_id=data.book_id,
                kind=kind,
                found=result.found,
                stale=result.stale,
            )
        structured = result.summary.structured_data
        return GetBookSummaryOutput(
            book_id=data.book_id,
            kind=kind,
            found=True,
            stale=False,
            summary=result.summary.content,
            themes=_strings(structured.get("themes")),
            setting=str(structured.get("setting", "")),
            tropes=_strings(structured.get("tropes")),
        )


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
