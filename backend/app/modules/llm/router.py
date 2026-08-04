"""LLM HTTP routes (models catalog + chat SSE)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.deps import get_current_user, get_db, get_effective_settings
from app.modules.llm.chat_service import ChatService
from app.modules.llm.schemas import (
    ChatRequest,
    ConfirmRequest,
    ConversationListRead,
    ConversationRead,
    ModelListResponse,
)
from app.modules.llm.service import LlmService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/llm", tags=["llm"])
chat_router = APIRouter(prefix="/chat", tags=["chat"])


def _llm_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LlmService:
    return LlmService(session, settings)


def _chat_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_effective_settings)],
) -> ChatService:
    return ChatService(session, settings)


def _sse(events: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        events,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    _user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[LlmService, Depends(_llm_service)],
) -> ModelListResponse:
    """List enabled/catalog models and capabilities (no secrets)."""
    return await service.list_public_models()


@chat_router.post("")
async def stream_chat(
    body: ChatRequest,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(_chat_service)],
) -> StreamingResponse:
    """Stream an assistant reply (SSE). Persists user + assistant messages."""

    async def _events() -> AsyncIterator[str]:
        async for event in service.stream_chat(
            user,
            body.message,
            body.conversation_id,
            ui_context=body.ui_context.model_dump(mode="json") if body.ui_context else None,
        ):
            yield event.encode()

    return _sse(_events())


@chat_router.post("/{conversation_id}/confirm")
async def stream_confirm(
    conversation_id: UUID,
    body: ConfirmRequest,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(_chat_service)],
) -> StreamingResponse:
    """Resume a paused turn after HITL approve/decline (new SSE stream)."""

    async def _events() -> AsyncIterator[str]:
        async for event in service.stream_confirm(
            user,
            conversation_id,
            body.call_id,
            approved=body.approved,
            values=body.values,
        ):
            yield event.encode()

    return _sse(_events())


@chat_router.get("", response_model=ConversationListRead)
async def list_conversations(
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(_chat_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ConversationListRead:
    """List the signed-in user's conversations (newest activity first)."""
    return await service.list_conversations(user.id, limit=limit, offset=offset)


@chat_router.get("/{conversation_id}", response_model=ConversationRead)
async def get_conversation(
    conversation_id: UUID,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(_chat_service)],
) -> ConversationRead:
    """Load one owned conversation with messages."""
    payload = await service.get_conversation(user.id, conversation_id)
    return ConversationRead.model_validate(payload)


@chat_router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_conversation(
    conversation_id: UUID,
    user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(_chat_service)],
) -> Response:
    """Delete an owned conversation and its messages."""
    await service.delete_conversation(user.id, conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
