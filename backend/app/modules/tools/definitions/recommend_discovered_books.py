"""recommend_discovered_books — batched discovery for “books like X”."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.modules.discovery.exceptions import DiscoveryRecommendError
from app.modules.discovery.schemas import DiscoveryRecommendItem
from app.modules.discovery.service import DiscoveryService, RecommendSpec
from app.modules.library.exceptions import BookAccessDeniedError
from app.modules.library.service import LibraryService
from app.modules.llm.service import LlmService
from app.modules.scraping.registry import supported_source_names
from app.modules.tools.base import BaseTool, RiskLevel, ToolContext
from app.modules.tools.definitions.recommend_excludes import (
    merge_exclude_titles,
    prior_recommend_exclude_titles,
)
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
        max_length=25,
        description=("Optional OTHER titles to search (not the seed title alone). Prefer themes."),
    )
    limit: int = Field(
        default=3,
        ge=1,
        le=25,
        description="How many ranked candidates to return (honor the user's count, max 25)",
    )
    exclude_owned: bool = Field(
        default=True,
        description="Omit titles already in the user's library",
    )
    exclude_titles: list[str] = Field(
        default_factory=list,
        max_length=50,
        description=(
            "Optional titles to skip. Server also auto-excludes titles already returned "
            "by recommend_discovered_books in this conversation."
        ),
    )
    source: str | None = Field(
        default=None,
        description=(
            "Optional scrape site name to require "
            f"({supported_source_names()}). Example: ranobes — only books found on "
            "that site. book_url is returned for import / only show if user asked "
            "for links."
        ),
    )
    exclude_sources: list[str] = Field(
        default_factory=list,
        max_length=10,
        description=(
            "Site names to avoid when the user says 'not from X' / 'except X' "
            f"({supported_source_names()}). Example: ['novelfire','novellunar']."
        ),
    )
    min_chapters: int | None = Field(
        default=None,
        ge=1,
        le=50_000,
        description="Optional minimum scrapable chapter estimate (e.g. 500).",
    )


class RecommendListItem(BaseModel):
    """Compact recommend row for the model (keeps tool payloads under truncate limits)."""

    discovered_book_id: UUID
    title: str
    author: str
    scrapable_chapters: int | None = None
    source: str | None = None
    book_url: str | None = None
    premise: str = ""


class RecommendDiscoveredBooksOutput(BaseModel):
    """Ranked discovery candidates with evidence for clarify / import."""

    themes: list[str]
    count: int
    results: list[RecommendListItem]
    message: str


class RecommendDiscoveredBooksTool(BaseTool):
    """Batch-search supported sites for recommendation-style prompts."""

    name = "recommend_discovered_books"
    description = (
        "Find several scrapable similar books in ONE call for 'books like X' / theme "
        "prompts. Searches supported sites "
        f"({supported_source_names()}). REQUIRED for similarity/theme intent — do not "
        "use search_discovered_books. Pass themes describing the seed (cultivation, "
        "xianxia, revenge, …). Do NOT pass the seed book's own title as "
        "candidate_titles (especially not as the only candidate) — that finds title "
        "lookalikes. Prefer themes only, or several OTHER similar titles. Set limit to "
        "the exact count the user asked for (1-25). Prior suggestions in this chat are "
        "auto-excluded; still pass exclude_titles when you know them. When the user "
        "names a site (e.g. ranobes) set source to that name; when they say not from / "
        "avoid / except a site, pass exclude_sources with those names and never re-use "
        "an excluded site. When they require a "
        "chapter floor (e.g. over 500) set min_chapters. Themes alone are "
        "enough (title research expands them; scrape sources verify). Then "
        "propose_choices and import_discovered_book. Requires external_allowed. "
        "One external budget unit for the whole batch. Never fall back to "
        "search_discovered_books for similarity. Present ONLY titles from this tool's "
        "message table (all count rows) — if count is below the requested limit, say "
        "so; never invent fillers or echo JSON. Rows include url: when known — show "
        "links ONLY if the user asked, and then paste that exact url (never invent "
        "slugs/IDs). Reformatting a prior list: reuse those same titles + urls; do not "
        "call this tool again just for a table. Import via discovered_book_id from "
        "results. If title research fails or titles are not on supported sites, report "
        "the tool error — do not invent replacement titles."
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
        prior = await prior_recommend_exclude_titles(
            ctx.session,
            user_id=ctx.user_id,
            conversation_id=ctx.conversation_id,
        )
        excluded = merge_exclude_titles(list(data.exclude_titles), prior)
        service = DiscoveryService(
            ctx.session,
            LlmService(ctx.session, get_settings()),
            conversation_id=ctx.conversation_id,
        )
        try:
            response = await service.recommend(
                ctx.user_id,
                RecommendSpec(
                    seed_book_id=data.seed_book_id,
                    themes=tuple(data.themes),
                    candidate_titles=tuple(data.candidate_titles),
                    limit=data.limit,
                    exclude_owned=data.exclude_owned,
                    exclude_titles=tuple(excluded),
                    source=data.source,
                    exclude_sources=tuple(data.exclude_sources),
                    min_chapters=data.min_chapters,
                ),
            )
        except DiscoveryRecommendError as exc:
            raise ToolValidationError(str(exc)) from exc
        except BookAccessDeniedError as exc:
            raise ToolAuthzError(str(exc)) from exc
        return RecommendDiscoveredBooksOutput(
            themes=response.themes,
            count=len(response.results),
            results=[_slim_item(item) for item in response.results],
            message=_message(response.results, response.queries, requested=data.limit),
        )


def _slim_item(item: DiscoveryRecommendItem) -> RecommendListItem:
    book = item.book
    top = book.sources[0] if book.sources else None
    return RecommendListItem(
        discovered_book_id=book.id,
        title=book.title,
        author=book.author.strip() or "unknown author",
        scrapable_chapters=item.scrapable_chapters,
        source=top.source if top else None,
        book_url=top.book_url if top else None,
        premise=_premise_snippet(item),
    )


def _message(
    results: list[DiscoveryRecommendItem],
    queries: list[str],
    *,
    requested: int,
) -> str:
    if not results:
        if queries:
            sample = ", ".join(queries[:4])
            return (
                "No scrapable sources matched researched titles "
                f"({sample}…). Try different themes or known English titles."
            )
        return "No discovery recommendations matched the batch queries."
    rows = [_table_row(item) for item in results]
    shortfall = ""
    if len(results) < requested:
        shortfall = (
            f" Only {len(results)} scrapable matches (user asked for {requested}). "
            "List ONLY these — do not invent more titles or encyclopedia chapter counts."
        )
    return (
        f"Found {len(results)} scrapable recommendation(s).{shortfall} "
        "Present EVERY title in the SAME format. Default (no links asked): title — "
        "author — chapters only. If the user asked for links/URLs/a link column: add "
        "the exact `url:` value from each row as the href (visible text may be the "
        "full URL); NEVER invent or guess ranobes/novel URLs; if a row has no url, "
        "say so instead of fabricating one. Do not invent chapter counts:\n" + "\n".join(rows)
    )


_PREMISE_MAX = 120


def _table_row(item: DiscoveryRecommendItem) -> str:
    book = item.book
    author = book.author.strip() or "unknown author"
    chapters = item.scrapable_chapters
    ch = f"~{chapters} chapters" if chapters is not None else "chapters unknown"
    line = f"- {book.title} — {author} — {ch}"
    top = book.sources[0] if book.sources else None
    if top is not None and top.book_url.strip():
        line = f"{line} — url: {top.book_url.strip()}"
    premise = _premise_snippet(item)
    return f"{line} — {premise}" if premise else line


def _premise_snippet(item: DiscoveryRecommendItem) -> str:
    desc = " ".join(item.book.description.split()).strip()
    if desc:
        return _clip(desc, _PREMISE_MAX)
    for reason in item.evidence:
        cleaned = reason.strip()
        if cleaned.lower().startswith("title research:"):
            cleaned = cleaned.split(":", 1)[1].strip()
        if cleaned and cleaned.lower() != "title research":
            return _clip(cleaned, _PREMISE_MAX)
    return ""


def _clip(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"
