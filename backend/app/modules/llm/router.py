"""LLM HTTP routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.deps import get_current_user, get_db
from app.modules.llm.schemas import ModelListResponse
from app.modules.llm.service import LlmService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/llm", tags=["llm"])


def _llm_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LlmService:
    return LlmService(session, settings)


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    _user: Annotated[UserRead, Depends(get_current_user)],
    service: Annotated[LlmService, Depends(_llm_service)],
) -> ModelListResponse:
    """List enabled/catalog models and capabilities (no secrets)."""
    return service.list_public_models()
