"""play_chapter — set reading position and request client playback."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.modules.library.exceptions import BookAccessDeniedError
from app.modules.library.service import LibraryService
from app.modules.reader.schemas import ProgressUpsert
from app.modules.reader.service import ReaderService
from app.modules.tools.base import BaseTool, RiskLevel, ToolContext
from app.modules.tools.definitions.chapter_ref import (
    ChapterRefInput,
    book_id_for_ref,
    load_chapter,
)
from app.modules.tools.exceptions import ToolAuthzError


class PlayChapterOutput(BaseModel):
    """Playback intent for the client (B4 wires TTS UI)."""

    action: str = "play_chapter"
    book_id: UUID
    chapter_id: UUID
    chapter_number: int
    title: str
    progress_updated: bool
    message: str


class PlayChapterTool(BaseTool):
    """Prepare a chapter for playback and update reading progress."""

    name = "play_chapter"
    description = (
        "Start listening to a chapter the user owns. Sets reading progress to that "
        "chapter and returns a play action for the client player. "
        "Identify the chapter with chapter_id, or book_id + chapter_number."
    )
    input_model = ChapterRefInput
    output_model = PlayChapterOutput
    risk_level = RiskLevel.LOW_RISK
    read_only = False
    touches_external = False
    allowed_in_internal_only = True
    timeout_ms = 10_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        data = ChapterRefInput.model_validate(inp.model_dump())
        book_id = await book_id_for_ref(data, ctx)
        try:
            await LibraryService(ctx.session).assert_access(ctx.user_id, book_id)
        except BookAccessDeniedError as exc:
            raise ToolAuthzError(str(exc)) from exc

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        data = ChapterRefInput.model_validate(inp.model_dump())
        chapter = await load_chapter(data, ctx)
        await ReaderService(ctx.session).upsert_progress(
            ctx.user_id,
            chapter.book_id,
            ProgressUpsert(
                chapter_id=chapter.id,
                chapter_number=chapter.chapter_number,
                paragraph_index=0,
                word_index=0,
            ),
        )
        return PlayChapterOutput(
            book_id=chapter.book_id,
            chapter_id=chapter.id,
            chapter_number=chapter.chapter_number,
            title=chapter.title,
            progress_updated=True,
            message=(
                f"Ready to play chapter {chapter.chapter_number}"
                f"{f' ({chapter.title})' if chapter.title else ''}. "
                "Open the reader to hear TTS if playback UI is available."
            ),
        )
