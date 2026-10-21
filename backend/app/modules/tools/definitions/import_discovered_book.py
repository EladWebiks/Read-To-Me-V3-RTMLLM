"""import_discovered_book — scrape from a discovery candidate (form HITL)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.discovery.exceptions import DiscoveredBookNotFoundError
from app.modules.discovery.service import DiscoveryService
from app.modules.scraping.exceptions import PreviewError, UnsupportedSourceError
from app.modules.scraping.registry import get_adapter, supported_source_names
from app.modules.scraping.schemas import ScrapeJobCreate
from app.modules.scraping.service import ScrapingService
from app.modules.tools.base import (
    BaseTool,
    ConfirmationPresentation,
    RiskLevel,
    ToolContext,
)
from app.modules.tools.exceptions import ToolValidationError


class ImportDiscoveredBookInput(BaseModel):
    """Discovery candidate id plus optional chapter window / source pick."""

    discovered_book_id: UUID = Field(
        description="Id from search_discovered_books or recommend_discovered_books results"
    )
    source_id: UUID | None = Field(
        default=None,
        description=("Optional book_sources.id. Omit to use the recommended (richest) source."),
    )
    exclude_sources: list[str] = Field(
        default_factory=list,
        max_length=10,
        description=(
            "Site names the user said to avoid ('not from X'). "
            f"Supported: {supported_source_names()}. Picks the richest remaining source."
        ),
    )
    start_chapter: int | None = Field(
        default=1,
        ge=0,
        description="Starting chapter (default 1)",
    )
    chapter_count: int | None = Field(
        default=None,
        ge=1,
        le=5000,
        description=(
            "Chapter count to scrape; null = entire book from start. "
            "If the user gives an end chapter, set count = end - start + 1."
        ),
    )


class ImportDiscoveredBookConfirm(BaseModel):
    """User-editable HITL form fields (URL comes from discovery)."""

    start_chapter: int | None = Field(
        default=1,
        ge=0,
        description="Starting chapter",
    )
    chapter_count: int | None = Field(
        default=None,
        ge=1,
        le=5000,
        description="Amount of chapters (empty = entire book)",
    )


class ImportDiscoveredBookOutput(BaseModel):
    """Queued scrape job from a discovery import."""

    job_id: UUID
    book_id: UUID | None
    title: str
    source: str
    book_url: str
    status: str
    mode: str
    chapter_from: int | None
    max_chapters: int | None
    message: str


class ImportDiscoveredBookTool(BaseTool):
    """Import a discovered title via scrape after form confirmation (no pasted URL)."""

    name = "import_discovered_book"
    description = (
        "Import/scrape a book chosen from search_discovered_books or "
        "recommend_discovered_books into the library. "
        "Pass discovered_book_id from search results. Omit source_id to use the "
        "recommended source (prefer more chapters when known). When the user says "
        "not from / avoid / except a site, pass exclude_sources with those names — "
        "do not import from an excluded site. "
        "Do not ask for a site URL. Map any chapter range into start_chapter and "
        "chapter_count; the user confirms on a form. Defaults: start_chapter=1, "
        "chapter_count=null (entire book)."
    )
    input_model = ImportDiscoveredBookInput
    output_model = ImportDiscoveredBookOutput
    confirmation_schema = ImportDiscoveredBookConfirm
    risk_level = RiskLevel.CONFIRMATION_REQUIRED
    read_only = False
    touches_external = True
    allowed_in_internal_only = False
    timeout_ms = 60_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        data = ImportDiscoveredBookInput.model_validate(inp.model_dump())
        try:
            _book, src = await DiscoveryService(ctx.session).pick_source(
                ctx.user_id,
                data.discovered_book_id,
                data.source_id,
                exclude_sources=tuple(data.exclude_sources),
            )
        except DiscoveredBookNotFoundError as exc:
            raise ToolValidationError(_import_source_error(str(exc))) from exc
        try:
            get_adapter(src.book_url)
        except UnsupportedSourceError as exc:
            raise ToolValidationError(str(exc)) from exc

    async def confirmation_presentation(
        self,
        inp: BaseModel,
        ctx: ToolContext,
    ) -> ConfirmationPresentation:
        data = ImportDiscoveredBookInput.model_validate(inp.model_dump())
        return await _import_presentation(ctx, data)

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        data = ImportDiscoveredBookInput.model_validate(inp.model_dump())
        try:
            book, src = await DiscoveryService(ctx.session).pick_source(
                ctx.user_id,
                data.discovered_book_id,
                data.source_id,
                exclude_sources=tuple(data.exclude_sources),
            )
        except DiscoveredBookNotFoundError as exc:
            raise ToolValidationError(_import_source_error(str(exc))) from exc
        create = _to_job_create(src.book_url, data.start_chapter, data.chapter_count)
        try:
            job = await ScrapingService(ctx.session).create_job(ctx.user_id, create)
        except (UnsupportedSourceError, PreviewError) as exc:
            raise ToolValidationError(str(exc)) from exc
        return ImportDiscoveredBookOutput(
            job_id=job.id,
            book_id=job.book_id,
            title=book.title,
            source=src.source,
            book_url=src.book_url,
            status=job.status,
            mode=job.mode,
            chapter_from=job.chapter_from,
            max_chapters=job.max_chapters,
            message=_queued_message(
                book.title,
                src.source,
                job.chapter_from,
                job.max_chapters,
                job.status,
            ),
        )


async def _import_presentation(
    ctx: ToolContext,
    data: ImportDiscoveredBookInput,
) -> ConfirmationPresentation:
    try:
        book, src = await DiscoveryService(ctx.session).pick_source(
            ctx.user_id,
            data.discovered_book_id,
            data.source_id,
            exclude_sources=tuple(data.exclude_sources),
        )
    except DiscoveredBookNotFoundError:
        return ConfirmationPresentation(action="Import book")
    return ConfirmationPresentation(
        action="Import book",
        title=book.title,
        subtitle=src.source,
    )


def _import_source_error(raw: str) -> str:
    if "no-sources-after-exclude:" in raw:
        names = raw.rsplit(":", 1)[-1]
        return (
            f"No scrape sources left after excluding {names}. "
            "Try another title or allow one of those sites."
        )
    return raw


def _to_job_create(
    url: str,
    start_chapter: int | None,
    chapter_count: int | None,
) -> ScrapeJobCreate:
    start = 1 if start_chapter is None else start_chapter
    if chapter_count is None:
        return ScrapeJobCreate(
            url=url,
            mode="full",
            chapter_from=start,
            starting_chapter=start,
            max_chapters=None,
        )
    return ScrapeJobCreate(
        url=url,
        mode="range",
        chapter_from=start,
        starting_chapter=start,
        max_chapters=chapter_count,
    )


def _queued_message(
    title: str,
    source: str,
    chapter_from: int | None,
    max_chapters: int | None,
    status: str,
) -> str:
    start = 1 if chapter_from is None else chapter_from
    if max_chapters is None:
        window = f"from chapter {start} to the end of the book"
    else:
        end = start + max_chapters - 1
        window = f"chapters {start}-{end} ({max_chapters} chapters)"
    return (
        f'Queued "{title}" via {source} — {window}. Job status: {status}. '
        "Open the Scraper page to watch progress; chapters show up in your library "
        "as they finish."
    )
