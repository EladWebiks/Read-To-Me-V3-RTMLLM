"""Chat: persist turns and stream orchestrated assistant replies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.llm.exceptions import ConversationNotFoundError, LlmError
from app.modules.llm.repository import LlmRepository
from app.modules.llm.service import LlmService
from app.modules.llm.sse import ChatSseEvent
from app.modules.llm.types import Role
from app.modules.orchestration.exceptions import OrchestrationError
from app.modules.orchestration.service import OrchestrationService

_TITLE_MAX = 80

# Re-export for tests / callers that imported from chat_service.
__all__ = ["ChatService", "ChatSseEvent"]


class ChatService:
    """Owns conversation persistence; delegates assistant turns to orchestration."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._repo = LlmRepository(session)
        self._llm = LlmService(session, settings)
        self._settings = settings

    async def get_conversation(self, user_id: UUID, conversation_id: UUID) -> dict[str, Any]:
        """Load an owned conversation with messages."""
        conv = await self._repo.get_conversation_for_user(conversation_id, user_id)
        if conv is None:
            raise ConversationNotFoundError(str(conversation_id))
        messages = await self._repo.list_messages(conversation_id, limit=200)
        return {
            "id": conv.id,
            "title": conv.title,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at,
                }
                for m in messages
            ],
        }

    async def stream_chat(
        self,
        user_id: UUID,
        message: str,
        conversation_id: UUID | None,
        ui_context: dict[str, Any] | None = None,
    ) -> AsyncIterator[ChatSseEvent]:
        """Persist user turn, run orchestrated assistant turn."""
        self._llm.ensure_enabled()
        text = message.strip()
        try:
            conv_id = await self._prepare_conversation(user_id, text, conversation_id)
            yield ChatSseEvent("meta", {"conversation_id": str(conv_id)})
            orch = self._orchestration()
            async for event in orch.run(user_id, conv_id, ui_context=ui_context):
                yield event
        except (LlmError, OrchestrationError) as exc:
            yield ChatSseEvent("error", {"detail": str(exc)})

    async def stream_confirm(
        self,
        user_id: UUID,
        conversation_id: UUID,
        call_id: UUID,
        *,
        approved: bool,
        values: dict[str, Any] | None,
    ) -> AsyncIterator[ChatSseEvent]:
        """Resume a turn after HITL confirmation (new SSE stream)."""
        self._llm.ensure_enabled()
        try:
            conv = await self._repo.get_conversation_for_user(conversation_id, user_id)
            if conv is None:
                raise ConversationNotFoundError(str(conversation_id))
            yield ChatSseEvent(
                "meta",
                {"conversation_id": str(conversation_id), "call_id": str(call_id)},
            )
            orch = self._orchestration()
            async for event in orch.resume_confirm(
                user_id,
                conversation_id,
                call_id,
                approved=approved,
                values=values,
            ):
                yield event
        except (LlmError, OrchestrationError) as exc:
            yield ChatSseEvent("error", {"detail": str(exc)})

    def _orchestration(self) -> OrchestrationService:
        return OrchestrationService(
            self._session,
            self._settings,
            self._llm,
            self._repo,
        )

    async def _prepare_conversation(
        self,
        user_id: UUID,
        text: str,
        conversation_id: UUID | None,
    ) -> UUID:
        if conversation_id is None:
            created = await self._repo.create_conversation(user_id, title=_title_from(text))
            conv_id = created.id
        else:
            existing = await self._repo.get_conversation_for_user(conversation_id, user_id)
            if existing is None:
                raise ConversationNotFoundError(str(conversation_id))
            conv_id = existing.id
            await self._repo.set_conversation_title(conv_id, _title_from(text))

        await self._repo.add_message(conv_id, role=Role.USER.value, content=text)
        await self._session.commit()
        return conv_id


def _title_from(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= _TITLE_MAX:
        return cleaned
    return cleaned[: _TITLE_MAX - 3] + "..."
