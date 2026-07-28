"""Tool-less chat: persist turns and stream assistant replies."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.llm.capabilities import ModelCapability
from app.modules.llm.exceptions import ConversationNotFoundError, LlmError, NoCandidateModelError
from app.modules.llm.models import ConversationMessage
from app.modules.llm.registry import ModelSpec
from app.modules.llm.repository import LlmRepository
from app.modules.llm.service import LlmService
from app.modules.llm.telemetry import TelemetryContext, estimate_cost
from app.modules.llm.types import GenerateTextRequest, Message, Role, Usage

_SYSTEM = (
    "You are the RTM (Read To Me) assistant. Be helpful and concise. "
    "You cannot take actions yet — tools arrive in a later milestone. "
    "Do not claim to search the library, scrape sites, or change user data."
)
_HISTORY_LIMIT = 40
_TITLE_MAX = 80
ChatEventKind = Literal["meta", "delta", "done", "error"]


@dataclass(frozen=True, slots=True)
class ChatSseEvent:
    """One SSE payload for the chat stream."""

    event: ChatEventKind
    data: dict[str, Any]

    def encode(self) -> str:
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"


class ChatService:
    """Owns conversation persistence around LlmService streaming."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._repo = LlmRepository(session)
        self._llm = LlmService(session, settings)

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
    ) -> AsyncIterator[ChatSseEvent]:
        """Persist user turn, stream assistant text, persist assistant turn."""
        self._llm.ensure_enabled()
        text = message.strip()
        try:
            conv_id = await self._prepare_conversation(user_id, text, conversation_id)
            yield ChatSseEvent("meta", {"conversation_id": str(conv_id)})
            async for event in self._stream_assistant(conv_id):
                yield event
        except LlmError as exc:
            yield ChatSseEvent("error", {"detail": str(exc)})

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

    async def _stream_assistant(self, conversation_id: UUID) -> AsyncIterator[ChatSseEvent]:
        history = await self._repo.list_messages(conversation_id, limit=_HISTORY_LIMIT)
        req = GenerateTextRequest(messages=_to_llm_messages(history), task="chat")
        model = self._require_chat_model()
        parts: list[str] = []
        usage = Usage(0, 0)
        started = time.perf_counter()
        async for chunk in self._llm.stream_text(req):
            if chunk.text:
                parts.append(chunk.text)
                yield ChatSseEvent("delta", {"text": chunk.text})
            if chunk.usage is not None:
                usage = chunk.usage
        yield await self._persist_assistant(conversation_id, model, parts, usage, started)

    def _require_chat_model(self) -> ModelSpec:
        matches = self._llm.router.candidates(ModelCapability.FAST_CHAT)
        if not matches:
            raise NoCandidateModelError(ModelCapability.FAST_CHAT.value)
        return matches[0]

    async def _persist_assistant(
        self,
        conversation_id: UUID,
        model: ModelSpec,
        parts: list[str],
        usage: Usage,
        started: float,
    ) -> ChatSseEvent:
        full = "".join(parts)
        assistant = await self._repo.add_message(
            conversation_id,
            role=Role.ASSISTANT.value,
            content=full,
            tokens_in=usage.tokens_in,
            tokens_out=usage.tokens_out,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        await self._llm.telemetry.write_result(
            TelemetryContext(
                task="chat",
                model=model,
                fallback_used=False,
                conversation_id=conversation_id,
            ),
            usage=usage,
            latency_ms=latency_ms,
            status="ok",
            error=None,
        )
        await self._session.commit()
        return ChatSseEvent(
            "done",
            {
                "message_id": str(assistant.id),
                "conversation_id": str(conversation_id),
                "cost_usd": estimate_cost(model, usage),
                "tokens_in": usage.tokens_in,
                "tokens_out": usage.tokens_out,
            },
        )


def _title_from(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= _TITLE_MAX:
        return cleaned
    return cleaned[: _TITLE_MAX - 3] + "..."


def _to_llm_messages(history: list[ConversationMessage]) -> list[Message]:
    messages = [Message(role=Role.SYSTEM, content=_SYSTEM)]
    for row in history:
        try:
            role = Role(row.role)
        except ValueError:
            continue
        if role == Role.SYSTEM:
            continue
        messages.append(Message(role=role, content=row.content))
    return messages
