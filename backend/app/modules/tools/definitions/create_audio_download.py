"""create_audio_download — confirmed chapter-range TTS download job."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.downloads.exceptions import InvalidChapterRangeError
from app.modules.downloads.schemas import DownloadCreate
from app.modules.downloads.service import DownloadService
from app.modules.library.exceptions import BookAccessDeniedError
from app.modules.library.service import LibraryService
from app.modules.tools.base import (
    BaseTool,
    ConfirmationPresentation,
    RiskLevel,
    ToolContext,
)
from app.modules.tools.exceptions import ToolAuthzError, ToolValidationError


class CreateAudioDownloadInput(BaseModel):
    """Range and TTS settings for a downloadable audio job."""

    book_id: UUID = Field(description="UUID of an owned book")
    chapter_from: int = Field(ge=0, description="First chapter number, inclusive")
    chapter_to: int = Field(ge=0, description="Last chapter number, inclusive")
    provider: Literal["edge", "sapi"] = Field(default="edge", description="TTS provider")
    voice: str | None = Field(default=None, description="TTS voice (blank uses provider default)")
    rate: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech rate")


class CreateAudioDownloadConfirmation(BaseModel):
    """User-editable range and TTS options."""

    chapter_from: int = Field(ge=0, description="First chapter number, inclusive")
    chapter_to: int = Field(ge=0, description="Last chapter number, inclusive")
    provider: Literal["edge", "sapi"] = Field(default="edge", description="TTS provider")
    voice: str | None = Field(default=None, description="TTS voice (blank uses provider default)")
    rate: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech rate")


class CreateAudioDownloadOutput(BaseModel):
    """Queued audio job details."""

    job_id: UUID
    book_id: UUID
    chapter_from: int
    chapter_to: int
    provider: str
    voice: str
    rate: str
    status: str
    total_count: int
    message: str


class CreateAudioDownloadTool(BaseTool):
    """Create a confirmed multi-chapter audio download."""

    name = "create_audio_download"
    description = (
        "Create downloadable MP3 audio for one or more chapters of an owned book. "
        "Use this when the user requests a chapter range, voice, provider, or speech rate. "
        "The user reviews and edits all audio options in a confirmation form before queuing."
    )
    input_model = CreateAudioDownloadInput
    output_model = CreateAudioDownloadOutput
    confirmation_schema = CreateAudioDownloadConfirmation
    risk_level = RiskLevel.CONFIRMATION_REQUIRED
    read_only = False
    touches_external = False
    allowed_in_internal_only = True
    timeout_ms = 20_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        data = CreateAudioDownloadInput.model_validate(inp.model_dump())
        try:
            await LibraryService(ctx.session).assert_access(ctx.user_id, data.book_id)
        except BookAccessDeniedError as exc:
            raise ToolAuthzError(str(exc)) from exc

    async def confirmation_presentation(
        self,
        inp: BaseModel,
        ctx: ToolContext,
    ) -> ConfirmationPresentation:
        data = CreateAudioDownloadInput.model_validate(inp.model_dump())
        return await _audio_presentation(ctx, data)

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        data = CreateAudioDownloadInput.model_validate(inp.model_dump())
        try:
            job = await DownloadService(ctx.session).create(
                ctx.user_id,
                DownloadCreate(
                    book_id=data.book_id,
                    chapter_from=data.chapter_from,
                    chapter_to=data.chapter_to,
                    provider=data.provider,
                    voice=data.voice,
                    rate=data.rate,
                ),
            )
        except InvalidChapterRangeError as exc:
            raise ToolValidationError(str(exc)) from exc
        return CreateAudioDownloadOutput(
            job_id=job.id,
            book_id=job.book_id,
            chapter_from=job.chapter_from,
            chapter_to=job.chapter_to,
            provider=job.provider,
            voice=job.voice,
            rate=job.rate,
            status=job.status,
            total_count=job.total_count,
            message=(
                f"Queued audio download for chapters {job.chapter_from}-{job.chapter_to} "
                f"using {job.provider} / {job.voice} at {job.rate}x."
            ),
        )


async def _audio_presentation(
    ctx: ToolContext,
    data: CreateAudioDownloadInput,
) -> ConfirmationPresentation:
    title: str | None = None
    try:
        book = await LibraryService(ctx.session).get_book(ctx.user_id, data.book_id)
        title = book.title
    except BookAccessDeniedError:
        title = None
    return ConfirmationPresentation(
        action="Create audio",
        title=title,
        subtitle=f"Chapters {data.chapter_from}-{data.chapter_to}",
    )
