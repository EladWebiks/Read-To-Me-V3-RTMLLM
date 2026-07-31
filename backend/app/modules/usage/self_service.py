"""Self-serve usage composition.

COMPOSITION LAYER: with rollup.py, one of exactly two usage files allowed to
import domain services (spec 2026-07-31-quota-usage-ux §3.2 amendment).
read_service.py stays pure so domain services can import it cycle-free.
usage never imports orchestration.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.downloads.service import DownloadService
from app.modules.imports.service import ImportService
from app.modules.llm.service import LlmService
from app.modules.quotas.kinds import KIND_REGISTRY, QuotaKind
from app.modules.quotas.service import QuotaService
from app.modules.scraping.service import ScrapingService
from app.modules.usage.read_service import UsageReadService
from app.modules.usage.schemas import MeUsageKindRead, MeUsageResponse
from app.modules.users.schemas import UserRead


class SelfUsageService:
    """Compose per-kind hybrid usage + resolved limits for one user."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._llm = LlmService(session, settings)
        self._reads = UsageReadService(session)

    async def usage_for(self, user: UserRead) -> MeUsageResponse:
        now = datetime.now(UTC)
        _, month_end = QuotaService.current_month_window(now)
        _, today_start = UsageReadService.hybrid_split(now)
        limits = await QuotaService(self._session).limits_for(user)
        kinds = [
            MeUsageKindRead(
                kind=kind,
                label=meta.label,
                unit=meta.unit,
                window=meta.window,
                used=await self._used(kind, user.id, now, today_start, month_end),
                limit=limits.limit(kind),
            )
            for kind, meta in KIND_REGISTRY.items()
        ]
        return MeUsageResponse(
            membership=user.membership.value,
            exempt=limits.exempt,
            as_of=now,
            resets_at=month_end,
            kinds=kinds,
        )

    async def _used(
        self, kind: QuotaKind, user_id: UUID, now: datetime, start: datetime, end: datetime
    ) -> float:
        """Hybrid month amount, or the live level for storage (never rolled)."""
        if kind is QuotaKind.STORAGE_BYTES:
            return float(await DownloadService(self._session).stored_bytes(user_id))
        rolled = await self._reads.rolled_month_amount(user_id, kind, now)
        return rolled + await self._today_tail(kind, user_id, start, end)

    async def _today_tail(
        self, kind: QuotaKind, user_id: UUID, start: datetime, end: datetime
    ) -> float:
        if kind in (QuotaKind.LLM_TOKENS, QuotaKind.LLM_COST_USD):
            return await self._llm_tail(kind, user_id, start, end)
        if kind is QuotaKind.AUDIO_CHAPTERS:
            downloads = DownloadService(self._session)
            return float(
                await downloads.chapters_in_period(user_id, period_start=start, period_end=end)
            )
        if kind is QuotaKind.SCRAPE_CHAPTERS:
            scraping = ScrapingService(self._session)
            return float(
                await scraping.chapters_in_period(user_id, period_start=start, period_end=end)
            )
        imports = ImportService(self._session)
        return float(
            await imports.completed_in_period(user_id, period_start=start, period_end=end)
        )

    async def _llm_tail(
        self, kind: QuotaKind, user_id: UUID, start: datetime, end: datetime
    ) -> float:
        """Today's live LLM tail. Two LLM kinds -> two usage_summary calls; both
        are single index scans over one day (documented, fine at this scale)."""
        summary = await self._llm.usage_summary(user_id, period_start=start, period_end=end)
        if kind is QuotaKind.LLM_TOKENS:
            return float(summary.tokens_in + summary.tokens_out)
        return float(summary.total_cost)
