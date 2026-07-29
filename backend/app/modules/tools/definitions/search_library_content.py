"""search_library_content — FTS over owned chapter text + book metadata."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.library.schemas import LibraryContentHit, LibraryContentSearchResult
from app.modules.library.service import LibraryService
from app.modules.summaries.service import SummaryService
from app.modules.tools.base import BaseTool, RiskLevel, ToolContext


class SearchLibraryContentInput(BaseModel):
    """Topic / keyword query over the user's library."""

    query: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "Keywords or topic to find in owned books — searches fresh summaries, "
            "chapter text, and book title/author/description."
        ),
    )


class SearchLibraryContentTool(BaseTool):
    """Full-text search across the user's library content."""

    name = "search_library_content"
    description = (
        "Search the user's owned books by topic or keywords. Fresh cached summaries "
        "are preferred, then metadata and chapter text. Use this for themes, "
        "plot elements, or anything that may not appear in a title. "
        "Returns short snippets only — not full chapters."
    )
    input_model = SearchLibraryContentInput
    output_model = LibraryContentSearchResult
    risk_level = RiskLevel.READ_ONLY
    read_only = True
    touches_external = False
    allowed_in_internal_only = True
    timeout_ms = 15_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        """Scoped to ctx.user_id inside LibraryService.search_content."""

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        data = SearchLibraryContentInput.model_validate(inp.model_dump())
        summary_rows = await SummaryService(ctx.session).search(
            ctx.user_id,
            data.query,
            limit=8,
        )
        summary_hits = [
            LibraryContentHit(
                book_id=row.book_id,
                book_title=row.book_title,
                match_source="summary",
                snippet=row.snippet,
            )
            for row in summary_rows
        ]
        fallback = await LibraryService(ctx.session).search_content(
            ctx.user_id,
            data.query,
            limit=8,
        )
        summarized = {hit.book_id for hit in summary_hits}
        other_hits = [hit for hit in fallback.hits if hit.book_id not in summarized]
        hits = (summary_hits + other_hits)[:8]
        return LibraryContentSearchResult(hits=hits, total=len(hits))


# Re-export hit type for tests / typing convenience.
__all__ = [
    "LibraryContentHit",
    "SearchLibraryContentInput",
    "SearchLibraryContentTool",
]
