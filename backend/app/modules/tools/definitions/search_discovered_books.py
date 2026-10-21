"""search_discovered_books — title search across discovery sources."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.discovery.schemas import DiscoveredBookRead
from app.modules.discovery.service import DiscoveryService
from app.modules.scraping.registry import supported_source_names
from app.modules.tools.base import BaseTool, RiskLevel, ToolContext


class SearchDiscoveredBooksInput(BaseModel):
    """Title / alias query for discovery search."""

    query: str = Field(min_length=1, max_length=200, description="Book title or alias to find")
    limit: int = Field(default=8, ge=1, le=20, description="Max candidates to return")


class SearchDiscoveredBooksOutput(BaseModel):
    """Discovery candidates for clarify / import."""

    query: str
    count: int
    results: list[DiscoveredBookRead]
    message: str


class SearchDiscoveredBooksTool(BaseTool):
    """Search supported sites by title; persist candidates for later import."""

    name = "search_discovered_books"
    description = (
        "Search for ONE book by exact title/alias on supported novel sites "
        f"({supported_source_names()}) when the user named that specific title "
        "(not 'books like X'), including follow-ups like 'what is X about?' for a "
        "title you previously recommended. For similarity/theme prompts use "
        "recommend_discovered_books instead. Returns candidates with ranked sources "
        "(recommended = richest known chapter count). Site blurbs are often empty — "
        "still return matches so you can answer with sources/ids; for premise see "
        "system grounding rules. If several title matches, call propose_choices, then "
        "import_discovered_book. Requires external_allowed mode."
    )
    input_model = SearchDiscoveredBooksInput
    output_model = SearchDiscoveredBooksOutput
    risk_level = RiskLevel.READ_ONLY
    read_only = True
    touches_external = True
    allowed_in_internal_only = False
    timeout_ms = 30_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        pass

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        data = SearchDiscoveredBooksInput.model_validate(inp.model_dump())
        response = await DiscoveryService(ctx.session).search_by_title(
            ctx.user_id,
            data.query,
            external=True,
            limit=data.limit,
        )
        visible = [row for row in response.results if not row.already_owned] or response.results
        return SearchDiscoveredBooksOutput(
            query=response.query,
            count=len(visible),
            results=visible,
            message=_message(response.query, visible),
        )


def _message(query: str, results: list[DiscoveredBookRead]) -> str:
    if not results:
        return f"No discovery matches for '{query}'."
    labels: list[str] = []
    for row in results[:5]:
        labels.append(_label(row))
    return f"Found {len(results)} candidate(s) for '{query}': {', '.join(labels)}."


def _label(row: DiscoveredBookRead) -> str:
    if not row.sources:
        return row.title
    top = row.sources[0]
    if top.chapter_count_estimate is not None:
        return f"{row.title} ({top.source} ~{top.chapter_count_estimate} ch)"
    return f"{row.title} ({top.source})"
