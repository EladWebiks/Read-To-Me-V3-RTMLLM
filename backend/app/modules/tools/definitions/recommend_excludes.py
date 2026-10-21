"""Server-side exclude titles for recommend follow-up batches."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.discovery.recommend import exclude_title_key
from app.modules.llm.models import Conversation, ConversationMessage, ToolCallRecord

_TOOL = "recommend_discovered_books"
_MAX = 50
_MIN_TITLE_LEN = 3
_BY_LINE = re.compile(
    r"(?im)^\s*(?:\d+[.)]\s*|[-*•]\s*)?(?P<title>.+?)\s+by\s+\S.+$",
)
_TABLE_LINE = re.compile(r"(?im)^\s*[-*•]\s+(?P<title>[^|\n]+?)\s*\|")
_DASH_LINE = re.compile(r"(?im)^\s*[-*•]\s+(?P<title>.+?)\s+—\s+")


def merge_exclude_titles(*groups: list[str]) -> list[str]:
    """Dedupe titles (article-insensitive) and hard-cap length."""
    seen: set[str] = set()
    out: list[str] = []
    for group in groups:
        for raw in group:
            title = " ".join(raw.split()).strip()
            if not title:
                continue
            key = exclude_title_key(title)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(title)
            if len(out) >= _MAX:
                return out
    return out


def titles_from_recommend_output(output: dict[str, Any] | None) -> list[str]:
    """Pull book titles from a recommend_discovered_books tool payload."""
    if not output:
        return []
    results = output.get("results")
    if not isinstance(results, list):
        return []
    titles: list[str] = []
    for item in results:
        title = _title_from_result_item(item)
        if title:
            titles.append(title)
    return titles


def _title_from_result_item(item: object) -> str | None:
    if not isinstance(item, dict):
        return None
    title = item.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    book = item.get("book")
    if isinstance(book, dict):
        nested = book.get("title")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    return None


def titles_from_assistant_text(content: str) -> list[str]:
    """Best-effort titles from prior assistant listings in this chat."""
    titles: list[str] = []
    for match in _BY_LINE.finditer(content):
        title = match.group("title").strip(" *-_\"'")
        if len(title) >= _MIN_TITLE_LEN:
            titles.append(title)
    for match in _TABLE_LINE.finditer(content):
        title = match.group("title").strip()
        if len(title) >= _MIN_TITLE_LEN:
            titles.append(title)
    for match in _DASH_LINE.finditer(content):
        title = match.group("title").strip(" *-_\"'")
        if len(title) >= _MIN_TITLE_LEN:
            titles.append(title)
    return titles


async def prior_recommend_exclude_titles(
    session: AsyncSession,
    *,
    user_id: UUID,
    conversation_id: UUID,
) -> list[str]:
    """Titles already recommended for this user since the conversation started."""
    conv = (
        await session.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if conv is None:
        return []
    outputs = (
        (
            await session.execute(
                select(ToolCallRecord.output).where(
                    ToolCallRecord.user_id == user_id,
                    ToolCallRecord.tool_name == _TOOL,
                    ToolCallRecord.status == "success",
                    ToolCallRecord.output.is_not(None),
                    ToolCallRecord.created_at >= conv.created_at,
                )
            )
        )
        .scalars()
        .all()
    )
    from_tools: list[str] = []
    for output in outputs:
        if isinstance(output, dict):
            from_tools.extend(titles_from_recommend_output(output))
    messages = (
        (
            await session.execute(
                select(ConversationMessage.content).where(
                    ConversationMessage.conversation_id == conversation_id,
                    ConversationMessage.role == "assistant",
                )
            )
        )
        .scalars()
        .all()
    )
    from_chat: list[str] = []
    for content in messages:
        from_chat.extend(titles_from_assistant_text(content))
    return merge_exclude_titles(from_tools, from_chat)
