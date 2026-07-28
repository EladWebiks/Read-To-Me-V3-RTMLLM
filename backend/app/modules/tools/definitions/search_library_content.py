"""search_library_content — FTS over owned chapter text + book metadata."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.library.schemas import LibraryContentHit, LibraryContentSearchResult
from app.modules.library.service import LibraryService
from app.modules.tools.base import BaseTool, RiskLevel, ToolContext


class SearchLibraryContentInput(BaseModel):
    """Topic / keyword query over the user's library."""

    query: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "Keywords or topic to find in owned books — searches chapter text "
            "and book title/author/description (not only the title)."
        ),
    )


class SearchLibraryContentTool(BaseTool):
    """Full-text search across the user's library content."""

    name = "search_library_content"
    description = (
        "Search the user's owned books by topic or keywords in chapter text and "
        "metadata. Use this when the user asks what a book is about, themes, "
        "plot elements, or anything that may not appear in the title. "
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
        return await LibraryService(ctx.session).search_content(
            ctx.user_id,
            data.query,
            limit=8,
        )


# Re-export hit type for tests / typing convenience.
__all__ = [
    "LibraryContentHit",
    "SearchLibraryContentInput",
    "SearchLibraryContentTool",
]
