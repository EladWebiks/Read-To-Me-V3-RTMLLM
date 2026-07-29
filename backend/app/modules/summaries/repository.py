"""Persistence for book summary cache rows."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.summaries.models import BookSummary
from app.modules.summaries.schemas import SummaryWrite


class SummaryRepository:
    """DB access for book_summaries only."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self,
        user_id: UUID,
        book_id: UUID,
        kind: str,
    ) -> BookSummary | None:
        """Return the active summary variant for this owner and book."""
        stmt = select(BookSummary).where(
            BookSummary.user_id == user_id,
            BookSummary.book_id == book_id,
            BookSummary.kind == kind,
            BookSummary.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, data: SummaryWrite) -> BookSummary:
        """Insert or refresh one cached variant."""
        row = await self.get(data.user_id, data.book_id, data.kind)
        if row is None:
            row = BookSummary(
                user_id=data.user_id,
                book_id=data.book_id,
                kind=data.kind,
                content=data.content,
                structured_data=data.structured_data,
                source="llm",
                provider=data.provider,
                model=data.model,
                prompt_version=data.prompt_version,
                content_hash=data.content_hash,
            )
            self._session.add(row)
        else:
            row.content = data.content
            row.structured_data = data.structured_data
            row.source = "llm"
            row.provider = data.provider
            row.model = data.model
            row.prompt_version = data.prompt_version
            row.content_hash = data.content_hash
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def search(
        self,
        user_id: UUID,
        query: str,
        *,
        limit: int,
    ) -> list[tuple[BookSummary, str]]:
        """FTS over this user's cached summary content."""
        document = func.to_tsvector("english", BookSummary.content)
        tsq = func.plainto_tsquery("english", query)
        headline = func.ts_headline(
            "english",
            BookSummary.content,
            tsq,
            "MaxWords=40, MinWords=12, ShortWord=2, HighlightAll=false",
        )
        stmt = (
            select(BookSummary, headline)
            .where(
                BookSummary.user_id == user_id,
                BookSummary.deleted_at.is_(None),
                document.op("@@")(tsq),
            )
            .order_by(func.ts_rank(document, tsq).desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [(row[0], str(row[1] or "")) for row in result.all()]

    async def soft_delete_for_book(self, user_id: UUID, book_id: UUID) -> None:
        """Soft-delete every summary variant for one owned book."""
        stmt = (
            update(BookSummary)
            .where(
                BookSummary.user_id == user_id,
                BookSummary.book_id == book_id,
                BookSummary.deleted_at.is_(None),
            )
            .values(deleted_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)
