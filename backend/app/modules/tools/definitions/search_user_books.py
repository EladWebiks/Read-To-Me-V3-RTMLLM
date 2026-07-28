"""search_user_books — list/filter books in the user's library."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.books.schemas import BookRead
from app.modules.library.service import LibraryService
from app.modules.tools.base import BaseTool, RiskLevel, ToolContext


class SearchUserBooksInput(BaseModel):
    """Optional substring filter over title/author."""

    query: str | None = Field(
        default=None,
        description="Optional case-insensitive filter matched against title, author, or description",
    )


class BookSummary(BaseModel):
    """Compact book row for the model."""

    id: UUID
    title: str
    author: str
    language: str
    chapter_count: int
    status: str


class SearchUserBooksOutput(BaseModel):
    """Owned library books (optionally filtered)."""

    books: list[BookSummary]
    total: int


class SearchUserBooksTool(BaseTool):
    """List books the authenticated user owns."""

    name = "search_user_books"
    description = (
        "List or filter books in the user's personal library by title, author, or "
        "description. For themes/plot/content inside chapters, use search_library_content."
    )
    input_model = SearchUserBooksInput
    output_model = SearchUserBooksOutput
    risk_level = RiskLevel.READ_ONLY
    read_only = True
    touches_external = False
    allowed_in_internal_only = True
    timeout_ms = 10_000

    async def authorize(self, inp: BaseModel, ctx: ToolContext) -> None:
        """Library list is always scoped to ctx.user_id — nothing to check."""

    async def execute(self, inp: BaseModel, ctx: ToolContext) -> BaseModel:
        data = SearchUserBooksInput.model_validate(inp.model_dump())
        books = await LibraryService(ctx.session).list_books(ctx.user_id)
        filtered = _filter_books(books, data.query)
        rows = [
            BookSummary(
                id=b.id,
                title=b.title,
                author=b.author,
                language=b.language,
                chapter_count=b.chapter_count,
                status=b.status,
            )
            for b in filtered
        ]
        return SearchUserBooksOutput(books=rows, total=len(rows))


def _filter_books(books: list[BookRead], query: str | None) -> list[BookRead]:
    if not query or not query.strip():
        return list(books)
    needle = query.strip().lower()
    return [
        book
        for book in books
        if needle in book.title.lower()
        or needle in book.author.lower()
        or needle in book.description.lower()
    ]
