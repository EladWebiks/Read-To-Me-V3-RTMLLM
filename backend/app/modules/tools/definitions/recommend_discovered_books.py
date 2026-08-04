"""recommend_discovered_books — batched discovery for “books like X”."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.modules.discovery.exceptions import DiscoveryRecommendError
from app.modules.discovery.schemas import DiscoveryRecommendItem
from app.modules.discovery.service import DiscoveryService
from app.modules.library.exceptions import BookAccessDeniedError
from app.modules.library.service import LibraryService
from app.modules.llm.service import LlmService
from app.modules.tools.base import BaseTool, RiskLevel, ToolContext
from app.modules.tools.exceptions import ToolAuthzError, ToolValidationError


class RecommendDiscoveredBooksInput(BaseModel):
    """One batched recommend across supported novel sites."""

    seed_book_id: UUID | None = Field(
        default=None,
        description="Owned library book to seed similar-book research from",
    )
    themes: list[str] = Field(
        default_factory=list,
        max_length=8,
        description=(
            "Tropes/genres of the seed book (e.g. cultivation, xianxia). For 'books "
            "like Against the Gods' pass themes like those — not the title itself. "
            "Alone is enough; LLM title research expands to known English titles, "
            "then scrape sources verify."
        ),
    )
    candidate_titles: list[str] = Field(
        default_factory=list,
        max_length=10,
        description=("Optional OTHER titles to search (not the seed title alone). Prefer themes."),
    )
    limit: int = Field(default=3, ge=1, le=10, description="Max ranked candidates to return")
    exclude_owned: bool = Field(
        default=True,
        description="Omit titles already in the user's library",
    )


class RecommendDiscoveredBooksOutput(BaseModel):
    """Ranked discovery candidates with evidence for clarify / import."""

    queries: list[str]
    themes: list[str]
    count: int
    results: list[DiscoveryRecommendItem]
    message: str


class RecommendDiscoveredBooksTool(BaseTool):
    """Batch-search supported sites for recommendation-style prompts."""

    name = "recommend_discovered_books"
    description = (
        "Find several scrapable similar books in ONE call for 'books like X' / theme "
        "prompts. REQUIRED for similarity/theme intent — do not use search_discovered_books. "
        "Pass themes describing the seed (cultivation, xianxia, revenge, …). Do NOT pass "
        "the seed book's own title as candidate_titles (especially not as the only "
        "candidate) — that finds title lookalikes. Prefer themes only, or several OTHER "
        "similar titles. Set limit to the requested count. Themes alone are enough "
        "(title research expands them; scrape sources verify). Then propose_choices and "
        "import_discovered_book. Requires external_allowed. One external budget unit for "
        "the whole batch. Never fall back to search_discovered_books for similarity. "
        "If title research fails or titles are not on supported sites, report the tool "
        "error — do not invent replacement titles."
    )
    input_model = RecommendDiscoveredBooksInput
    output_model = RecommendDiscoveredBooksOutput
    risk_level = RiskLevel.READ_ONLY
    read_only = True
    touches_external = True
    allowed_in_internal_only = False
    timeout_ms = 150_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        data = RecommendDiscoveredBooksInput.model_validate(inp.model_dump())
        if data.seed_book_id is None:
            return
        try:
            await LibraryService(ctx.session).assert_access(ctx.user_id, data.seed_book_id)
        except BookAccessDeniedError as exc:
            raise ToolAuthzError(str(exc)) from exc

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        data = RecommendDiscoveredBooksInput.model_validate(inp.model_dump())
        service = DiscoveryService(
            ctx.session,
            LlmService(ctx.session, get_settings()),
            conversation_id=ctx.conversation_id,
        )
        try:
            response = await service.recommend(
                ctx.user_id,
                seed_book_id=data.seed_book_id,
                themes=data.themes,
                candidate_titles=data.candidate_titles,
                limit=data.limit,
                exclude_owned=data.exclude_owned,
            )
        except DiscoveryRecommendError as exc:
            raise ToolValidationError(str(exc)) from exc
        except BookAccessDeniedError as exc:
            raise ToolAuthzError(str(exc)) from exc
        return RecommendDiscoveredBooksOutput(
            queries=response.queries,
            themes=response.themes,
            count=len(response.results),
            results=response.results,
            message=_message(response.results, response.queries),
        )


def _message(results: list[DiscoveryRecommendItem], queries: list[str]) -> str:
    if not results:
        if queries:
            sample = ", ".join(queries[:4])
            return (
                "No scrapable sources matched researched titles "
                f"({sample}…). Try different themes or known English titles."
            )
        return "No discovery recommendations matched the batch queries."
    rows = [_table_row(item) for item in results]
    return (
        f"Found {len(results)} scrapable recommendation(s). "
        "When tabulating for the user use ONLY these tool fields "
        "(chapters = scrapable on our sites, not encyclopedia totals):\n" + "\n".join(rows)
    )


def _table_row(item: DiscoveryRecommendItem) -> str:
    book = item.book
    author = book.author.strip() or "unknown author"
    chapters = item.scrapable_chapters
    ch = (
        f"{chapters} ch on supported sites"
        if chapters is not None
        else "unknown on supported sites"
    )
    source = book.sources[0].source if book.sources else "no source"
    return f"- {book.title} | {author} | {ch} ({source})"
