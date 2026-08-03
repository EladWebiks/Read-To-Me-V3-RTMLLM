"""Aggregation-only DTOs for the backoffice API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.downloads.schemas import DownloadJobAdminRead
from app.modules.llm.schemas import (
    AdminUsageOverview,
    LlmExecutionRead,
    ToolCallAdminRead,
    UserUsageRead,
)
from app.modules.scraping.schemas import ScrapeJobAdminRead


class Page[ItemT](BaseModel):
    """Uniform limit/offset pagination envelope for admin lists."""

    items: list[ItemT]
    total: int
    limit: int
    offset: int


class AdminUsageSummary(AdminUsageOverview):
    """LLM overview + quota-rejection aggregates over the SELECTED period.

    Rejection counts are hybrid like every other aggregate: rolled rejected_*
    metrics for closed days plus today's raw quota_rejections rows.
    """

    rejections: int = 0
    rejections_by_kind: dict[str, int] = Field(default_factory=dict)


class AdminUserUsageRead(UserUsageRead):
    """Per-user usage row + identity/quota columns resolved by the admin router.

    month_* cover the CURRENT UTC calendar month regardless of the selected
    period. *_limit fields: None = unlimited (no membership_quotas rule).
    """

    username: str | None = None
    membership: str | None = None
    month_tokens: int = 0
    month_cost: float = 0.0
    llm_tokens_limit: float | None = None
    llm_cost_limit: float | None = None
    month_audio_chapters: int = 0
    month_scrape_chapters: int = 0
    month_epub_imports: int = 0
    period_rejections: int = 0


class AdminLlmExecutionRead(LlmExecutionRead):
    """Execution row + username resolved by the admin router."""

    username: str | None = None


class AdminToolCallRead(ToolCallAdminRead):
    """Tool-call audit row + identity resolved by the admin router."""

    username: str | None = None
    email: str | None = None


class AdminScrapeJobRead(ScrapeJobAdminRead):
    """Scraping job row + username resolved by the admin router."""

    username: str | None = None


class AdminDownloadJobRead(DownloadJobAdminRead):
    """Download job row + username resolved by the admin router."""

    username: str | None = None
