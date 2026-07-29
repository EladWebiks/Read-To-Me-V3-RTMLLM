"""summarize_book — ensure a fresh persisted summary for an owned book."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.modules.library.exceptions import BookAccessDeniedError
from app.modules.library.service import LibraryService
from app.modules.llm.service import LlmService
from app.modules.summaries.exceptions import SummaryUnavailableError
from app.modules.summaries.schemas import SummaryKind
from app.modules.summaries.service import SummaryService
from app.modules.tools.base import BaseTool, RiskLevel, ToolContext
from app.modules.tools.exceptions import ToolAuthzError, ToolValidationError


class SummarizeBookInput(BaseModel):
    """Select an owned book and summary style."""

    book_id: UUID = Field(description="UUID of a book the user owns")
    kind: Literal["no_spoiler", "full"] = Field(
        default="no_spoiler",
        description="no_spoiler (default) or full",
    )


class SummarizeBookOutput(BaseModel):
    """Fresh generated or cached summary."""

    book_id: UUID
    kind: SummaryKind
    summary: str
    themes: list[str] = Field(default_factory=list)
    setting: str = ""
    tropes: list[str] = Field(default_factory=list)
    cached: bool


class SummarizeBookTool(BaseTool):
    """Generate on demand, or reuse an unchanged summary."""

    name = "summarize_book"
    description = (
        "Generate and persist a summary for an owned book, or reuse the cache when "
        "chapter content is unchanged. Use no_spoiler by default; use full only when "
        "the user explicitly permits spoilers."
    )
    input_model = SummarizeBookInput
    output_model = SummarizeBookOutput
    risk_level = RiskLevel.LOW_RISK
    read_only = False
    touches_external = False
    allowed_in_internal_only = True
    timeout_ms = 55_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        data = SummarizeBookInput.model_validate(inp.model_dump())
        try:
            await LibraryService(ctx.session).assert_access(ctx.user_id, data.book_id)
        except BookAccessDeniedError as exc:
            raise ToolAuthzError(str(exc)) from exc

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        data = SummarizeBookInput.model_validate(inp.model_dump())
        service = SummaryService(
            ctx.session,
            LlmService(ctx.session, get_settings()),
        )
        kind = SummaryKind(data.kind)
        try:
            result = await service.ensure(
                ctx.user_id,
                data.book_id,
                kind,
                conversation_id=ctx.conversation_id,
            )
        except SummaryUnavailableError as exc:
            raise ToolValidationError(str(exc)) from exc
        structured = result.summary.structured_data
        return SummarizeBookOutput(
            book_id=data.book_id,
            kind=kind,
            summary=result.summary.content,
            themes=_strings(structured.get("themes")),
            setting=str(structured.get("setting", "")),
            tropes=_strings(structured.get("tropes")),
            cached=result.cached,
        )


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
