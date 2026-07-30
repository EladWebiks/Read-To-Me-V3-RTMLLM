"""Shared FK-ordered user cleanup for authorization integration tests.

Every table referencing `users` must be emptied before `users` itself, or
orphaned rows left by unrelated test modules (LLM conversations, scraping
jobs, …) make `DELETE FROM users` fail on a foreign-key violation.
"""

from __future__ import annotations

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
    "users",
)


async def clear_users(executor: AsyncSession | AsyncConnection) -> None:
    """Delete every user and all rows that reference them."""
    for table in CLEAR_ORDER:
        await executor.execute(text(f"DELETE FROM {table}"))  # noqa: S608 - fixed literals
