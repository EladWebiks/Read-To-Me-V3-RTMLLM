"""scrape_book_range — gated scrape job (form HITL)."""

from __future__ import annotations

from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.scraping.exceptions import PreviewError, UnsupportedSourceError
from app.modules.scraping.registry import get_adapter
from app.modules.scraping.schemas import ScrapeJobCreate
from app.modules.scraping.service import ScrapingService
from app.modules.tools.base import (
    BaseTool,
    ConfirmationPresentation,
    RiskLevel,
    ToolContext,
)
from app.modules.tools.exceptions import ToolValidationError


class ScrapeBookRangeInput(BaseModel):
    """URL plus optional chapter window."""

    url: str = Field(
        min_length=8,
        max_length=2048,
        description="Book or chapter URL on a supported source",
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


class ScrapeBookRangeConfirm(BaseModel):
    """User-editable HITL form fields."""

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


class ScrapeBookRangeOutput(BaseModel):
    """Queued scrape job summary."""

    job_id: UUID
    book_id: UUID | None
    title: str
    status: str
    mode: str
    chapter_from: int | None
    max_chapters: int | None
    message: str


class ScrapeBookRangeTool(BaseTool):
    """Enqueue a scrape after user form confirmation."""

    name = "scrape_book_range"
    description = (
        "Import/scrape a book from a supported novel-site URL into the user's library. "
        "Call when the user provides a URL and wants to add/scrape/import. "
        "Map any chapter range they already stated into start_chapter and "
        "chapter_count (count = end - start + 1 when both ends are given; "
        "null count = entire book). Do not ask for those in chat — the user "
        "confirms or edits on a form. Defaults if unspecified: start_chapter=1, "
        "chapter_count=null."
    )
    input_model = ScrapeBookRangeInput
    output_model = ScrapeBookRangeOutput
    confirmation_schema = ScrapeBookRangeConfirm
    risk_level = RiskLevel.CONFIRMATION_REQUIRED
    read_only = False
    touches_external = True
    allowed_in_internal_only = False
    timeout_ms = 60_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        data = ScrapeBookRangeInput.model_validate(inp.model_dump())
        try:
            get_adapter(data.url)
        except UnsupportedSourceError as exc:
            raise ToolValidationError(str(exc)) from exc

    async def confirmation_presentation(
        self,
        inp: BaseModel,
        ctx: ToolContext,
    ) -> ConfirmationPresentation:
        data = ScrapeBookRangeInput.model_validate(inp.model_dump())
        return await _scrape_presentation(ctx, data.url)

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        data = ScrapeBookRangeInput.model_validate(inp.model_dump())
        create = _to_job_create(data)
        try:
            job = await ScrapingService(ctx.session).create_job(ctx.user_id, create)
        except (UnsupportedSourceError, PreviewError) as exc:
            raise ToolValidationError(str(exc)) from exc
        title = await _job_title(ctx, job.book_id)
        return ScrapeBookRangeOutput(
            job_id=job.id,
            book_id=job.book_id,
            title=title,
            status=job.status,
            mode=job.mode,
            chapter_from=job.chapter_from,
            max_chapters=job.max_chapters,
            message=_queued_message(title, job.chapter_from, job.max_chapters, job.status),
        )


async def _job_title(ctx: ToolContext, book_id: UUID | None) -> str:
    from app.modules.library.exceptions import BookAccessDeniedError
    from app.modules.library.service import LibraryService

    if book_id is None:
        return "book"
    try:
        book = await LibraryService(ctx.session).get_book(ctx.user_id, book_id)
    except BookAccessDeniedError:
        return "book"
    return book.title


async def _scrape_presentation(ctx: ToolContext, url: str) -> ConfirmationPresentation:
    host = urlparse(url).netloc or url
    try:
        preview = await ScrapingService(ctx.session).preview(url)
    except (UnsupportedSourceError, PreviewError):
        return ConfirmationPresentation(action="Scrape book", subtitle=host)
    return ConfirmationPresentation(
        action="Scrape book",
        title=preview.title,
        subtitle=preview.source or host,
    )


def _queued_message(
    title: str,
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
        f'Queued "{title}" - {window}. Job status: {status}. '
        "Open the Scraper page to watch progress; chapters show up in your library "
        "as they finish."
    )


def _to_job_create(data: ScrapeBookRangeInput) -> ScrapeJobCreate:
    start = 1 if data.start_chapter is None else data.start_chapter
    if data.chapter_count is None:
        return ScrapeJobCreate(
            url=data.url,
            mode="full",
            chapter_from=start,
            starting_chapter=start,
            max_chapters=None,
        )
    return ScrapeJobCreate(
        url=data.url,
        mode="range",
        chapter_from=start,
        starting_chapter=start,
        max_chapters=data.chapter_count,
    )
