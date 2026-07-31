"""Shared FK-ordered user cleanup for authorization integration tests.

Every table referencing `users` must be emptied before `users` itself, or
orphaned rows left by unrelated test modules (LLM conversations, scraping
jobs, …) make `DELETE FROM users` fail on a foreign-key violation.
"""

from __future__ import annotations

from app.modules.users import membership_registry
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

CLEAR_ORDER = (
    "scraping_job_items",
    "scraping_jobs",
    "download_jobs",
    "reading_progress",
    "chapters",
    "user_books",
    "books",
    "cost_records",
    "llm_executions",
    "tool_calls",
    "conversation_messages",
    "conversations",
    "app_settings_audit",
    "app_settings",
    # Usage rollup (Part D): both reference users; the llm_*_daily tables do not.
    "usage_daily",
    "quota_rejections",
    # Per-user quota overrides reference users; membership_quotas do not.
    "user_quota_overrides",
    "users",
)

_NON_FREE_TIER_CLEANUP = (
    "DELETE FROM membership_policies WHERE membership <> 'free'",
    "DELETE FROM membership_quotas WHERE membership <> 'free'",
    "DELETE FROM memberships WHERE slug <> 'free'",
)


async def clear_users(executor: AsyncSession | AsyncConnection) -> None:
    """Delete every user and all rows that reference them."""
    for table in CLEAR_ORDER:
        await executor.execute(text(f"DELETE FROM {table}"))  # noqa: S608 - fixed literals
    for stmt in _NON_FREE_TIER_CLEANUP:
        await executor.execute(text(stmt))
    # The tier registry is a process-level 30s snapshot and seed_membership_policies
    # derives its inserts from it. Without this, a snapshot warmed with a tier we
    # just deleted makes the next seed insert a membership_policies row whose FK
    # target is gone.
    membership_registry.invalidate()
