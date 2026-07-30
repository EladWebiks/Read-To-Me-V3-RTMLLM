"""All-models-disabled degrades exactly like llm_enabled=false at the chat boundary.

Both cases raise from `await self._llm.ensure_ready()` — before any SSE
event is yielded — and both exception types map to 503 in
core/exceptions.py (_llm_disabled, _llm_no_candidate).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from app.core.db import SessionLocal
from app.modules.llm import catalog
from app.modules.llm.chat_service import ChatService
from app.modules.llm.exceptions import LlmDisabledError, NoCandidateModelError
from sqlalchemy import text

from tests.factories import make_settings


async def _disable_all_models() -> None:
    async with SessionLocal() as session:
        await session.execute(text("UPDATE model_configurations SET enabled = false"))
        await session.commit()
    catalog.invalidate()


@pytest.mark.integration
async def test_llm_disabled_raises_before_any_event(seeded_catalog: None) -> None:
    async with SessionLocal() as session:
        service = ChatService(session, make_settings(llm_enabled=False))
        stream = service.stream_chat(uuid4(), "hello", None)
        with pytest.raises(LlmDisabledError):
            await anext(stream)


@pytest.mark.integration
async def test_all_models_disabled_raises_before_any_event(seeded_catalog: None) -> None:
    await _disable_all_models()
    async with SessionLocal() as session:
        service = ChatService(session, make_settings(llm_enabled=True, gemini_api_key="test-key"))
        stream = service.stream_chat(uuid4(), "hello", None)
        with pytest.raises(NoCandidateModelError):
            await anext(stream)


@pytest.mark.integration
async def test_all_models_disabled_blocks_confirm_resume(seeded_catalog: None) -> None:
    await _disable_all_models()
    async with SessionLocal() as session:
        service = ChatService(session, make_settings(llm_enabled=True, gemini_api_key="test-key"))
        confirm = service.stream_confirm(uuid4(), uuid4(), uuid4(), approved=True, values=None)
        with pytest.raises(NoCandidateModelError):
            await anext(confirm)
