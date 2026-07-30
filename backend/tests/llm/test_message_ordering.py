"""Conversation message ordering is insertion order even when timestamps tie.

`created_at` comes from the Python clock, whose resolution is ~15ms on
Windows — a batch of messages appended inside one request can share an
identical timestamp. Ordering must not fall back to the random UUID PK.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.modules.llm.repository import LlmRepository
from app.modules.users.schemas import UserCreate
from app.modules.users.service import UserService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

MESSAGE_COUNT = 12


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def _conversation_with_messages(session: AsyncSession) -> tuple[LlmRepository, object]:
    user = await UserService(session).ensure_user(
        UserCreate(username=f"ordering_{uuid4().hex[:8]}", password="test-pass-123")
    )
    repo = LlmRepository(session)
    conversation = await repo.create_conversation(user.id)
    for index in range(MESSAGE_COUNT):
        await repo.add_message(
            conversation.id,
            role="user" if index % 2 == 0 else "assistant",
            content=f"message {index}",
        )
    await session.commit()
    return repo, conversation


@pytest.mark.integration
async def test_list_all_messages_keeps_insertion_order(session: AsyncSession) -> None:
    repo, conversation = await _conversation_with_messages(session)
    rows = await repo.list_all_messages(conversation.id)  # type: ignore[attr-defined]
    assert [row.content for row in rows] == [f"message {i}" for i in range(MESSAGE_COUNT)]


@pytest.mark.integration
async def test_list_messages_window_keeps_insertion_order(session: AsyncSession) -> None:
    repo, conversation = await _conversation_with_messages(session)
    rows = await repo.list_messages(conversation.id, limit=5)  # type: ignore[attr-defined]
    assert [row.content for row in rows] == [f"message {i}" for i in range(7, MESSAGE_COUNT)]
