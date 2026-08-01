"""Backoffice tool-call audit listing with attribution join (needs Postgres)."""

from __future__ import annotations

from uuid import UUID

import pytest
from app.modules.llm.models import Conversation, ConversationMessage, ToolCallRecord
from httpx import AsyncClient

from tests.admin.helpers import create_user, login, seed_session

BASE = "/api/admin/tool-calls"


@pytest.fixture
async def admin(client: AsyncClient) -> UUID:
    user_id = await create_user("boss", is_admin=True)
    login(client, user_id, "boss")
    return user_id


async def seed_tool_calls(user_id: UUID) -> None:
    """One attributed success + one orphan failure (message_id NULL)."""
    async with seed_session() as session:
        conversation = Conversation(user_id=user_id, title="audit")
        session.add(conversation)
        await session.flush()
        message = ConversationMessage(
            conversation_id=conversation.id, role="assistant", content="…"
        )
        session.add(message)
        await session.flush()
        session.add(
            ToolCallRecord(
                message_id=message.id,
                tool_name="search_books",
                input={"q": "dragons"},
                output={"ok": True},
                status="success",
                risk_level="read_only",
                duration_ms=12,
                confirmed_by_user=False,
            )
        )
        session.add(
            ToolCallRecord(
                message_id=None,
                tool_name="scrape_url",
                input={},
                status="failed",
                risk_level="confirmation_required",
                error="boom",
            )
        )


@pytest.mark.integration
async def test_lists_all_with_attribution(client: AsyncClient, admin: UUID) -> None:
    reader = await create_user("reader")
    await seed_tool_calls(reader)
    response = await client.get(BASE)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    by_tool = {row["tool_name"]: row for row in payload["items"]}
    assert by_tool["search_books"]["user_id"] == str(reader)
    assert by_tool["search_books"]["input"] == {"q": "dragons"}
    assert by_tool["search_books"]["duration_ms"] == 12
    assert by_tool["scrape_url"]["user_id"] is None
    assert by_tool["scrape_url"]["error"] == "boom"


@pytest.mark.integration
async def test_filters(client: AsyncClient, admin: UUID) -> None:
    reader = await create_user("reader")
    await seed_tool_calls(reader)
    by_name = await client.get(BASE, params={"tool_name": "search_books"})
    assert by_name.json()["total"] == 1
    assert by_name.json()["items"][0]["tool_name"] == "search_books"
    by_status = await client.get(BASE, params={"status": "failed"})
    assert by_status.json()["total"] == 1
    by_risk = await client.get(BASE, params={"risk_level": "read_only"})
    assert by_risk.json()["total"] == 1
    none_left = await client.get(BASE, params={"tool_name": "search_books", "status": "failed"})
    assert none_left.json()["total"] == 0


@pytest.mark.integration
async def test_pagination_envelope(client: AsyncClient, admin: UUID) -> None:
    reader = await create_user("reader")
    await seed_tool_calls(reader)
    response = await client.get(BASE, params={"limit": 1, "offset": 0})
    payload = response.json()
    assert payload["total"] == 2
    assert len(payload["items"]) == 1
    assert payload["limit"] == 1
