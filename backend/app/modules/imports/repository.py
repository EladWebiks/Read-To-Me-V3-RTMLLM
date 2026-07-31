"""DB access for the imports module's tables only (epub_imports)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.imports.models import EpubImportRecord


class EpubImportRepository:
    """Durable log of EPUB import attempts (golden rule 7)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user_id: UUID) -> EpubImportRecord:
        record = EpubImportRecord(user_id=user_id)
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def set_terminal(
        self,
        record_id: UUID,
        *,
        status: str,
        chapter_count: int,
        book_id: UUID | None = None,
    ) -> None:
        record = await self._session.get(EpubImportRecord, record_id)
        if record is None:
            return
        record.status = status
        record.chapter_count = chapter_count
        if book_id is not None:
            record.book_id = book_id
        await self._session.flush()

    async def completed_in_period(
        self,
        user_id: UUID,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        """Completed imports in the window; failures are usually our bugs (§3.5)."""
        stmt = select(func.count(EpubImportRecord.id)).where(
            EpubImportRecord.user_id == user_id,
            EpubImportRecord.status == "completed",
            EpubImportRecord.created_at >= period_start,
            EpubImportRecord.created_at < period_end,
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def completed_for_users(
        self,
        user_ids: list[UUID],
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> dict[UUID, int]:
        """Per-user completed-import counts for the backoffice usage table."""
        if not user_ids:
            return {}
        stmt = (
            select(EpubImportRecord.user_id, func.count(EpubImportRecord.id))
            .where(
                EpubImportRecord.user_id.in_(user_ids),
                EpubImportRecord.status == "completed",
                EpubImportRecord.created_at >= period_start,
                EpubImportRecord.created_at < period_end,
            )
            .group_by(EpubImportRecord.user_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return {row[0]: int(row[1]) for row in rows}
